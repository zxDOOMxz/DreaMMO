"""
🎮 DreaMMO API Routes
Main game mechanics endpoints
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from database.connection import fetch_one, fetch_all, execute, fetch_val
from passlib.hash import bcrypt
from jose import jwt
from config import settings

# simple JWT util (for demo purposes)
SECRET_KEY = settings.JWT_SECRET
ALGORITHM = settings.JWT_ALGORITHM

# ===== Route Definitions =====
router = APIRouter(prefix="/api", tags=["game"])

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


@router.post("/auth/register", response_model=dict)
async def register(user: RegisterModel):
    """Create a new user account"""
    try:
        exists = fetch_one("SELECT id FROM users WHERE username = %s OR email = %s", user.username, user.email)
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username or email already registered"
            )
        hashed = bcrypt.hash(user.password)
        execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s,%s,%s)",
            user.username, user.email, hashed
        )
        return {"status": "success", "data": {"registered": True}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginModel):
    """Authenticate and return JWT token"""
    user_record = fetch_one("SELECT id, password_hash FROM users WHERE username = %s", payload.username)
    if not user_record or not bcrypt.verify(payload.password, user_record[1]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    user_id = user_record[0]
    token = jwt.encode({"sub": str(user_id)}, SECRET_KEY, algorithm=ALGORITHM)
    # Обновим last_login и пометим персонажей пользователя как online
    try:
        execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s", user_id)
        execute("UPDATE characters SET is_online = TRUE WHERE user_id = %s", user_id)
    except Exception:
        pass
    return TokenResponse(access_token=token)


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
                SELECT a.id, a.name, a.description
                FROM race_passive_abilities rpa
                JOIN abilities a ON rpa.ability_id = a.id
                WHERE rpa.race_id = %s
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
        classes = fetch_all("SELECT id, name, description, base_health, base_mana FROM character_classes ORDER BY id")
        return {
            "classes": [
                {
                    "id": c[0],
                    "name": c[1],
                    "description": c[2],
                    "base_health": c[3],
                    "base_mana": c[4]
                }
                for c in classes
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/characters/create", response_model=dict)
async def create_character(data: dict):
    """Create new character for player"""
    try:
        user_id = data.get('user_id')
        name = data.get('name')
        class_id = data.get('class_id')
        race_id = data.get('race_id')
        
        if not all([user_id, name, class_id, race_id]):
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        # Check if character name exists
        existing = fetch_one("SELECT id FROM characters WHERE name = %s", name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Character name already taken"
            )
        
        # Get race and class bonuses
        race = fetch_one("SELECT strength_bonus, dexterity_bonus, constitution_bonus, intelligence_bonus, wisdom_bonus, luck_bonus FROM races WHERE id = %s", race_id)
        char_class = fetch_one("SELECT base_health, base_mana FROM character_classes WHERE id = %s", class_id)
        
        if not race or not char_class:
            raise HTTPException(status_code=404, detail="Invalid race or class")
        
        # Create base stats with race bonuses
        base_health = char_class[0] + (race[2] * 5)  # constitution bonus affects health
        base_mana = char_class[1] + (race[3] * 3)    # intelligence bonus affects mana
        
        # Create character with spawn location set to Элдория (location_id = 1)
        execute(
            "INSERT INTO characters (user_id, name, race_id, class_id, level, experience, health_points, max_health_points, mana_points, max_mana_points, current_location_id, position_x, position_y) VALUES (%s, %s, %s, %s, 1, 0, %s, %s, %s, %s, 1, 0, 0)",
            user_id, name, race_id, class_id, base_health, base_health, base_mana, base_mana
        )
        
        char_id = fetch_one("SELECT id FROM characters WHERE name = %s", name)[0]
        
        # Initialize character stats with race bonuses
        execute("""
            INSERT INTO character_stats (character_id, strength, dexterity, constitution, intelligence, wisdom, luck)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, char_id, 10 + race[0], 10 + race[1], 10 + race[2], 10 + race[3], 10 + race[4], 10 + race[5])
        
        # Give class abilities
        abilities = fetch_all("SELECT id FROM abilities WHERE class_id = %s", class_id)
        for ability in abilities:
            execute("INSERT INTO character_abilities (character_id, ability_id, level) VALUES (%s, %s, 1)", char_id, ability[0])
        
        # Give race passive abilities
        race_abilities = fetch_all("SELECT ability_id FROM race_passive_abilities WHERE race_id = %s", race_id)
        for ability in race_abilities:
            execute("INSERT INTO character_abilities (character_id, ability_id, level) VALUES (%s, %s, 1)", char_id, ability[0])
        
        # Initialize skill coins and butchering skill
        execute("INSERT INTO skill_coins (character_id, balance, total_earned, total_spent) VALUES (%s, 0, 0, 0)", char_id)
        execute("INSERT INTO butchering_skill (character_id, skill_level, experience) VALUES (%s, 1, 0)", char_id)
        
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/characters/{character_id}")
async def delete_character(character_id: int):
    """Delete a character and all related data"""
    try:
        exists = fetch_one("SELECT id FROM characters WHERE id = %s", character_id)
        if not exists:
            raise HTTPException(status_code=404, detail="Character not found")

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
async def list_characters(user_id: int):
    """Get all characters for a user"""
    try:
        characters = fetch_all(
            """
            SELECT id, name, level, experience,
                   health_points, max_health_points,
                   mana_points AS magic_points,
                   max_mana_points AS max_magic_points,
                   gold
            FROM characters
            WHERE user_id = %s
            ORDER BY created_at DESC
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
                    "gold": c[8]
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
async def get_character_inventory(character_id: int):
    """Get character inventory items and gold."""
    try:
        char_row = fetch_one(
            "SELECT id, gold FROM characters WHERE id = %s",
            character_id
        )

        if not char_row:
            raise HTTPException(status_code=404, detail="Character not found")

        item_rows = fetch_all(
            """
            SELECT i.id, i.name, i.item_type, i.rarity, i.value,
                   inv.quantity, inv.equipped, inv.slot
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
            "inventory": [
                {
                    "item_id": row[0],
                    "name": row[1],
                    "type": row[2],
                    "rarity": row[3],
                    "value": row[4],
                    "quantity": row[5],
                    "equipped": row[6],
                    "slot": row[7]
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
async def logout(user_id: int):
    """Mark user's characters as offline (MVP)"""
    try:
        execute("UPDATE characters SET is_online = FALSE WHERE user_id = %s", user_id)
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
            "SELECT id, name, location_type, danger_level, capacity FROM locations ORDER BY name"
        )
        
        return {
            "count": len(locations),
            "locations": [
                {
                    "id": loc[0],
                    "name": loc[1],
                    "type": loc[2],
                    "danger_level": loc[3],
                    "capacity": loc[4]
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
async def world_current(character_id: int):
    """Get current location for character with objects"""
    try:
        # Ensure character has a location (default to Элдория - location_id 1)
        char_location = fetch_one(
            "SELECT current_location_id FROM characters WHERE id = %s",
            character_id
        )
        
        if not char_location or char_location[0] is None:
            execute("UPDATE characters SET current_location_id = 1, position_x = 0, position_y = 0 WHERE id = %s", character_id)
            location_id = 1
        else:
            location_id = char_location[0]
        
        # Get location info
        loc = fetch_one(
            "SELECT id, name, description, location_type, danger_level FROM locations WHERE id = %s",
            location_id
        )
        
        if not loc:
            raise HTTPException(status_code=404, detail="Location not found")
        
        return {
            "location": {
                "id": loc[0],
                "name": loc[1],
                "description": loc[2],
                "type": loc[3],
                "danger_level": loc[4],
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/world/mobs", response_model=dict)
async def get_mobs_in_location(character_id: int):
    """Get mobs in character's current location"""
    try:
        # Get current location
        location_row = fetch_one(
            "SELECT current_location_id FROM characters WHERE id = %s",
            character_id
        )
        if not location_row or not location_row[0]:
            # Default to Элдория
            execute("UPDATE characters SET current_location_id = 1 WHERE id = %s", character_id)
            location_id = 1
        else:
            location_id = location_row[0]
        
        # Get mobs in location
        mobs = fetch_all(
            """
            SELECT id, name, level, health_points, max_health_points, damage_min, damage_max, 
                   armor_class, experience_reward, gold_reward, mob_type, aggression_type
            FROM mobs 
            WHERE location_id = %s AND health_points > 0
            ORDER BY level ASC, name ASC
            """,
            location_id
        )
        
        return {
            "mobs": [
                {
                    "id": m[0],
                    "name": m[1],
                    "level": m[2],
                    "health": m[3],
                    "max_health": m[4],
                    "damage_min": m[5],
                    "damage_max": m[6],
                    "armor": m[7],
                    "exp_reward": m[8],
                    "gold_reward": m[9],
                    "type": m[10],
                    "aggression": m[11]
                }
                for m in mobs
            ],
            "location_id": location_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    """Get all visible objects in the zone (characters within 300m, buildings and NPCs in zone)"""
    try:
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
async def get_recipes():
    """Get available crafting recipes"""
    try:
        recipes = fetch_all(
            """
            SELECT id, crafting_type, result_item_id, required_skill_level, crafting_time_seconds
            FROM crafting_recipes
            """
        )
        
        return {
            "count": len(recipes),
            "recipes": [
                {
                    "id": r[0],
                    "type": r[1],
                    "result_item_id": r[2],
                    "skill_level_required": r[3],
                    "crafting_time_seconds": r[4]
                }
                for r in recipes
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/crafting/craft", response_model=dict)
async def craft_item(character_id: int, recipe_id: int):
    """
    Craft an item
    
    Mechanics:
    - Requires materials from inventory
    - Crafting time depends on intelligence and skill
    - Success rate based on skill level
    - Experience reward on completion
    """
    return {
        "status": "crafting_started",
        "message": "Crafting mechanics coming soon (MVP)",
        "recipe_id": recipe_id
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
async def get_available_quests(location_id: int, character_id: int):
    """Get available quests from NPCs in location"""
    try:
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
async def accept_quest(quest_id: int, character_id: int):
    """Accept a quest"""
    try:
        # Check if already active
        existing = fetch_one(
            "SELECT id FROM character_quests WHERE character_id = %s AND quest_id = %s AND status = 'active'",
            character_id, quest_id
        )
        if existing:
            return {"status": "already_active", "message": "This quest is already active"}
        
        # Add quest to character
        execute(
            "INSERT INTO character_quests (character_id, quest_id, status, progress_data) VALUES (%s, %s, 'active', '{}')",
            character_id, quest_id
        )
        
        return {"status": "quest_accepted", "quest_id": quest_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/quests/{character_id}/active", response_model=dict)
async def get_active_quests(character_id: int):
    """Get active quests for character"""
    try:
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
async def report_kill(character_id: int, quest_id: int, mob_id: int):
    """Report killing a mob for quest"""
    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/quests/{character_id}/collect", response_model=dict)
async def report_item_collection(character_id: int, quest_id: int, item_id: int, quantity: int = 1):
    """Report collecting an item for quest (e.g., stones, bones, skins, etc.)"""
    try:
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
async def get_quest_progress(character_id: int, quest_id: int):
    """Get detailed progress for a quest"""
    try:
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
async def complete_quest(character_id: int, quest_id: int):
    """Complete a quest and get rewards"""
    try:
        # Get quest details
        quest = fetch_one(
            """SELECT reward_experience, reward_gold FROM quests WHERE id = %s""",
            quest_id
        )
        
        if not quest:
            raise HTTPException(status_code=404, detail="Quest not found")
        
        # Update character stats
        execute(
            "UPDATE characters SET experience = experience + %s, gold = COALESCE(gold, 0) + %s WHERE id = %s",
            quest[0], quest[1], character_id
        )
        
        # Add skill coins reward
        coin_reward = max(10, quest[0] // 50)  # Based on experience reward
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
        
        # Mark quest as completed
        execute(
            "UPDATE character_quests SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE character_id = %s AND quest_id = %s",
            character_id, quest_id
        )
        
        return {
            "status": "quest_completed",
            "experience_reward": quest[0],
            "gold_reward": quest[1],
            "skill_coins_reward": coin_reward
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
async def butcher_mob(character_id: int, mob_id: int):
    """Butcher a killed mob and gain loot"""
    try:
        # Get mob loot table
        mob = fetch_one(
            "SELECT loot_table_id FROM mobs WHERE id = %s",
            mob_id
        )
        
        if not mob or not mob[0]:
            return {"status": "no_loot", "message": "This mob has no loot"}
        
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
async def get_butchering_skill(character_id: int):
    """Get character's butchering skill info"""
    try:
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

# ===== SKILL COINS (Коины умений) =====
@router.get("/skill_coins/{character_id}", response_model=dict)
async def get_skill_coins(character_id: int):
    """Get character's skill coins balance"""
    try:
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
            "total_earned": coins[1],
            "total_spent": coins[2]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/abilities/{ability_id}/learn", response_model=dict)
async def learn_ability_with_coins(character_id: int, ability_id: int):
    """Learn an ability using skill coins"""
    try:
        # Check if already learned
        learned = fetch_one(
            "SELECT id FROM character_learned_abilities WHERE character_id = %s AND ability_id = %s",
            character_id, ability_id
        )
        
        if learned:
            return {"status": "already_learned", "message": "You already know this ability"}
        
        # Get skill coin cost
        cost = fetch_one(
            """SELECT skill_coin_cost, unlocked_at_level FROM ability_skill_coin_costs 
               WHERE ability_id = %s""",
            ability_id
        )
        
        if not cost or cost[0] == 0:
            return {"status": "free_ability", "message": "This ability cannot be purchased"}
        
        coin_cost = cost[0]
        
        # Check character level
        character = fetch_one(
            "SELECT level FROM characters WHERE id = %s",
            character_id
        )
        
        if character[0] < cost[1]:
            return {"status": "low_level", "message": f"Character must be level {cost[1]}"}
        
        # Check balance
        coins = fetch_one(
            "SELECT balance FROM skill_coins WHERE character_id = %s",
            character_id
        )
        
        if not coins or coins[0] < coin_cost:
            return {"status": "insufficient_coins", "message": "Not enough skill coins"}
        
        # Deduct coins and add ability
        execute(
            "UPDATE skill_coins SET balance = balance - %s, total_spent = total_spent + %s WHERE character_id = %s",
            coin_cost, coin_cost, character_id
        )
        
        execute(
            "INSERT INTO character_learned_abilities (character_id, ability_id) VALUES (%s, %s)",
            character_id, ability_id
        )
        
        # Log transaction
        execute(
            "INSERT INTO skill_coin_transactions (character_id, transaction_type, amount, source, description) VALUES (%s, 'spent', %s, %s, 'Learned ability')",
            character_id, coin_cost, f"ability_{ability_id}"
        )
        
        return {
            "status": "ability_learned",
            "ability_id": ability_id,
            "coins_spent": coin_cost
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/abilities/{character_id}/purchasable", response_model=dict)
async def get_purchasable_abilities(character_id: int):
    """Get abilities that can be purchased with skill coins"""
    try:
        # Get character level and class
        char_data = fetch_one(
            "SELECT level, class_id FROM characters WHERE id = %s",
            character_id
        )
        
        # Get already learned abilities
        learned = fetch_all(
            "SELECT ability_id FROM character_learned_abilities WHERE character_id = %s",
            character_id
        )
        learned_ids = [a[0] for a in learned]
        
        # Get purchasable abilities
        abilities = fetch_all("""
            SELECT a.id, a.name, a.description, ascc.skill_coin_cost, ascc.unlocked_at_level
            FROM abilities a
            JOIN ability_skill_coin_costs ascc ON a.id = ascc.ability_id
            WHERE ascc.skill_coin_cost > 0 
            AND ascc.unlocked_at_level <= %s
            AND a.class_id = %s
            AND a.id NOT IN (SELECT ability_id FROM character_learned_abilities WHERE character_id = %s)
        """, char_data[0], char_data[1], character_id)
        
        return {
            "abilities": [
                {
                    "ability_id": a[0],
                    "name": a[1],
                    "description": a[2],
                    "skill_coin_cost": a[3],
                    "unlocked_at_level": a[4],
                    "is_affordable": a[3] <= fetch_one("SELECT balance FROM skill_coins WHERE character_id = %s", character_id)[0]
                } for a in abilities
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
