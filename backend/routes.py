"""
🎮 DreaMMO API Routes
Main game mechanics endpoints
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import json
import random
from database.connection import fetch_one, fetch_all, execute, fetch_val
from passlib.hash import bcrypt
from mob_population import get_zone_mob_entries, restore_zone_if_fully_dead
from security import (
    create_access_token,
    ensure_character_owner,
    ensure_user_matches,
    get_current_user_id,
)
from progression import apply_experience_and_level_up
from oren_daily_quests import ensure_oren_daily_quests_for_npc


def _filter_fox_forest_mobs(rows: list[dict]) -> list[dict]:
    """Keep only canonical fox mobs and collapse duplicates by best alive candidate."""
    targets = ["старый лис", "молодой лис", "матерый лис", "лисий вожак"]

    def _match_target(name: str) -> str | None:
        normalized = str(name or "").strip().lower()
        for t in targets:
            if t in normalized:
                return t
        return None

    best_by_target = {}
    for row in rows:
        target_key = _match_target(row.get("name"))
        if not target_key:
            continue
        current = best_by_target.get(target_key)
        row_alive = int(row.get("alive_count") or 0)
        cur_alive = int(current.get("alive_count") or 0) if current else -1
        row_level = int(row.get("level") or 0)
        cur_level = int(current.get("level") or 0) if current else -1
        if current is None or row_alive > cur_alive or (row_alive == cur_alive and row_level > cur_level):
            best_by_target[target_key] = row

    return [best_by_target[t] for t in targets if t in best_by_target]

# ===== Route Definitions =====
router = APIRouter(prefix="/api", tags=["game"])

COMMON_STARTER_PACK = {
    "Малое зелье лечения": 3,
}

MELEE_STARTER_PACK = {
    "Учебный меч": 1,
    "Учебный двуручный меч": 1,
    "Учебный щит": 1,
    "Потрепанная куртка": 1,
}

MAGE_STARTER_PACK = {
    "Учебный посох": 1,
    "Роба ученика": 1,
}

RANGED_STARTER_PACK = {
    "Учебный лук": 1,
    "Потрепанная куртка": 1,
}


def _inventory_count(character_id: int, item_id: int) -> int:
    return int(
        fetch_val(
            "SELECT COALESCE(SUM(quantity), 0) FROM inventory WHERE character_id = %s AND item_id = %s",
            character_id,
            item_id,
        )
        or 0
    )


def _inventory_add(character_id: int, item_id: int, quantity: int) -> None:
    if quantity <= 0:
        return
    existing = fetch_one(
        "SELECT id, quantity FROM inventory WHERE character_id = %s AND item_id = %s AND slot IS NULL LIMIT 1",
        character_id,
        item_id,
    )
    if existing:
        execute("UPDATE inventory SET quantity = quantity + %s WHERE id = %s", quantity, existing[0])
    else:
        execute(
            "INSERT INTO inventory (character_id, item_id, quantity, equipped, slot) VALUES (%s, %s, %s, FALSE, NULL)",
            character_id,
            item_id,
            quantity,
        )


def _inventory_remove(character_id: int, item_id: int, quantity: int) -> None:
    if quantity <= 0:
        return
    rows = fetch_all(
        "SELECT id, quantity FROM inventory WHERE character_id = %s AND item_id = %s ORDER BY created_at ASC",
        character_id,
        item_id,
    )
    remaining = quantity
    for row_id, row_qty in rows:
        if remaining <= 0:
            break
        take = min(remaining, int(row_qty or 0))
        new_qty = int(row_qty or 0) - take
        if new_qty <= 0:
            execute("DELETE FROM inventory WHERE id = %s", row_id)
        else:
            execute("UPDATE inventory SET quantity = %s WHERE id = %s", new_qty, row_id)
        remaining -= take
    if remaining > 0:
        raise HTTPException(status_code=400, detail="Not enough materials in inventory")


def _starter_pack_for_class(class_name: str) -> dict:
    normalized = (class_name or "").strip().lower()
    pack = dict(COMMON_STARTER_PACK)

    if normalized in {"воин", "танк"}:
        pack.update(MELEE_STARTER_PACK)
    elif normalized in {"маг огня", "ледяной маг", "некромант", "целитель"}:
        pack.update(MAGE_STARTER_PACK)
    else:
        pack.update(RANGED_STARTER_PACK)

    return pack


def _honor_reward_for_quest(level_requirement: int, quest_type: str) -> int:
    lvl = int(level_requirement or 1)
    if lvl <= 1:
        reward = 1
    elif lvl <= 3:
        reward = 2
    elif lvl <= 5:
        reward = 3
    elif lvl <= 7:
        reward = 4
    else:
        reward = 5

    if (quest_type or "").lower() in {"boss", "dungeon", "elite"}:
        reward = min(5, reward + 1)

    return max(1, min(5, reward))


def _ensure_starter_pack(character_id: int) -> list:
    """Backfill missing class starter items for existing characters once."""
    class_row = fetch_one(
        """
        SELECT cc.name
        FROM characters c
        LEFT JOIN character_classes cc ON cc.id = c.class_id
        WHERE c.id = %s
        """,
        character_id,
    )
    starter_pack = _starter_pack_for_class(class_row[0] if class_row else "")

    granted = []
    for item_name, required_qty in starter_pack.items():
        item_id = fetch_val("SELECT id FROM items WHERE name = %s LIMIT 1", item_name)
        if not item_id:
            continue
        owned_qty = _inventory_count(character_id, int(item_id))
        missing = int(required_qty) - owned_qty
        if missing > 0:
            _inventory_add(character_id, int(item_id), int(missing))
            granted.append({"item_name": item_name, "quantity": int(missing)})
    return granted

# ===== Authentication =====
class RegisterModel(BaseModel):
    username: str
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class LoginModel(BaseModel):
    username: str
    password: str


class ChangePasswordModel(BaseModel):
    current_password: str
    new_password: str


class ChatSendModel(BaseModel):
    channel: str
    message: str


def _normalize_chat_channel(raw: str) -> str:
    return str(raw or "").strip().lower()


def _resolve_world_chat_label(location_id: int, location_name: str) -> str:
    # Keep user-facing naming simple for the starter map.
    if int(location_id or 0) == 1:
        return "Аурис"
    return str(location_name or "Мир").strip() or "Мир"


def _ensure_chat_table_indexes() -> None:
    execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_type_created ON chat_messages(chat_type, created_at)")
    execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_location_type_created ON chat_messages(location_id, chat_type, created_at)")


@router.get("/chat/channels/{character_id}", response_model=dict)
async def get_chat_channels(character_id: int, current_user_id: int = Depends(get_current_user_id)):
    """Return available chat channels after entering world."""
    ensure_character_owner(character_id, current_user_id)

    row = fetch_one(
        """
        SELECT c.current_location_id, l.name
        FROM characters c
        LEFT JOIN locations l ON l.id = c.current_location_id
        WHERE c.id = %s
        """,
        character_id,
    )
    location_id = int((row[0] if row and row[0] is not None else 1) or 1)
    location_name = str(row[1] if row and len(row) > 1 else "")
    world_label = _resolve_world_chat_label(location_id, location_name)

    return {
        "channels": [
            {"id": "world", "label": f"Мир - {world_label}", "location_id": location_id},
            {"id": "help", "label": "Помощь новичка", "location_id": None},
            {"id": "trade", "label": "Торговля", "location_id": None},
            {"id": "system", "label": "Системный", "location_id": None},
        ]
    }


@router.get("/chat/history/{character_id}", response_model=dict)
async def get_chat_history(
    character_id: int,
    channel: str,
    limit: int = 50,
    current_user_id: int = Depends(get_current_user_id),
):
    """Load chat history for world/help/trade channels."""
    ensure_character_owner(character_id, current_user_id)
    _ensure_chat_table_indexes()

    normalized_channel = _normalize_chat_channel(channel)
    if normalized_channel not in {"world", "help", "trade"}:
        raise HTTPException(status_code=400, detail="Unsupported chat channel")

    safe_limit = max(10, min(200, int(limit or 50)))

    if normalized_channel == "world":
        location_id = fetch_val("SELECT current_location_id FROM characters WHERE id = %s", character_id)
        location_id = int(location_id or 1)
        rows = fetch_all(
            """
            SELECT cm.id,
                   cm.sender_id,
                   COALESCE(ch.name, 'Игрок') AS sender_name,
                   cm.message,
                   cm.created_at,
                   cm.chat_type,
                   cm.location_id
            FROM chat_messages cm
            LEFT JOIN characters ch ON ch.id = cm.sender_id
            WHERE cm.chat_type = 'world'
              AND cm.location_id = %s
            ORDER BY cm.created_at DESC
            LIMIT %s
            """,
            location_id,
            safe_limit,
        )
    else:
        rows = fetch_all(
            """
            SELECT cm.id,
                   cm.sender_id,
                   COALESCE(ch.name, 'Игрок') AS sender_name,
                   cm.message,
                   cm.created_at,
                   cm.chat_type,
                   cm.location_id
            FROM chat_messages cm
            LEFT JOIN characters ch ON ch.id = cm.sender_id
            WHERE cm.chat_type = %s
            ORDER BY cm.created_at DESC
            LIMIT %s
            """,
            normalized_channel,
            safe_limit,
        )

    messages = [
        {
            "id": int(r[0]),
            "sender_id": int(r[1]) if r[1] is not None else None,
            "sender_name": r[2],
            "message": r[3],
            "created_at": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
            "channel": r[5],
            "location_id": int(r[6]) if r[6] is not None else None,
        }
        for r in reversed(rows)
    ]

    return {"channel": normalized_channel, "messages": messages}


@router.post("/chat/send/{character_id}", response_model=dict)
async def send_chat_message(
    character_id: int,
    payload: ChatSendModel,
    current_user_id: int = Depends(get_current_user_id),
):
    """Send chat message to world/help/trade channels."""
    ensure_character_owner(character_id, current_user_id)
    _ensure_chat_table_indexes()

    channel = _normalize_chat_channel(payload.channel)
    if channel not in {"world", "help", "trade"}:
        raise HTTPException(status_code=400, detail="Unsupported chat channel")

    message = str(payload.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Сообщение пустое")
    if len(message) > 400:
        raise HTTPException(status_code=400, detail="Сообщение слишком длинное (макс. 400 символов)")

    location_id = None
    if channel == "world":
        location_id = int(fetch_val("SELECT current_location_id FROM characters WHERE id = %s", character_id) or 1)

    message_id = fetch_val(
        """
        INSERT INTO chat_messages (sender_id, chat_type, location_id, message)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        character_id,
        channel,
        location_id,
        message,
    )

    sender_name = fetch_val("SELECT name FROM characters WHERE id = %s", character_id) or "Игрок"
    created_at = fetch_val("SELECT created_at FROM chat_messages WHERE id = %s", message_id)

    return {
        "status": "sent",
        "message": {
            "id": int(message_id),
            "sender_id": int(character_id),
            "sender_name": sender_name,
            "message": message,
            "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
            "channel": channel,
            "location_id": location_id,
        },
    }


@router.post("/auth/register", response_model=dict)
async def register(user: RegisterModel):
    """Create a new user account"""
    try:
        normalized_username = user.username.strip()
        normalized_email = user.email.strip().lower()

        exists = fetch_one(
            "SELECT id FROM users WHERE LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s)",
            normalized_username,
            normalized_email,
        )
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username or email already registered"
            )
        if len(user.password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        if len(normalized_username) < 3:
            raise HTTPException(status_code=400, detail="Username must be at least 3 characters")

        hashed = bcrypt.hash(user.password)
        execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s,%s,%s)",
            normalized_username, normalized_email, hashed
        )
        return {"status": "success", "data": {"registered": True}}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginModel):
    """Authenticate and return JWT token"""
    user_record = fetch_one(
        "SELECT id, password_hash FROM users WHERE LOWER(username) = LOWER(%s)",
        payload.username.strip(),
    )
    if not user_record or not bcrypt.verify(payload.password, user_record[1]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    user_id = user_record[0]
    token = create_access_token(user_id)
    # Обновим last_login и пометим персонажей пользователя как online
    try:
        execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s", user_id)
        execute("UPDATE characters SET is_online = TRUE WHERE user_id = %s", user_id)
    except Exception:
        pass
    return TokenResponse(access_token=token)


@router.post("/auth/change-password", response_model=dict)
async def change_password(
    payload: ChangePasswordModel,
    current_user_id: int = Depends(get_current_user_id),
):
    """Change password for currently authenticated user."""
    try:
        if len(payload.new_password) < 8:
            raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
        if payload.new_password == payload.current_password:
            raise HTTPException(status_code=400, detail="New password must be different from current password")

        user_record = fetch_one(
            "SELECT password_hash FROM users WHERE id = %s",
            current_user_id,
        )
        if not user_record:
            raise HTTPException(status_code=404, detail="User not found")

        if not bcrypt.verify(payload.current_password, user_record[0]):
            raise HTTPException(status_code=401, detail="Current password is incorrect")

        new_hash = bcrypt.hash(payload.new_password)
        execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            new_hash,
            current_user_id,
        )

        return {"status": "success", "message": "Password updated"}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to update password")


# ===== Characters =====
class CharacterCreate(BaseModel):
    name: str
    user_id: int
    class_id: int

class CharacterStats(BaseModel):
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    luck: int = 10

class CharacterResponse(BaseModel):
    id: int
    name: str
    level: int
    experience: int
    health_points: int
    max_health_points: int


class EquipItemModel(BaseModel):
    item_id: int


class UnequipItemModel(BaseModel):
    slot: str


def _resolve_equipment_slot(item_type: str) -> str:
    kind = (item_type or "").lower().strip()
    slot_map = {
        "weapon": "right_hand",
        "melee_weapon": "right_hand",
        "sword": "right_hand",
        "axe": "right_hand",
        "mace": "right_hand",
        "one_handed_weapon": "right_hand",
        "weapon_one_handed": "right_hand",
        "weapon_1h": "right_hand",
        "two_handed_weapon": "right_hand",
        "weapon_two_handed": "right_hand",
        "weapon_2h": "right_hand",
        "bow": "right_hand",
        "staff": "right_hand",
        "armor": "chest",
        "chest_armor": "chest",
        "body_armor": "chest",
        "robe": "chest",
        "shield": "left_hand",
        "helmet": "head",
        "hat": "head",
        "boots": "feet",
        "gloves": "hands",
        "pants": "legs",
        "ring": "ring",
        "accessory": "ring",
    }
    return slot_map.get(kind, "")


def _normalize_equipment_slot(slot: str) -> str:
    normalized = (slot or "").strip().lower()
    slot_aliases = {
        "main_hand": "right_hand",
        "off_hand": "left_hand",
        "body": "chest",
        "torso": "chest",
    }
    return slot_aliases.get(normalized, normalized)


def _slot_aliases_for_query(slot: str) -> list:
    normalized = _normalize_equipment_slot(slot)
    aliases = {
        "right_hand": ["right_hand", "main_hand"],
        "left_hand": ["left_hand", "off_hand"],
        "chest": ["chest", "body", "torso"],
        "head": ["head"],
        "legs": ["legs"],
        "feet": ["feet"],
        "ring_left": ["ring_left"],
        "ring_right": ["ring_right"],
        "both_hands": ["both_hands"],
    }
    return aliases.get(normalized, [normalized])


def _is_two_handed_item(item_type: str, item_name: str, item_description: str) -> bool:
    kind = (item_type or "").lower().strip()
    text = f"{item_name or ''} {item_description or ''}".lower()
    if kind in {"two_handed_weapon", "weapon_2h", "weapon_two_handed"}:
        return True
    markers = ["двуруч", "двумя руками", "two-handed", "2h", "greatsword", "polearm"]
    return any(marker in text for marker in markers)

@router.get("/characters/{character_id}/abilities", response_model=dict)
async def get_character_abilities(character_id: int):
    """Get abilities for a character"""
    try:
        abilities = fetch_all(
            """
            SELECT a.id, a.name, a.description, a.ability_type, a.mana_cost, a.cooldown, 
                   a.damage_min, a.damage_max, a.healing, a.effect_type, ca.level, ca.cooldown_remaining
            FROM character_abilities ca
            JOIN abilities a ON ca.ability_id = a.id
            WHERE ca.character_id = %s
            ORDER BY a.ability_type, a.name
            """,
            character_id
        )
        return {
            "abilities": [
                {
                    "id": a[0],
                    "name": a[1],
                    "description": a[2],
                    "type": a[3],
                    "mana_cost": a[4],
                    "cooldown": a[5],
                    "damage_min": a[6],
                    "damage_max": a[7],
                    "healing": a[8],
                    "effect_type": a[9],
                    "level": a[10],
                    "cooldown_remaining": a[11]
                }
                for a in abilities
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/races", response_model=dict)
async def get_races():
    """Get all available character races"""
    try:
        races = fetch_all("""
            SELECT id, name, description, strength_bonus, dexterity_bonus, constitution_bonus, 
                   intelligence_bonus, wisdom_bonus, luck_bonus, health_bonus, mana_bonus
            FROM races ORDER BY id
        """)
        
        result = []
        for r in races:
            # Get passive abilities for this race
            passives = fetch_all("""
                SELECT MIN(a.id) AS id, a.name, a.description
                FROM race_passive_abilities rpa
                JOIN abilities a ON rpa.ability_id = a.id
                WHERE rpa.race_id = %s
                GROUP BY a.name, a.description
                ORDER BY a.name
            """, r[0])
            
            race_data = {
                "id": r[0],
                "name": r[1],
                "description": r[2],
                "bonuses": {
                    "strength": r[3],
                    "dexterity": r[4],
                    "constitution": r[5],
                    "intelligence": r[6],
                    "wisdom": r[7],
                    "luck": r[8],
                    "health": r[9],
                    "mana": r[10]
                },
                "passive_abilities": [
                    {
                        "id": p[0],
                        "name": p[1],
                        "description": p[2]
                    }
                    for p in passives
                ]
            }
            result.append(race_data)
        
        return {"races": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/classes", response_model=dict)
async def get_classes():
    """Get all available character classes"""
    try:
        classes = fetch_all(
            """
            SELECT id, name, description, base_health, base_mana,
                   COALESCE(base_strength, 10), COALESCE(base_dexterity, 10),
                   COALESCE(base_constitution, 10), COALESCE(base_intelligence, 10),
                   COALESCE(base_wisdom, 10), COALESCE(base_luck, 10),
                   primary_stat
            FROM character_classes
            ORDER BY id
            """
        )
        return {
            "classes": [
                {
                    "id": c[0],
                    "name": c[1],
                    "description": c[2],
                    "base_health": c[3],
                    "base_mana": c[4],
                    "base_stats": {
                        "strength": c[5],
                        "dexterity": c[6],
                        "constitution": c[7],
                        "intelligence": c[8],
                        "wisdom": c[9],
                        "luck": c[10],
                    },
                    "primary_stat": c[11],
                }
                for c in classes
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/characters/create", response_model=dict)
async def create_character(data: dict, current_user_id: int = Depends(get_current_user_id)):
    """Create new character for player"""
    try:
        user_id = data.get('user_id') or current_user_id
        name = data.get('name')
        class_id = data.get('class_id')
        race_id = data.get('race_id')
        
        if not all([user_id, name, class_id, race_id]):
            raise HTTPException(status_code=400, detail="Missing required fields")

        ensure_user_matches(int(user_id), current_user_id)
        
        # Check if character name exists
        existing = fetch_one("SELECT id FROM characters WHERE name = %s", name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Character name already taken"
            )
        
        # Get race and class bonuses
        race = fetch_one("SELECT strength_bonus, dexterity_bonus, constitution_bonus, intelligence_bonus, wisdom_bonus, luck_bonus FROM races WHERE id = %s", race_id)
        char_class = fetch_one(
            """
            SELECT base_health, base_mana,
                   COALESCE(base_strength, 10), COALESCE(base_dexterity, 10),
                   COALESCE(base_constitution, 10), COALESCE(base_intelligence, 10),
                   COALESCE(base_wisdom, 10), COALESCE(base_luck, 10)
            FROM character_classes
            WHERE id = %s
            """,
            class_id,
        )
        
        if not race or not char_class:
            raise HTTPException(status_code=404, detail="Invalid race or class")
        
        # Create base stats with race bonuses
        base_health = char_class[0] + (race[2] * 5)  # constitution bonus affects health
        base_mana = char_class[1] + (race[3] * 3)    # intelligence bonus affects mana
        
        # Create character with spawn location set to Элдория city (location_id = 1)
        default_city_zone = fetch_one(
            """
            SELECT id
            FROM mob_spawn_zones
            WHERE location_id = 1
            ORDER BY
                CASE WHEN zone_name = 'Город новичков Аурис' THEN 0 ELSE 1 END,
                CASE WHEN zone_type = 'city' THEN 0 ELSE 1 END,
                id
            LIMIT 1
            """
        )
        default_city_zone_id = int(default_city_zone[0]) if default_city_zone else None
        execute(
            "INSERT INTO characters (user_id, name, race_id, class_id, level, experience, health_points, max_health_points, mana_points, max_mana_points, gold, silver, current_location_id, current_zone_id, position_x, position_y) VALUES (%s, %s, %s, %s, 1, 0, %s, %s, %s, %s, 100, 100, 1, %s, 0, 0)",
            user_id, name, race_id, class_id, base_health, base_health, base_mana, base_mana, default_city_zone_id
        )
        
        char_id = fetch_one("SELECT id FROM characters WHERE name = %s", name)[0]
        
        # Initialize character stats with race bonuses
        execute("""
            INSERT INTO character_stats (character_id, strength, dexterity, constitution, intelligence, wisdom, luck)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, char_id, char_class[2] + race[0], char_class[3] + race[1], char_class[4] + race[2], char_class[5] + race[3], char_class[6] + race[4], char_class[7] + race[5])
        
        # Give only first class base ability at level 1 (not the whole class tree).
        base_class_ability = fetch_one(
            """
            SELECT id
            FROM abilities
            WHERE class_id = %s AND level_requirement <= 1
            ORDER BY id ASC
            LIMIT 1
            """,
            class_id,
        )
        if base_class_ability:
            execute(
                "INSERT INTO character_abilities (character_id, ability_id, level) VALUES (%s, %s, 1) ON CONFLICT DO NOTHING",
                char_id,
                base_class_ability[0],
            )

        # Give one active race skill.
        race_name = fetch_val("SELECT name FROM races WHERE id = %s", race_id)
        class_name = fetch_val("SELECT name FROM character_classes WHERE id = %s", class_id)
        race_skill_name = f"{race_name}: Первый путь" if race_name else None
        if race_skill_name:
            race_skill_id = fetch_val("SELECT id FROM abilities WHERE name = %s LIMIT 1", race_skill_name)
            if race_skill_id:
                execute(
                    "INSERT INTO character_abilities (character_id, ability_id, level) VALUES (%s, %s, 1) ON CONFLICT DO NOTHING",
                    char_id,
                    int(race_skill_id),
                )

        # Give race-specific class starter attack from strict identity set.
        if race_name and class_name:
            race_class_skill_id = fetch_val(
                """
                SELECT id
                FROM abilities
                WHERE name LIKE %s
                ORDER BY level_requirement ASC, id ASC
                LIMIT 1
                """,
                f"{race_name} {class_name}: [ATK1]%",
            )
            if race_class_skill_id:
                execute(
                    "INSERT INTO character_abilities (character_id, ability_id, level) VALUES (%s, %s, 1) ON CONFLICT DO NOTHING",
                    char_id,
                    int(race_class_skill_id),
                )
        
        # Give race passive abilities
        race_abilities = fetch_all("SELECT ability_id FROM race_passive_abilities WHERE race_id = %s", race_id)
        for ability in race_abilities:
            execute("INSERT INTO character_abilities (character_id, ability_id, level) VALUES (%s, %s, 1)", char_id, ability[0])
        
        # Initialize skill coins and butchering skill
        execute("INSERT INTO skill_coins (character_id, balance, total_earned, total_spent) VALUES (%s, 0, 0, 0)", char_id)
        execute("INSERT INTO butchering_skill (character_id, skill_level, experience) VALUES (%s, 1, 0)", char_id)

        # Starter inventory pack for new characters.
        _ensure_starter_pack(char_id)
        
        return {
            "status": "success",
            "data": {
                "character": {
                    "id": char_id,
                    "name": name,
                    "race_id": race_id,
                    "class_id": class_id,
                    "level": 1,
                    "experience": 0,
                    "health_points": base_health,
                    "max_health_points": base_health
                }
            }
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Character creation failed")

@router.delete("/characters/{character_id}")
async def delete_character(character_id: int, current_user_id: int = Depends(get_current_user_id)):
    """Delete a character and all related data"""
    try:
        exists = fetch_one("SELECT id FROM characters WHERE id = %s", character_id)
        if not exists:
            raise HTTPException(status_code=404, detail="Character not found")

        ensure_character_owner(character_id, current_user_id)

        # Most related tables are configured with ON DELETE CASCADE.
        execute("DELETE FROM characters WHERE id = %s", character_id)
        
        return {"status": "success", "message": "Character deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Character deletion failed: {str(e)}"
        )

@router.get("/characters", response_model=dict)
async def list_characters(user_id: int, current_user_id: int = Depends(get_current_user_id)):
    """Get all characters for a user"""
    try:
        ensure_user_matches(user_id, current_user_id)

        characters = fetch_all(
            """
                 SELECT c.id, c.name, c.level, c.experience,
                     c.health_points, c.max_health_points,
                     c.mana_points AS magic_points,
                     c.max_mana_points AS max_magic_points,
                                         c.gold,
                                         COALESCE(c.silver, 0) AS silver,
                   COALESCE(r.name, 'Не выбрана') AS race_name,
                   COALESCE(cc.name, 'Не выбран') AS class_name
            FROM characters c
            LEFT JOIN races r ON r.id = c.race_id
            LEFT JOIN character_classes cc ON cc.id = c.class_id
            WHERE user_id = %s
            ORDER BY c.created_at DESC
            """,
            user_id
        )
        
        return {
            "count": len(characters),
            "characters": [
                {
                    "id": c[0],
                    "name": c[1],
                    "level": c[2],
                    "experience": c[3],
                    "health_points": c[4],
                    "max_health_points": c[5],
                    "magic_points": c[6],
                    "max_magic_points": c[7],
                    "gold": c[8],
                    "silver": c[9],
                    "race_name": c[10],
                    "class_name": c[11]
                }
                for c in characters
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/characters/{character_id}/inventory", response_model=dict)
async def get_character_inventory(character_id: int, current_user_id: int = Depends(get_current_user_id)):
    """Get character inventory items and gold."""
    try:
        ensure_character_owner(character_id, current_user_id)

        char_row = fetch_one(
            "SELECT id, gold, COALESCE(silver, 0) FROM characters WHERE id = %s",
            character_id
        )

        if not char_row:
            raise HTTPException(status_code=404, detail="Character not found")

        starter_granted = _ensure_starter_pack(character_id)

        item_rows = fetch_all(
            """
             SELECT i.id, i.name, i.item_type, i.rarity, i.value,
                 inv.quantity, inv.equipped, inv.slot,
                 COALESCE(i.description, ''),
                 COALESCE(i.damage_min, 0), COALESCE(i.damage_max, 0),
                 COALESCE(i.armor_class, 0), COALESCE(i.health_recovery, 0)
            FROM inventory inv
            JOIN items i ON i.id = inv.item_id
            WHERE inv.character_id = %s
            ORDER BY inv.equipped DESC, inv.created_at ASC
            """,
            character_id
        )

        return {
            "character_id": character_id,
            "gold": char_row[1] or 0,
            "silver": char_row[2] or 0,
            "starter_items_granted": starter_granted,
            "inventory": [
                {
                    "item_id": row[0],
                    "name": row[1],
                    "type": row[2],
                    "rarity": row[3],
                    "value": row[4],
                    "quantity": row[5],
                    "equipped": row[6],
                    "slot": _normalize_equipment_slot(row[7]),
                    "description": row[8],
                    "damage_min": row[9],
                    "damage_max": row[10],
                    "armor_class": row[11],
                    "health_recovery": row[12],
                }
                for row in item_rows
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/characters/{character_id}/inventory/equip", response_model=dict)
async def equip_inventory_item(
    character_id: int,
    payload: EquipItemModel,
    current_user_id: int = Depends(get_current_user_id),
):
    """Equip one item from backpack into its equipment slot."""
    try:
        ensure_character_owner(character_id, current_user_id)

        item = fetch_one(
            "SELECT id, name, item_type, COALESCE(description, '') FROM items WHERE id = %s",
            payload.item_id,
        )
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        slot = _resolve_equipment_slot(item[2])
        if not slot:
            raise HTTPException(status_code=400, detail="This item cannot be equipped")

        is_two_handed = _is_two_handed_item(item[2], item[1], item[3])

        resolved_slot = slot
        conflict_slots = [slot]
        if slot == "right_hand":
            conflict_slots = ["right_hand", "both_hands"]
            if is_two_handed:
                resolved_slot = "both_hands"
                conflict_slots = ["right_hand", "left_hand", "both_hands"]
        elif slot == "left_hand":
            conflict_slots = ["left_hand", "both_hands"]
        elif slot == "ring":
            left_ring = fetch_one(
                "SELECT id FROM inventory WHERE character_id = %s AND equipped = TRUE AND slot = 'ring_left' LIMIT 1",
                character_id,
            )
            right_ring = fetch_one(
                "SELECT id FROM inventory WHERE character_id = %s AND equipped = TRUE AND slot = 'ring_right' LIMIT 1",
                character_id,
            )
            if not left_ring:
                resolved_slot = "ring_left"
                conflict_slots = ["ring_left"]
            elif not right_ring:
                resolved_slot = "ring_right"
                conflict_slots = ["ring_right"]
            else:
                resolved_slot = "ring_left"
                conflict_slots = ["ring_left"]

        bag_row = fetch_one(
            """
            SELECT id, quantity
            FROM inventory
                        WHERE character_id = %s
                            AND item_id = %s
                            AND equipped = FALSE
                            AND COALESCE(slot, '') NOT IN ('right_hand', 'left_hand', 'both_hands', 'head', 'chest', 'legs', 'feet', 'ring_left', 'ring_right', 'main_hand', 'off_hand', 'body', 'torso')
            ORDER BY created_at ASC
            LIMIT 1
            """,
            character_id,
            payload.item_id,
        )
        if not bag_row or int(bag_row[1] or 0) <= 0:
            raise HTTPException(status_code=400, detail="Item is not in backpack")

        # Unequip conflicting equipped item(s), if any.
        expanded_conflict_slots = []
        for conflict_slot in conflict_slots:
            expanded_conflict_slots.extend(_slot_aliases_for_query(conflict_slot))

        current_equipped = fetch_all(
            "SELECT id, item_id FROM inventory WHERE character_id = %s AND equipped = TRUE AND slot = ANY(%s)",
            character_id,
            list(dict.fromkeys(expanded_conflict_slots)),
        )
        for equipped_row in current_equipped:
            _inventory_add(character_id, int(equipped_row[1]), 1)
            execute("DELETE FROM inventory WHERE id = %s", equipped_row[0])

        if int(bag_row[1]) > 1:
            execute("UPDATE inventory SET quantity = quantity - 1 WHERE id = %s", bag_row[0])
        else:
            execute("DELETE FROM inventory WHERE id = %s", bag_row[0])

        # Remove stale non-equipped rows with the same item/slot from legacy data.
        execute(
            "DELETE FROM inventory WHERE character_id = %s AND item_id = %s AND equipped = FALSE AND slot = %s",
            character_id,
            payload.item_id,
            resolved_slot,
        )

        execute(
            """
            INSERT INTO inventory (character_id, item_id, quantity, equipped, slot)
            VALUES (%s, %s, 1, TRUE, %s)
            """,
            character_id,
            payload.item_id,
            resolved_slot,
        )

        return {
            "status": "equipped",
            "slot": resolved_slot,
            "item_id": payload.item_id,
            "two_handed": is_two_handed,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/characters/{character_id}/inventory/unequip", response_model=dict)
async def unequip_inventory_item(
    character_id: int,
    payload: UnequipItemModel,
    current_user_id: int = Depends(get_current_user_id),
):
    """Unequip item from slot back to backpack."""
    try:
        ensure_character_owner(character_id, current_user_id)

        normalized_slot = (payload.slot or "").strip().lower()
        if normalized_slot in {"right_hand", "left_hand"}:
            aliases = _slot_aliases_for_query(normalized_slot)
            equipped_row = fetch_one(
                "SELECT id, item_id FROM inventory WHERE character_id = %s AND equipped = TRUE AND slot = ANY(%s) LIMIT 1",
                character_id,
                aliases + ["both_hands"],
            )
        else:
            aliases = _slot_aliases_for_query(normalized_slot)
            equipped_row = fetch_one(
                "SELECT id, item_id FROM inventory WHERE character_id = %s AND equipped = TRUE AND slot = ANY(%s) LIMIT 1",
                character_id,
                aliases,
            )
        if not equipped_row:
            raise HTTPException(status_code=404, detail="No equipped item in this slot")

        _inventory_add(character_id, int(equipped_row[1]), 1)
        execute("DELETE FROM inventory WHERE id = %s", equipped_row[0])
        return {"status": "unequipped", "slot": normalized_slot}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/characters/{character_id}/starter-items/ensure", response_model=dict)
async def ensure_character_starter_items(character_id: int, current_user_id: int = Depends(get_current_user_id)):
    """Manual endpoint to backfill starter items if missing."""
    try:
        ensure_character_owner(character_id, current_user_id)
        exists = fetch_one("SELECT id FROM characters WHERE id = %s", character_id)
        if not exists:
            raise HTTPException(status_code=404, detail="Character not found")
        granted = _ensure_starter_pack(character_id)
        return {"status": "success", "granted": granted}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===== Players (online) =====
@router.get("/players/online_count", response_model=dict)
async def get_online_players_count():
    """Return number of online characters (simple metric)"""
    try:
        count = fetch_val("SELECT COUNT(*) FROM characters WHERE is_online = TRUE") or 0
        return {"count": int(count)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth/logout", response_model=dict)
async def logout(user_id: int = None, current_user_id: int = Depends(get_current_user_id)):
    """Mark user's characters as offline (MVP)"""
    try:
        target_user_id = user_id or current_user_id
        ensure_user_matches(target_user_id, current_user_id)
        execute("UPDATE characters SET is_online = FALSE WHERE user_id = %s", target_user_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===== Locations =====
@router.get("/locations/{location_id}", response_model=dict)
async def get_location(location_id: int):
    """Get location details with objects (EVE Online style)"""
    try:
        location = fetch_one(
            "SELECT id, name, description, location_type, danger_level FROM locations WHERE id = %s",
            location_id
        )
        
        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Location not found"
            )
        
        # Get all objects in location
        objects = fetch_all(
            """
            SELECT id, object_type, name, distance_km, interaction_type
            FROM location_objects WHERE location_id = %s
            ORDER BY distance_km ASC
            """,
            location_id
        )
        
        return {
            "id": location[0],
            "name": location[1],
            "description": location[2],
            "type": location[3],
            "danger_level": location[4],
            "objects": [
                {
                    "id": obj[0],
                    "type": obj[1],
                    "name": obj[2],
                    "distance_km": obj[3],
                    "interaction": obj[4]
                }
                for obj in objects
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/locations", response_model=dict)
async def list_locations():
    """Get all available locations"""
    try:
        locations = fetch_all(
            """
            SELECT id, name, description, location_type, danger_level, capacity
            FROM locations
            WHERE name IN ('Изумрудные леса Лирана', 'Туманные болота Моргрима', 'Пепельные земли Кхаргара')
            ORDER BY CASE name
                WHEN 'Изумрудные леса Лирана' THEN 1
                WHEN 'Туманные болота Моргрима' THEN 2
                WHEN 'Пепельные земли Кхаргара' THEN 3
                ELSE 99
            END
            """
        )

        if not locations:
            locations = fetch_all(
                "SELECT id, name, description, location_type, danger_level, capacity FROM locations ORDER BY id"
            )
        
        return {
            "count": len(locations),
            "locations": [
                {
                    "id": loc[0],
                    "name": loc[1],
                    "description": loc[2],
                    "type": loc[3],
                    "danger_level": loc[4],
                    "capacity": loc[5]
                }
                for loc in locations
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# ===== World (current location & movement) =====
@router.get("/world/current", response_model=dict)
async def world_current(character_id: int, current_user_id: int = Depends(get_current_user_id)):
    """Get current location for character with objects"""
    try:
        ensure_character_owner(character_id, current_user_id)

        # Ensure character has a location (default to Элдория - location_id 1)
        char_location = fetch_one(
            "SELECT current_location_id, current_zone_id, position_x, position_y, COALESCE(position_z, 0) FROM characters WHERE id = %s",
            character_id
        )
        
        if not char_location or char_location[0] is None:
            default_zone = fetch_one(
                """
                SELECT id
                FROM mob_spawn_zones
                WHERE location_id = 1
                ORDER BY
                    CASE WHEN zone_name = 'Город новичков Аурис' THEN 0 ELSE 1 END,
                    CASE WHEN zone_type = 'city' THEN 0 ELSE 1 END,
                    id
                LIMIT 1
                """
            )
            default_zone_id = int(default_zone[0]) if default_zone else None
            execute(
                "UPDATE characters SET current_location_id = 1, current_zone_id = %s, position_x = 0, position_y = 0, position_z = 0 WHERE id = %s",
                default_zone_id,
                character_id,
            )
            location_id = 1
            active_subzone_id = default_zone_id
            pos_x, pos_y, pos_z = 0, 0, 0
        else:
            location_id = char_location[0]
            active_subzone_id = char_location[1]
            pos_x = float(char_location[2] or 0)
            pos_y = float(char_location[3] or 0)
            pos_z = float(char_location[4] or 0)
        
        # Get location info
        loc = fetch_one(
            "SELECT id, name, description, location_type, danger_level FROM locations WHERE id = %s",
            location_id
        )
        
        if not loc:
            raise HTTPException(status_code=404, detail="Location not found")
        
        active_zone = None
        if active_subzone_id:
            active_zone = fetch_one("SELECT zone_name, zone_type FROM mob_spawn_zones WHERE id = %s", active_subzone_id)

        return {
            "location": {
                "id": loc[0],
                "name": loc[1],
                "description": loc[2],
                "type": loc[3],
                "danger_level": loc[4],
            },
            "zone": {
                "id": active_subzone_id,
                "name": active_zone[0] if active_zone else None,
                "type": active_zone[1] if active_zone else None,
            },
            "area": {
                "id": active_subzone_id,
                "name": active_zone[0] if active_zone else None,
                "type": active_zone[1] if active_zone else None,
                "kind": "subzone",
            },
            "character_position": {"x": pos_x, "y": pos_y, "z": pos_z},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/world/mobs", response_model=dict)
async def get_mobs_in_location(character_id: int, current_user_id: int = Depends(get_current_user_id)):
    """Get mobs in character's current location"""
    try:
        ensure_character_owner(character_id, current_user_id)

        # Get current location
        location_row = fetch_one(
            "SELECT current_location_id, current_zone_id FROM characters WHERE id = %s",
            character_id
        )
        if not location_row or not location_row[0]:
            # Default to Элдория
            default_zone = fetch_one(
                """
                SELECT id
                FROM mob_spawn_zones
                WHERE location_id = 1
                ORDER BY
                    CASE WHEN zone_name = 'Город новичков Аурис' THEN 0 ELSE 1 END,
                    CASE WHEN zone_type = 'city' THEN 0 ELSE 1 END,
                    id
                LIMIT 1
                """
            )
            default_zone_id = int(default_zone[0]) if default_zone else None
            execute("UPDATE characters SET current_location_id = 1, current_zone_id = %s, position_z = COALESCE(position_z, 0) WHERE id = %s", default_zone_id, character_id)
            location_id = 1
            zone_id = default_zone_id
        else:
            location_id = location_row[0]
            zone_id = location_row[1]
        
        # Mobs are shown for the currently entered zone only.
        mobs = []
        if zone_id:
            restore_zone_if_fully_dead(int(zone_id))
            zone_name_row = fetch_one("SELECT zone_name FROM mob_spawn_zones WHERE id = %s", zone_id)
            zone_name = str(zone_name_row[0] if zone_name_row else "")
            is_fox_forest = "лисий лес" in zone_name.lower()

            mobs = get_zone_mob_entries(int(zone_id), int(location_id))
            if is_fox_forest:
                mobs = _filter_fox_forest_mobs(mobs)
        
        return {
            "mobs": mobs,
            "location_id": location_id,
            "zone_id": zone_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/world/objects", response_model=dict)
async def get_visible_world_objects(character_id: int, current_user_id: int = Depends(get_current_user_id)):
    """Get all visible objects in the zone (characters within 300m, buildings and NPCs in zone)"""
    try:
        ensure_character_owner(character_id, current_user_id)

        # Get current location
        location_row = fetch_one(
            "SELECT current_location_id FROM player_status WHERE character_id = %s",
            character_id
        )
        if not location_row:
            raise HTTPException(status_code=404, detail="Character not found")
        location_id = location_row[0]
        
        # Get all characters in the same location (assuming zone = location for now)
        # For characters within 300m, we'd need coordinates, but for MVP, get all in location
        characters = fetch_all(
            """
            SELECT c.id, c.name, 'character' as type, 0 as distance_m
            FROM characters c
            JOIN player_status ps ON ps.character_id = c.id
            WHERE ps.current_location_id = %s AND c.id != %s
            """,
            location_id, character_id
        )
        
        # Get all buildings and NPCs in the location
        objects = fetch_all(
            """
            SELECT id, object_type, name, COALESCE(distance_km * 1000, 0) as distance_m, interaction_type
            FROM location_objects 
            WHERE location_id = %s AND object_type IN ('building', 'npc')
            ORDER BY distance_m ASC, id ASC
            """,
            location_id
        )
        
        # Combine and filter characters within 300m (for now all in location)
        visible_objects = []
        
        # Add characters (all in location, assume within 300m)
        for char in characters:
            visible_objects.append({
                "id": char[0],
                "name": char[1],
                "type": char[2],
                "distance_m": char[3],
                "interaction": "talk"  # or whatever
            })
        
        # Add buildings and NPCs
        for obj in objects:
            visible_objects.append({
                "id": obj[0],
                "name": obj[2],
                "type": obj[1],
                "distance_m": obj[3],
                "interaction": obj[4]
            })
        
        return {
            "objects": visible_objects,
            "zone_id": location_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/world/move", response_model=dict)
async def world_move(character_id: int, location_id: int):
    """Move character to another location (MVP: no range/requirements checks)"""
    try:
        loc = fetch_one("SELECT id, name FROM locations WHERE id = %s", location_id)
        if not loc:
            raise HTTPException(status_code=404, detail="Location not found")
        # Upsert player_status
        execute(
            """
            INSERT INTO player_status (character_id, current_location_id, status_type)
            VALUES (%s, %s, 'idle')
            ON CONFLICT (character_id)
            DO UPDATE SET current_location_id = EXCLUDED.current_location_id, updated_at = CURRENT_TIMESTAMP
            """,
            character_id, location_id
        )
        return {"status": "success", "moved_to": {"id": loc[0], "name": loc[1]}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===== Combat (STUB) =====
@router.post("/combat/attack", response_model=dict)
async def attack_target(attacker_id: int, defender_id: int, target_type: str = "player"):
    """
    Initiate combat attack
    target_type: "player" or "npc"
    
    Combat mechanics from Mortal Online:
    - Damage calculation: attacker strength + weapon damage vs defender armor + dexterity
    - Hit location: head, chest, legs, arms
    - Hit chance: affected by weapon skill and dexterity
    - Block/parry: can be triggered by defender
    """
    return {
        "status": "attack_initiated",
        "message": "Combat mechanics coming soon (MVP)"
    }

@router.post("/combat/block", response_model=dict)
async def block_attack(defender_id: int):
    """Block incoming attack (based on dexterity and shield/armor)"""
    return {
        "status": "blocked",
        "message": "Block mechanics coming soon (MVP)"
    }

@router.post("/combat/escape", response_model=dict)
async def escape_combat(character_id: int):
    """
    Attempt to escape from combat
    Success chance based on: character dexterity vs opponent strength and movement speed
    """
    return {
        "status": "escape_attempted",
        "message": "Escape mechanics coming soon (MVP)"
    }

# ===== Crafting (STUB) =====
@router.get("/crafting/recipes", response_model=dict)
async def get_recipes(character_id: int = None, current_user_id: int = Depends(get_current_user_id)):
    """Get available crafting recipes"""
    try:
        if character_id is not None:
            ensure_character_owner(character_id, current_user_id)

        recipes = fetch_all(
            """
            SELECT cr.id, cr.crafting_type, cr.result_item_id, cr.required_skill_level,
                   cr.crafting_time_seconds, cr.result_quantity, cr.required_materials,
                   cr.success_rate, i.name
            FROM crafting_recipes cr
            JOIN items i ON i.id = cr.result_item_id
            ORDER BY cr.required_skill_level, cr.id
            """
        )
        
        recipe_items = []
        for r in recipes:
            required_materials = json.loads(r[6]) if r[6] else []
            enriched_materials = []
            can_craft = True
            for mat in required_materials:
                item_id = int(mat.get("item_id", 0))
                required_qty = int(mat.get("quantity", 0))
                item_name = fetch_val("SELECT name FROM items WHERE id = %s", item_id) or f"item_{item_id}"
                have_qty = _inventory_count(character_id, item_id) if character_id is not None else None
                if character_id is not None and have_qty < required_qty:
                    can_craft = False
                enriched_materials.append(
                    {
                        "item_id": item_id,
                        "item_name": item_name,
                        "quantity": required_qty,
                        "have": have_qty,
                    }
                )

            recipe_items.append(
                {
                    "id": r[0],
                    "type": r[1],
                    "result_item_id": r[2],
                    "skill_level_required": r[3],
                    "crafting_time_seconds": r[4],
                    "result_quantity": r[5],
                    "required_materials": enriched_materials,
                    "success_rate": r[7],
                    "result_item_name": r[8],
                    "can_craft": can_craft if character_id is not None else None,
                }
            )

        return {
            "count": len(recipes),
            "recipes": recipe_items,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/crafting/craft", response_model=dict)
async def craft_item(character_id: int, recipe_id: int, current_user_id: int = Depends(get_current_user_id)):
    """
    Craft an item
    
    Mechanics:
    - Requires materials from inventory
    - Crafting time depends on intelligence and skill
    - Success rate based on skill level
    - Experience reward on completion
    """
    ensure_character_owner(character_id, current_user_id)

    recipe = fetch_one(
        """
        SELECT cr.id, cr.result_item_id, cr.result_quantity, cr.required_skill_level,
               cr.required_materials, cr.success_rate, i.name
        FROM crafting_recipes cr
        JOIN items i ON i.id = cr.result_item_id
        WHERE cr.id = %s
        """,
        recipe_id,
    )
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    materials = json.loads(recipe[4]) if recipe[4] else []
    if not isinstance(materials, list):
        raise HTTPException(status_code=500, detail="Recipe materials are malformed")

    missing = []
    for mat in materials:
        item_id = int(mat.get("item_id", 0))
        needed_qty = int(mat.get("quantity", 0))
        if item_id <= 0 or needed_qty <= 0:
            continue
        have_qty = _inventory_count(character_id, item_id)
        if have_qty < needed_qty:
            item_name = fetch_val("SELECT name FROM items WHERE id = %s", item_id) or f"item_{item_id}"
            missing.append({"item_id": item_id, "item_name": item_name, "required": needed_qty, "have": have_qty})

    if missing:
        return {"status": "missing_materials", "missing": missing}

    for mat in materials:
        item_id = int(mat.get("item_id", 0))
        needed_qty = int(mat.get("quantity", 0))
        if item_id > 0 and needed_qty > 0:
            _inventory_remove(character_id, item_id, needed_qty)

    success_rate = max(1, min(100, int(recipe[5] or 100)))
    is_success = (random.random() * 100) <= success_rate

    crafted_qty = int(recipe[2] or 1) if is_success else 0
    bonus_proc = False
    if is_success and random.random() < 0.12:
        crafted_qty += 1
        bonus_proc = True

    if crafted_qty > 0:
        _inventory_add(character_id, int(recipe[1]), crafted_qty)

    crafting_record = fetch_one(
        "SELECT id FROM character_crafting WHERE character_id = %s AND recipe_id = %s",
        character_id,
        recipe_id,
    )
    if crafting_record:
        execute(
            "UPDATE character_crafting SET items_crafted = items_crafted + %s, last_crafted_at = CURRENT_TIMESTAMP WHERE id = %s",
            crafted_qty,
            crafting_record[0],
        )
    else:
        execute(
            "INSERT INTO character_crafting (character_id, recipe_id, skill_level, items_crafted, last_crafted_at) VALUES (%s, %s, 1, %s, CURRENT_TIMESTAMP)",
            character_id,
            recipe_id,
            crafted_qty,
        )

    return {
        "status": "crafted" if is_success else "craft_failed",
        "recipe_id": recipe_id,
        "success_rate": success_rate,
        "result_item_id": int(recipe[1]),
        "result_item_name": recipe[6],
        "result_quantity": crafted_qty,
        "bonus_proc": bonus_proc,
        "materials_spent": materials,
        "note": "Вдохновение мастера: иногда создается +1 предмет" if bonus_proc else "",
    }

# ===== Quests (STUB) =====
@router.get("/quests", response_model=dict)
async def get_quests(character_id: int):
    """Get available quests for character"""
    try:
        quests = fetch_all(
            """
            SELECT q.id, q.title, q.quest_type, q.level_requirement, q.reward_experience, q.reward_gold
            FROM quests q
            WHERE q.is_available = TRUE AND q.level_requirement <= (SELECT level FROM characters WHERE id = %s)
            """,
            character_id
        )
        
        return {
            "count": len(quests),
            "quests": [
                {
                    "id": q[0],
                    "title": q[1],
                    "type": q[2],
                    "level_required": q[3],
                    "reward_experience": q[4],
                    "reward_gold": q[5]
                }
                for q in quests
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/quests/accept", response_model=dict)
async def accept_quest(character_id: int, quest_id: int):
    """Accept a quest"""
    return {
        "status": "quest_accepted",
        "message": "Quest system coming soon (MVP)",
        "quest_id": quest_id
    }

# ===== Social =====
@router.get("/player/{user_id}/status", response_model=dict)
async def get_player_status(user_id: int):
    """Get player current status (location, activity, etc.)"""
    try:
        status = fetch_one(
            """
            SELECT ps.status_type, l.name, c.name
            FROM player_status ps
            JOIN locations l ON ps.current_location_id = l.id
            JOIN characters c ON ps.character_id = c.id
            WHERE c.user_id = %s
            """,
            user_id
        )
        
        if not status:
            return {"status": "offline"}
        
        return {
            "activity": status[0],
            "location": status[1],
            "character": status[2],
            "status": "online"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/chat/send", response_model=dict)
async def send_chat_message(sender_id: int, message: str, chat_type: str = "location"):
    """
    Send chat message
    chat_type: global, location, faction, private
    """
    return {
        "status": "message_sent",
        "chat_type": chat_type,
        "message": "Chat system coming soon (MVP)"
    }

# ===== QUESTS (Квесты) =====
@router.get("/quests/available", response_model=dict)
async def get_available_quests(location_id: int, character_id: int, current_user_id: int = Depends(get_current_user_id)):
    """Get available quests from NPCs in location"""
    try:
        ensure_character_owner(character_id, current_user_id)

        oren_npc_ids = fetch_all(
            "SELECT id FROM npcs WHERE location_id = %s AND LOWER(name) = LOWER(%s)",
            location_id,
            "Смотритель Равнин Орен",
        )
        for (oren_npc_id,) in oren_npc_ids:
            ensure_oren_daily_quests_for_npc(int(oren_npc_id))

        quests = fetch_all("""
            SELECT  q.id, q.title, q.description, q.quest_type, q.level_requirement, 
                   q.reward_experience, q.reward_gold, n.name as npc_name
            FROM quests q
            JOIN npcs n ON q.npc_id = n.id
            WHERE n.location_id = %s AND q.is_available = TRUE
        """, location_id)
        
        # Check which quests are already active for character
        active_quests = fetch_all(
            "SELECT quest_id FROM character_quests WHERE character_id = %s AND status = 'active'",
            character_id
        )
        active_quest_ids = [q[0] for q in active_quests]
        
        return {
            "quests": [
                {
                    "id": q[0],
                    "title": q[1],
                    "description": q[2],
                    "quest_type": q[3],
                    "level_requirement": q[4],
                    "reward_experience": q[5],
                    "reward_gold": q[6],
                    "npc_name": q[7],
                    "is_active": q[0] in active_quest_ids
                } for q in quests
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/quests/{quest_id}/accept", response_model=dict)
async def accept_quest(quest_id: int, character_id: int, current_user_id: int = Depends(get_current_user_id)):
    """Accept a quest"""
    try:
        ensure_character_owner(character_id, current_user_id)

        quest_exists = fetch_one("SELECT id FROM quests WHERE id = %s AND is_available = TRUE", quest_id)
        if not quest_exists:
            raise HTTPException(status_code=404, detail="Quest not found")

        # Check if already active
        existing = fetch_one(
            "SELECT id FROM character_quests WHERE character_id = %s AND quest_id = %s AND status = 'active'",
            character_id, quest_id
        )
        if existing:
            return {"status": "already_active", "message": "This quest is already active"}
        
        # Block duplicate rewards for already completed quests.
        done = fetch_one(
            "SELECT id FROM character_quests WHERE character_id = %s AND quest_id = %s AND status = 'completed'",
            character_id,
            quest_id,
        )
        if done:
            return {"status": "already_completed", "message": "Quest already completed"}

        # Add quest to character
        execute(
            "INSERT INTO character_quests (character_id, quest_id, status, progress_data) VALUES (%s, %s, 'active', '{}')",
            character_id, quest_id
        )
        
        return {"status": "quest_accepted", "quest_id": quest_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/quests/{character_id}/active", response_model=dict)
async def get_active_quests(character_id: int, current_user_id: int = Depends(get_current_user_id)):
    """Get active quests for character"""
    try:
        ensure_character_owner(character_id, current_user_id)

        quests = fetch_all("""
            SELECT cq.id, q.id, q.title, q.description, q.quest_type, q.reward_experience, q.reward_gold,
                   cq.status, cq.progress_data
            FROM character_quests cq
            JOIN quests q ON cq.quest_id = q.id
            WHERE cq.character_id = %s AND cq.status = 'active'
        """, character_id)
        
        result_quests = []
        for q in quests:
            # Get kill targets for this quest
            targets = fetch_all("""
                SELECT qkt.mob_id, m.name, qkt.required_count
                FROM quest_kill_targets qkt
                JOIN mobs m ON qkt.mob_id = m.id
                WHERE qkt.quest_id = %s
            """, q[1])
            
            quest_data = {
                "character_quest_id": q[0],
                "quest_id": q[1],
                "title": q[2],
                "description": q[3],
                "quest_type": q[4],
                "reward_experience": q[5],
                "reward_gold": q[6],
                "status": q[7],
                "kill_targets": [
                    {"mob_id": t[0], "mob_name": t[1], "required_count": t[2]}
                    for t in targets
                ]
            }
            result_quests.append(quest_data)
        
        return {"quests": result_quests, "count": len(result_quests)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/quests/{character_id}/kill", response_model=dict)
async def report_kill(character_id: int, quest_id: int, mob_id: int, current_user_id: int = Depends(get_current_user_id)):
    """Report killing a mob for quest"""
    try:
        ensure_character_owner(character_id, current_user_id)

        active = fetch_one(
            "SELECT id FROM character_quests WHERE character_id = %s AND quest_id = %s AND status = 'active'",
            character_id,
            quest_id,
        )
        if not active:
            raise HTTPException(status_code=400, detail="Quest is not active")

        target = fetch_one(
            "SELECT id FROM quest_kill_targets WHERE quest_id = %s AND mob_id = %s",
            quest_id,
            mob_id,
        )
        if not target:
            raise HTTPException(status_code=400, detail="Mob is not a target for this quest")

        # Update kill count
        existing = fetch_one(
            "SELECT id, kill_count FROM character_quest_kills WHERE character_id = %s AND quest_id = %s AND mob_id = %s",
            character_id, quest_id, mob_id
        )
        
        if existing:
            execute(
                "UPDATE character_quest_kills SET kill_count = kill_count + 1 WHERE id = %s",
                existing[0]
            )
            new_count = existing[1] + 1
        else:
            execute(
                "INSERT INTO character_quest_kills (character_id, quest_id, mob_id, kill_count) VALUES (%s, %s, %s, 1)",
                character_id, quest_id, mob_id
            )
            new_count = 1
        
        return {"status": "kill_reported", "new_count": new_count}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/quests/{character_id}/collect", response_model=dict)
async def report_item_collection(
    character_id: int,
    quest_id: int,
    item_id: int,
    quantity: int = 1,
    current_user_id: int = Depends(get_current_user_id),
):
    """Report collecting an item for quest (e.g., stones, bones, skins, etc.)"""
    try:
        ensure_character_owner(character_id, current_user_id)

        import json
        
        # Get current quest progress
        cq = fetch_one(
            "SELECT id, progress_data FROM character_quests WHERE character_id = %s AND quest_id = %s AND status = 'active'",
            character_id, quest_id
        )
        
        if not cq:
            raise HTTPException(status_code=400, detail="Quest not active")
        
        # Parse progress data
        try:
            progress = json.loads(cq[1]) if cq[1] else {}
        except:
            progress = {}
        
        # Initialize collected items dict if not exists
        if 'collected_items' not in progress:
            progress['collected_items'] = {}
        
        item_key = str(item_id)
        if item_key not in progress['collected_items']:
            progress['collected_items'][item_key] = 0
        
        progress['collected_items'][item_key] += quantity
        
        # Update progress
        execute(
            "UPDATE character_quests SET progress_data = %s WHERE id = %s",
            json.dumps(progress), cq[0]
        )
        
        return {
            "status": "item_collected",
            "item_id": item_id,
            "current_count": progress['collected_items'][item_key]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/quests/{character_id}/{quest_id}/progress", response_model=dict)
async def get_quest_progress(character_id: int, quest_id: int, current_user_id: int = Depends(get_current_user_id)):
    """Get detailed progress for a quest"""
    try:
        ensure_character_owner(character_id, current_user_id)

        import json
        
        # Get quest and progress
        cq = fetch_one(
            """SELECT cq.id, q.quest_type, cq.progress_data, q.description
            FROM character_quests cq
            JOIN quests q ON cq.quest_id = q.id
            WHERE cq.character_id = %s AND cq.quest_id = %s AND cq.status = 'active'
            """, character_id, quest_id
        )
        
        if not cq:
            raise HTTPException(status_code=404, detail="Quest not found or not active")
        
        quest_type = cq[1]
        progress_data = json.loads(cq[2]) if cq[2] else {}
        
        result = {
            "quest_id": quest_id,
            "quest_type": quest_type,
            "description": cq[3],
            "progress": {}
        }
        
        if quest_type == 'kill':
            # Get kill targets
            targets = fetch_all("""
                SELECT qkt.mob_id, m.name, qkt.required_count
                FROM quest_kill_targets qkt
                JOIN mobs m ON qkt.mob_id = m.id
                WHERE qkt.quest_id = %s
            """, quest_id)
            
            kill_progress = []
            for target_mob_id, mob_name, required in targets:
                # Get current kills for this mob
                kill_count = fetch_val(
                    "SELECT COALESCE(kill_count, 0) FROM character_quest_kills WHERE character_id = %s AND quest_id = %s AND mob_id = %s",
                    character_id, quest_id, target_mob_id
                ) or 0
                
                kill_progress.append({
                    "mob_id": target_mob_id,
                    "mob_name": mob_name,
                    "killed": kill_count,
                    "required": required,
                    "completed": kill_count >= required
                })
            
            result["progress"] = kill_progress
            result["all_completed"] = all(p["completed"] for p in kill_progress)
        
        elif quest_type == 'collect':
            # For collect quests, we need to check what items the quest requires
            # Parse from description or create a generic collection tracker
            collected_items = progress_data.get('collected_items', {})
            
            # Try to determine required items from collected count
            result["progress"] = {
                "collected_items": collected_items,
                "raw_data": progress_data
            }
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/quests/{character_id}/complete", response_model=dict)
async def complete_quest(character_id: int, quest_id: int, current_user_id: int = Depends(get_current_user_id)):
    """Complete a quest and get rewards"""
    try:
        ensure_character_owner(character_id, current_user_id)

        quest_state = fetch_one(
            "SELECT status FROM character_quests WHERE character_id = %s AND quest_id = %s",
            character_id,
            quest_id,
        )
        if not quest_state:
            raise HTTPException(status_code=404, detail="Quest is not accepted")
        if quest_state[0] != 'active':
            raise HTTPException(status_code=400, detail="Quest is not active")

        # Get quest details
        quest = fetch_one(
            """SELECT reward_experience, reward_gold, quest_type, level_requirement, reward_item_id, completion_condition FROM quests WHERE id = %s""",
            quest_id
        )
        
        if not quest:
            raise HTTPException(status_code=404, detail="Quest not found")
        
        # Validate completion conditions for kill quests.
        if quest[2] == 'kill':
            pending = fetch_val(
                """
                SELECT COUNT(*)
                FROM quest_kill_targets qkt
                LEFT JOIN character_quest_kills cqk
                    ON cqk.quest_id = qkt.quest_id
                    AND cqk.mob_id = qkt.mob_id
                    AND cqk.character_id = %s
                WHERE qkt.quest_id = %s
                    AND COALESCE(cqk.kill_count, 0) < qkt.required_count
                """,
                character_id,
                quest_id,
            )
            if (pending or 0) > 0:
                raise HTTPException(status_code=400, detail="Quest objectives are not completed")

        if quest[2] == 'collect':
            required_item_id = None
            required_count = 0
            try:
                cond = json.loads(quest[5]) if quest[5] else {}
                required_item_id = int(cond.get('required_item_id') or 0)
                required_count = int(cond.get('required_count') or 0)
            except Exception:
                required_item_id = None
                required_count = 0

            if required_item_id and required_count > 0:
                progress_row = fetch_one(
                    "SELECT progress_data FROM character_quests WHERE character_id = %s AND quest_id = %s",
                    character_id,
                    quest_id,
                )
                progress = {}
                try:
                    progress = json.loads(progress_row[0]) if progress_row and progress_row[0] else {}
                except Exception:
                    progress = {}
                collected = int(((progress.get('collected_items') or {}).get(str(required_item_id)) or 0))
                if collected < required_count:
                    raise HTTPException(status_code=400, detail="Quest objectives are not completed")

                # Spend collected resources on turn-in.
                _inventory_remove(character_id, required_item_id, required_count)

        progression = apply_experience_and_level_up(character_id, int(quest[0] or 0), int(quest[1] or 0))

        reward_item_quantity = 1
        try:
            cond = json.loads(quest[5]) if quest[5] else {}
            reward_item_quantity = max(1, int(cond.get('reward_item_quantity') or 1))
        except Exception:
            reward_item_quantity = 1

        if quest[4]:
            _inventory_add(character_id, int(quest[4]), reward_item_quantity)
        
        # Add honor coins reward (1-5) based on quest complexity.
        coin_reward = _honor_reward_for_quest(int(quest[3] or 1), quest[2])
        existing_coins = fetch_one(
            "SELECT id FROM skill_coins WHERE character_id = %s",
            character_id
        )
        
        if existing_coins:
            execute(
                "UPDATE skill_coins SET balance = balance + %s, total_earned = total_earned + %s WHERE character_id = %s",
                coin_reward, coin_reward, character_id
            )
        else:
            execute(
                "INSERT INTO skill_coins (character_id, balance, total_earned) VALUES (%s, %s, %s)",
                character_id, coin_reward, coin_reward
            )

        execute(
            "INSERT INTO skill_coin_transactions (character_id, transaction_type, amount, source, description) VALUES (%s, 'earned', %s, %s, %s)",
            character_id,
            coin_reward,
            f"quest_{quest_id}",
            "Награда за завершение квеста",
        )
        
        # Mark quest as completed
        updated = execute(
            "UPDATE character_quests SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE character_id = %s AND quest_id = %s AND status = 'active'",
            character_id,
            quest_id,
        )
        if updated == 0:
            raise HTTPException(status_code=400, detail="Quest is not active")
        
        return {
            "status": "quest_completed",
            "experience_reward": quest[0],
            "gold_reward": quest[1],
            "reward_item_id": int(quest[4]) if quest[4] else None,
            "reward_item_quantity": reward_item_quantity if quest[4] else 0,
            "skill_coins_reward": coin_reward,
            "honor_points_reward": coin_reward,
            "new_level": progression["level"],
            "leveled_up": progression["leveled_up"]
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to complete quest")

# ===== NPCs (Информация о НПС и их квестах) =====
@router.get("/npcs/{npc_id}", response_model=dict)
async def get_npc_quests(npc_id: int, character_id: int):
    """Get NPC information and their available quests"""
    try:
        # Get NPC info
        npc = fetch_one("""
            SELECT id, name, type, level, description, location_id
            FROM npcs
            WHERE id = %s
        """, npc_id)
        
        if not npc:
            raise HTTPException(status_code=404, detail="NPC not found")
        
        # Get NPC's quests
        quests = fetch_all("""
            SELECT id, title, description, quest_type, level_requirement, reward_experience, reward_gold
            FROM quests
            WHERE npc_id = %s AND is_available = TRUE
        """, npc_id)
        
        # Check which quests are already active/completed for this character
        active_quests = fetch_all(
            "SELECT quest_id FROM character_quests WHERE character_id = %s AND (status = 'active' OR status = 'completed')",
            character_id
        )
        active_quest_ids = [q[0] for q in active_quests]
        
        # Check completed quests
        completed_quests = fetch_all(
            "SELECT quest_id FROM character_quests WHERE character_id = %s AND status = 'completed'",
            character_id
        )
        completed_quest_ids = [q[0] for q in completed_quests]
        
        quest_list = []
        for q in quests:
            # Get kill targets if it's a kill quest
            kill_targets = []
            if q[3] == 'kill':
                targets = fetch_all("""
                    SELECT mob_id, qkt.required_count, m.name
                    FROM quest_kill_targets qkt
                    JOIN mobs m ON qkt.mob_id = m.id
                    WHERE qkt.quest_id = %s
                """, q[0])
                kill_targets = [{"mob_id": t[0], "required_count": t[1], "mob_name": t[2]} for t in targets]
            
            quest_list.append({
                "id": q[0],
                "title": q[1],
                "description": q[2],
                "quest_type": q[3],
                "level_requirement": q[4],
                "reward_experience": q[5],
                "reward_gold": q[6],
                "is_active": q[0] in active_quest_ids,
                "is_completed": q[0] in completed_quest_ids,
                "kill_targets": kill_targets
            })
        
        return {
            "npc": {
                "id": npc[0],
                "name": npc[1],
                "type": npc[2],
                "level": npc[3],
                "description": npc[4],
                "location_id": npc[5]
            },
            "quests": quest_list,
            "quest_count": len(quest_list)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/npcs/location/{location_id}", response_model=dict)
async def get_location_npcs(location_id: int, character_id: int):
    """Get all NPCs with quests in a location"""
    try:
        npcs = fetch_all("""
            SELECT id, name, type, level, description
            FROM npcs
            WHERE location_id = %s AND has_quest = TRUE
            ORDER BY name
        """, location_id)
        
        npc_list = []
        for npc in npcs:
            # Get quest count for this NPC
            quest_count = fetch_val(
                "SELECT COUNT(*) FROM quests WHERE npc_id = %s AND is_available = TRUE",
                npc[0]
            ) or 0
            
            npc_list.append({
                "id": npc[0],
                "name": npc[1],
                "type": npc[2],
                "level": npc[3],
                "description": npc[4],
                "quest_count": quest_count
            })
        
        return {
            "location_id": location_id,
            "npcs": npc_list,
            "npc_count": len(npc_list)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===== CRAFTING & BUTCHERING (Разделка и крафт) =====
@router.post("/butchering/butcher_mob", response_model=dict)
async def butcher_mob(character_id: int, mob_id: int, current_user_id: int = Depends(get_current_user_id)):
    """Butcher a killed mob and gain loot"""
    try:
        ensure_character_owner(character_id, current_user_id)

        # Get mob loot table
        mob = fetch_one(
            "SELECT loot_table_id, health_points FROM mobs WHERE id = %s",
            mob_id
        )
        
        if not mob or not mob[0]:
            return {"status": "no_loot", "message": "This mob has no loot"}

        if int(mob[1] or 0) > 0:
            return {"status": "mob_alive", "message": "Mob must be defeated before butchering"}
        
        # Get loot items from table
        loot_items = fetch_all("""
            SELECT item_id, drop_chance, min_quantity, max_quantity
            FROM loot_items
            WHERE loot_table_id = %s
        """, mob[0])
        
        import random
        obtained_items = []
        
        for item_id, drop_chance, min_qty, max_qty in loot_items:
            if random.random() * 100 < drop_chance:
                quantity = random.randint(min_qty, max_qty)
                # Add to inventory
                execute("""
                    INSERT INTO mob_loot (character_id, mob_id, item_id, quantity, is_butchered)
                    VALUES (%s, %s, %s, %s, TRUE)
                """, character_id, mob_id, item_id, quantity)
                _inventory_add(character_id, item_id, quantity)
                
                # Get item name
                item = fetch_one("SELECT name FROM items WHERE id = %s", item_id)
                obtained_items.append({"item_id": item_id, "name": item[0], "quantity": quantity})
        
        # Gain butchering experience
        butchering = fetch_one(
            "SELECT id, skill_level, experience FROM butchering_skill WHERE character_id = %s",
            character_id
        )
        
        butchering_exp = 25  # Experience per butcher
        if butchering:
            execute(
                "UPDATE butchering_skill SET experience = experience + %s, items_butchered = items_butchered + 1 WHERE character_id = %s",
                butchering_exp, character_id
            )
        else:
            execute(
                "INSERT INTO butchering_skill (character_id, skill_level, experience, items_butchered) VALUES (%s, 1, %s, 1)",
                character_id, butchering_exp
            )
        
        return {
            "status": "butchered_success",
            "obtained_items": obtained_items,
            "butchering_exp": butchering_exp
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/butchering/{character_id}/skill", response_model=dict)
async def get_butchering_skill(character_id: int, current_user_id: int = Depends(get_current_user_id)):
    """Get character's butchering skill info"""
    try:
        ensure_character_owner(character_id, current_user_id)

        skill = fetch_one("""
            SELECT skill_level, experience, experience_next_level, items_butchered
            FROM butchering_skill
            WHERE character_id = %s
        """, character_id)
        
        if not skill:
            return {
                "skill_level": 0,
                "experience": 0,
                "experience_next_level": 100,
                "items_butchered": 0
            }
        
        return {
            "skill_level": skill[0],
            "experience": skill[1],
            "experience_next_level": skill[2],
            "items_butchered": skill[3]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/loot/starter-zone", response_model=dict)
async def get_starter_zone_loot_table():
    """Return starter-zone mobs and their configured loot tables."""
    try:
        rows = fetch_all(
            """
            SELECT m.id, m.name, m.level, m.location_id,
                   COALESCE(lt.name, 'Без таблицы лута') AS loot_table_name,
                   i.id AS item_id, i.name AS item_name,
                   li.drop_chance, li.min_quantity, li.max_quantity
            FROM mobs m
            LEFT JOIN loot_tables lt ON lt.id = m.loot_table_id
            LEFT JOIN loot_items li ON li.loot_table_id = lt.id
            LEFT JOIN items i ON i.id = li.item_id
            WHERE m.location_id IN (1, 2)
            ORDER BY m.location_id, m.level, m.name, i.name
            """
        )

        mobs = {}
        for row in rows:
            mob_id = row[0]
            if mob_id not in mobs:
                mobs[mob_id] = {
                    "mob_id": mob_id,
                    "mob_name": row[1],
                    "level": row[2],
                    "location_id": row[3],
                    "loot_table": row[4],
                    "loot_items": [],
                }
            if row[5] is not None:
                mobs[mob_id]["loot_items"].append(
                    {
                        "item_id": row[5],
                        "item_name": row[6],
                        "drop_chance": float(row[7]),
                        "min_quantity": row[8],
                        "max_quantity": row[9],
                    }
                )

        return {
            "count": len(mobs),
            "mobs": list(mobs.values()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===== HONOR COINS (Коины чести) =====
@router.get("/skill_coins/{character_id}", response_model=dict)
async def get_skill_coins(character_id: int, current_user_id: int = Depends(get_current_user_id)):
    """Get character honor coins balance."""
    try:
        ensure_character_owner(character_id, current_user_id)

        coins = fetch_one("""
            SELECT balance, total_earned, total_spent
            FROM skill_coins
            WHERE character_id = %s
        """, character_id)
        
        if not coins:
            # Initialize if not exists
            execute(
                "INSERT INTO skill_coins (character_id, balance, total_earned, total_spent) VALUES (%s, 0, 0, 0)",
                character_id
            )
            return {"balance": 0, "total_earned": 0, "total_spent": 0}
        
        return {
            "balance": coins[0],
            "honor_points": coins[0],
            "total_earned": coins[1],
            "total_spent": coins[2]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/abilities/{ability_id}/learn", response_model=dict)
async def learn_ability_with_coins(
    character_id: int,
    ability_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    """Learn an ability using honor points earned from quests."""
    try:
        ensure_character_owner(character_id, current_user_id)

        # Check if already learned in either tracking table or active abilities table.
        learned = fetch_one(
            "SELECT id FROM character_abilities WHERE character_id = %s AND ability_id = %s",
            character_id,
            ability_id,
        )
        if learned:
            return {"status": "already_learned", "message": "You already know this ability"}

        # Character data for constraints.
        char = fetch_one(
            """
            SELECT c.level, c.class_id, r.name, cc.name
            FROM characters c
            LEFT JOIN races r ON r.id = c.race_id
            LEFT JOIN character_classes cc ON cc.id = c.class_id
            WHERE c.id = %s
            """,
            character_id,
        )
        if not char:
            raise HTTPException(status_code=404, detail="Character not found")
        char_level, char_class_id, race_name, class_name = char

        ability = fetch_one(
            "SELECT id, name, class_id, level_requirement FROM abilities WHERE id = %s",
            ability_id
        )
        if not ability:
            raise HTTPException(status_code=404, detail="Ability not found")

        ability_name = ability[1] or ""
        ability_class_id = ability[2]

        # Basic class compatibility.
        if ability_class_id and char_class_id and int(ability_class_id) != int(char_class_id):
            raise HTTPException(status_code=400, detail="Ability belongs to another class")

        # Race/class unique compatibility by naming convention.
        if race_name and class_name:
            race_prefix = f"{race_name}:"
            race_class_prefix = f"{race_name} {class_name}:"
            if ":" in ability_name and not (
                ability_name.startswith(race_prefix) or ability_name.startswith(race_class_prefix)
            ):
                raise HTTPException(status_code=400, detail="Ability is not available for this race/class")

        cost = fetch_one(
            """
            SELECT skill_coin_cost, unlocked_at_level, COALESCE(required_completed_quests, 0)
            FROM ability_skill_coin_costs
            WHERE ability_id = %s
            """,
            ability_id,
        )
        default_required_level = int(ability[3] or 1)
        coin_cost = int(cost[0] or 10) if cost else 10
        required_level = int(cost[1] or default_required_level) if cost else default_required_level
        required_quests = int(cost[2] or 0) if cost else 0

        if int(char_level or 1) < required_level:
            return {"status": "low_level", "message": f"Character must be level {required_level}"}

        completed_quests = int(
            fetch_val(
                "SELECT COUNT(*) FROM character_quests WHERE character_id = %s AND status = 'completed'",
                character_id,
            )
            or 0
        )
        if completed_quests < required_quests:
            return {
                "status": "not_enough_quests",
                "message": f"Нужно завершить квестов: {required_quests}",
            }

        coins = fetch_one(
            "SELECT balance FROM skill_coins WHERE character_id = %s",
            character_id
        )

        if not coins or int(coins[0] or 0) < coin_cost:
            return {"status": "insufficient_coins", "message": "Not enough honor points"}

        # Deduct honor points.
        execute(
            "UPDATE skill_coins SET balance = balance - %s, total_spent = total_spent + %s WHERE character_id = %s",
            coin_cost, coin_cost, character_id
        )

        # Persist both as learned marker and active character ability.
        execute(
            "INSERT INTO character_learned_abilities (character_id, ability_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            character_id, ability_id
        )
        execute(
            "INSERT INTO character_abilities (character_id, ability_id, level, cooldown_remaining) VALUES (%s, %s, 1, 0) ON CONFLICT DO NOTHING",
            character_id,
            ability_id,
        )

        # Log transaction
        execute(
            "INSERT INTO skill_coin_transactions (character_id, transaction_type, amount, source, description) VALUES (%s, 'spent', %s, %s, 'Learned ability')",
            character_id, coin_cost, f"ability_{ability_id}"
        )

        new_balance = int(fetch_val("SELECT balance FROM skill_coins WHERE character_id = %s", character_id) or 0)

        return {
            "status": "ability_learned",
            "ability_id": ability_id,
            "ability_name": ability_name,
            "coins_spent": coin_cost,
            "honor_points_spent": coin_cost,
            "honor_points_balance": new_balance,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/abilities/{character_id}/purchasable", response_model=dict)
async def get_purchasable_abilities(character_id: int, current_user_id: int = Depends(get_current_user_id)):
    """Get race/class purchasable abilities for honor points."""
    try:
        ensure_character_owner(character_id, current_user_id)

        # Character context.
        char_data = fetch_one(
            """
            SELECT c.level, c.class_id, r.name, cc.name
            FROM characters c
            LEFT JOIN races r ON r.id = c.race_id
            LEFT JOIN character_classes cc ON cc.id = c.class_id
            WHERE c.id = %s
            """,
            character_id
        )
        if not char_data:
            raise HTTPException(status_code=404, detail="Character not found")
        level, class_id, race_name, class_name = char_data

        # Keep this endpoint centered on race+class identity skills.
        race_class_prefix = f"{race_name} {class_name}:" if race_name and class_name else ""
        race_prefix = f"{race_name}:" if race_name else ""

        learned_ids = {
            row[0]
            for row in fetch_all("SELECT ability_id FROM character_abilities WHERE character_id = %s", character_id)
        }

        coin_balance = int(fetch_val("SELECT COALESCE(balance, 0) FROM skill_coins WHERE character_id = %s", character_id) or 0)
        completed_quests = int(
            fetch_val(
                "SELECT COUNT(*) FROM character_quests WHERE character_id = %s AND status = 'completed'",
                character_id,
            )
            or 0
        )

        abilities = fetch_all("""
            SELECT a.id, a.name, a.description, a.class_id,
                COALESCE(ascc.skill_coin_cost, 10) AS cost,
                COALESCE(ascc.unlocked_at_level, a.level_requirement, 1) AS unlock_level,
                COALESCE(ascc.required_completed_quests, 0) AS req_quests
            FROM abilities a
            LEFT JOIN ability_skill_coin_costs ascc ON a.id = ascc.ability_id
            WHERE COALESCE(ascc.unlocked_at_level, a.level_requirement, 1) <= %s
            AND a.class_id = %s
            ORDER BY COALESCE(ascc.unlocked_at_level, a.level_requirement, 1) ASC,
               COALESCE(ascc.skill_coin_cost, 10) ASC,
               a.name ASC
        """, level, class_id)

        result = []
        role_tags = ("[ATK", "[DEF", "[REC]", "[ULT]")
        for a in abilities:
            ability_id, name, desc, ability_class_id, cost, unlock_level, req_quests = a
            if ability_id in learned_ids:
                continue
            # Race-class uniqueness filter.
            if race_class_prefix:
                if not (name.startswith(race_class_prefix) or name.startswith(race_prefix)):
                    continue
            if not any(tag in name for tag in role_tags):
                continue
            affordable = int(cost or 0) <= coin_balance
            quest_gate_ok = completed_quests >= int(req_quests or 0)
            result.append(
                {
                    "ability_id": ability_id,
                    "name": name,
                    "description": desc,
                    "skill_coin_cost": int(cost or 0),
                    "honor_points_cost": int(cost or 0),
                    "unlocked_at_level": int(unlock_level or 1),
                    "required_completed_quests": int(req_quests or 0),
                    "is_affordable": affordable,
                    "requirements_met": affordable and quest_gate_ok,
                    "is_race_class_unique": True,
                }
            )

        return {
            "balance": coin_balance,
            "honor_points": coin_balance,
            "completed_quests": completed_quests,
            "abilities": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/abilities/{character_id}/honor-shop", response_model=dict)
async def get_honor_shop(character_id: int, current_user_id: int = Depends(get_current_user_id)):
    """Alias for purchasable abilities endpoint (UI-friendly naming)."""
    return await get_purchasable_abilities(character_id, current_user_id)
