"""
Combat system routes with Lineage 2-style mechanics
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from database.connection import fetch_all, fetch_one, execute, fetch_val
from datetime import datetime
import random
import math
from security import ensure_character_owner, get_current_user_id
from progression import apply_experience_and_level_up
from mob_population import consume_mob_unit, fetch_zone_population_row, restore_zone_if_fully_dead

combat_router = APIRouter()

STAT_FIELDS = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "luck")


class StatAllocationRequest(BaseModel):
    strength: int = 0
    dexterity: int = 0
    constitution: int = 0
    intelligence: int = 0
    wisdom: int = 0
    luck: int = 0

# ===== COMBAT FORMULAS (Lineage 2 style) =====

def calculate_damage(attacker_stats, defender_stats, is_crit=False):
    """
    Calculate damage based on attacker and defender stats
    """
    # Base damage from strength
    base_damage = attacker_stats.get('damage_min', 5), attacker_stats.get('damage_max', 10)
    damage = random.randint(base_damage[0], base_damage[1])
    
    # Strength bonus (+1 damage per 2 strength above 10)
    strength = attacker_stats.get('strength', 10)
    strength_bonus = max(0, (strength - 10) / 2)
    damage += strength_bonus
    
    # Critical hit (based on luck)
    if is_crit:
        crit_multiplier = 1.5 + (attacker_stats.get('luck', 10) / 100)
        damage *= crit_multiplier
    
    # Armor reduction
    armor = defender_stats.get('armor_class', 0)
    damage_reduction = armor * 0.5  # Each armor point reduces 0.5 damage
    damage = max(1, damage - damage_reduction)
    
    return int(damage)


def calculate_hit_chance(attacker_dex, defender_dex):
    """
    Calculate chance to hit (based on dexterity)
    """
    base_chance = 85  # 85% base hit chance
    dex_diff = attacker_dex - defender_dex
    hit_chance = base_chance + (dex_diff * 0.5)
    return max(50, min(95, hit_chance))  # Clamp between 50-95%


def calculate_crit_chance(attacker_luck):
    """
    Calculate critical hit chance (based on luck)
    """
    base_crit = 5  # 5% base crit
    luck_bonus = (attacker_luck - 10) * 0.3
    return max(1, min(30, base_crit + luck_bonus))  # Clamp between 1-30%


def calculate_block_chance(defender_dex, defender_con):
    """
    Calculate block chance (based on dexterity and constitution)
    """
    base_block = 10  # 10% base block
    dex_bonus = (defender_dex - 10) * 0.2
    con_bonus = (defender_con - 10) * 0.1
    return max(0, min(40, base_block + dex_bonus + con_bonus))  # Clamp 0-40%


def calculate_attack_speed(base_speed, dexterity):
    """
    Calculate attack speed (attacks per minute)
    """
    dex_modifier = (dexterity - 10) * 0.05  # +5% per dex above 10
    speed = base_speed * (1 + dex_modifier)
    return max(30, min(120, speed))  # Clamp between 30-120 attacks/min


def get_exp_multiplier(character_level, mob_level):
    """
    Calculate experience multiplier based on level difference (Lineage 2 style)
    """
    level_diff = character_level - mob_level
    
    # Get rule from database
    rule = fetch_one("""
        SELECT exp_multiplier, gold_multiplier
        FROM exp_penalty_rules
        WHERE %s >= level_difference_min AND %s <= level_difference_max
    """, level_diff, level_diff)
    
    if rule:
        return rule[0], rule[1]  # exp_multiplier, gold_multiplier
    
    # Default: full XP if mob is same level or higher
    return 1.0, 1.0


def _is_humanoid_mob(mob_type: str) -> bool:
    normalized = (mob_type or "").strip().lower()
    humanoid_markers = (
        "human",
        "humanoid",
        "orc",
        "elf",
        "dwarf",
        "bandit",
        "goblin",
        "knight",
        "солдат",
        "бандит",
        "гуманоид",
    )
    return any(marker in normalized for marker in humanoid_markers)


def _resolve_death_territory(character_id: int) -> str:
    row = fetch_one(
        """
        SELECT c.current_location_id,
               COALESCE(l.is_pvp_enabled, FALSE),
               COALESCE(l.danger_level, 0),
               COALESCE(z.zone_type, '')
        FROM characters c
        LEFT JOIN locations l ON l.id = c.current_location_id
        LEFT JOIN mob_spawn_zones z ON z.id = c.current_zone_id
        WHERE c.id = %s
        """,
        character_id,
    )
    if not row:
        return "starter"

    location_id, is_pvp_enabled, danger_level, zone_type = row
    zone_type = (zone_type or "").strip().lower()

    if int(location_id or 0) == 1 or zone_type == "city" or (not is_pvp_enabled and int(danger_level or 0) <= 2):
        return "starter"
    if bool(is_pvp_enabled):
        return "pvp"
    return "neutral"


def _drop_inventory_on_death(character_id: int, territory: str) -> list[dict]:
    if territory == "starter":
        return []

    rows = fetch_all(
        """
        SELECT inv.id, inv.item_id, inv.quantity, i.name
        FROM inventory inv
        JOIN items i ON i.id = inv.item_id
        WHERE inv.character_id = %s
          AND COALESCE(inv.equipped, FALSE) = FALSE
          AND COALESCE(inv.quantity, 0) > 0
        ORDER BY inv.created_at ASC
        """,
        character_id,
    )
    if not rows:
        return []

    if territory == "pvp":
        selected = rows
    else:
        max_drop = min(2, len(rows))
        drop_count = random.randint(1, max_drop)
        selected = random.sample(rows, k=drop_count)

    dropped_items = []
    for inv_id, item_id, qty, item_name in selected:
        execute("DELETE FROM inventory WHERE id = %s", inv_id)
        dropped_items.append(
            {
                "item_id": int(item_id),
                "name": item_name,
                "quantity": int(qty or 0),
            }
        )

    return dropped_items


def _load_combat_stats_row(character_id: int):
    return fetch_one(
        """
        SELECT c.level,
               COALESCE(s.strength, 10),
               COALESCE(s.dexterity, 10),
               COALESCE(s.constitution, 10),
               COALESCE(s.intelligence, 10),
               COALESCE(s.wisdom, 10),
               COALESCE(s.luck, 10),
               COALESCE(s.available_stat_points, 0)
        FROM characters c
        LEFT JOIN character_stats s ON s.character_id = c.id
        WHERE c.id = %s
        """,
        character_id,
    )


def _build_combat_stats_response(character_id: int) -> dict:
    char = _load_combat_stats_row(character_id)
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    lvl, str_val, dex, con, int_val, wis, luck, available_stat_points = char

    equipped_bonus = fetch_one(
        """
        SELECT
            COALESCE(SUM(CASE WHEN inv.equipped = TRUE THEN i.armor_class ELSE 0 END), 0) AS armor_bonus,
            COALESCE(SUM(CASE WHEN inv.equipped = TRUE AND inv.slot IN ('right_hand', 'both_hands') THEN i.damage_min ELSE 0 END), 0) AS weapon_damage_min,
            COALESCE(SUM(CASE WHEN inv.equipped = TRUE AND inv.slot IN ('right_hand', 'both_hands') THEN i.damage_max ELSE 0 END), 0) AS weapon_damage_max
        FROM inventory inv
        JOIN items i ON i.id = inv.item_id
        WHERE inv.character_id = %s
        """,
        character_id,
    ) or (0, 0, 0)
    armor_bonus, weapon_damage_min, weapon_damage_max = equipped_bonus

    # Calculate all combat stats
    base_dmg_min = 5 + (str_val // 5) + int(weapon_damage_min or 0)
    base_dmg_max = 10 + (str_val // 3) + int(weapon_damage_max or 0)
    hit_chance = calculate_hit_chance(dex, 10)
    crit_chance = calculate_crit_chance(luck)
    block_chance = calculate_block_chance(dex, con)
    attack_speed = calculate_attack_speed(60, dex)  # Base 60 attacks/min
    armor_value = (con - 10) * 0.3 + float(armor_bonus or 0)

    return {
        "level": lvl,
        "available_stat_points": int(available_stat_points or 0),
        "stats": {
            "strength": str_val,
            "dexterity": dex,
            "constitution": con,
            "intelligence": int_val,
            "wisdom": wis,
            "luck": luck
        },
        "combat": {
            "damage_min": base_dmg_min,
            "damage_max": base_dmg_max,
            "hit_chance": round(hit_chance, 1),
            "crit_chance": round(crit_chance, 1),
            "block_chance": round(block_chance, 1),
            "attack_speed": round(attack_speed, 1),
            "armor_value": round(armor_value, 1),
            "equipment_armor_bonus": int(armor_bonus or 0),
            "equipment_weapon_damage_min": int(weapon_damage_min or 0),
            "equipment_weapon_damage_max": int(weapon_damage_max or 0),
        }
    }


def _is_tank_class(class_name: str) -> bool:
    normalized = (class_name or "").strip().lower()
    return "танк" in normalized or "tank" in normalized


def _resolve_aggro_target(mob_id: int, attacker_id: int, attacker_is_tank: bool) -> tuple[int, str]:
    if attacker_is_tank:
        execute(
            """
            INSERT INTO mob_aggro_targets (mob_id, target_character_id, aggro_mode, updated_at)
            VALUES (%s, %s, 'tank', CURRENT_TIMESTAMP)
            ON CONFLICT (mob_id) DO UPDATE SET
                target_character_id = EXCLUDED.target_character_id,
                aggro_mode = 'tank',
                updated_at = CURRENT_TIMESTAMP
            """,
            mob_id,
            attacker_id,
        )
        return attacker_id, "tank"

    target_row = fetch_one(
        """
        SELECT mat.target_character_id
        FROM mob_aggro_targets mat
        JOIN characters c ON c.id = mat.target_character_id
        WHERE mat.mob_id = %s
          AND c.health_points > 0
        """,
        mob_id,
    )
    if target_row:
        return int(target_row[0]), "first_hit"

    execute(
        """
        INSERT INTO mob_aggro_targets (mob_id, target_character_id, aggro_mode, updated_at)
        VALUES (%s, %s, 'first_hit', CURRENT_TIMESTAMP)
        ON CONFLICT (mob_id) DO UPDATE SET
            target_character_id = EXCLUDED.target_character_id,
            aggro_mode = 'first_hit',
            updated_at = CURRENT_TIMESTAMP
        """,
        mob_id,
        attacker_id,
    )
    return attacker_id, "first_hit"


# ===== COMBAT API ENDPOINTS =====

@combat_router.post("/combat/attack/{character_id}/{mob_id}")
async def attack_mob(character_id: int, mob_id: int, ability_id: int = None, current_user_id: int = Depends(get_current_user_id)):
    """
    Attack a mob (or use ability)
    Returns combat log entry with damage, XP, gold, loot
    """
    try:
        ensure_character_owner(character_id, current_user_id)

        # Get character stats
        char = fetch_one("""
            SELECT c.id, c.name, c.level, c.health_points, c.max_health_points, c.position_x, c.position_y, c.experience,
                 s.strength, s.dexterity, s.constitution, s.intelligence, s.wisdom, s.luck,
                 COALESCE(cc.name, '')
            FROM characters c
            LEFT JOIN character_stats s ON s.character_id = c.id
             LEFT JOIN character_classes cc ON cc.id = c.class_id
            WHERE c.id = %s
        """, character_id)
        
        if not char:
            raise HTTPException(status_code=404, detail="Character not found")
        
        char_id, char_name, char_lvl, char_hp, char_max_hp, char_x, char_y, char_exp, str_val, dex, con, int_val, wis, luck, class_name = char

        equipped_bonus = fetch_one(
            """
            SELECT
                COALESCE(SUM(CASE WHEN inv.equipped = TRUE THEN i.armor_class ELSE 0 END), 0) AS armor_bonus,
                COALESCE(SUM(CASE WHEN inv.equipped = TRUE AND inv.slot IN ('right_hand', 'both_hands') THEN i.damage_min ELSE 0 END), 0) AS weapon_damage_min,
                COALESCE(SUM(CASE WHEN inv.equipped = TRUE AND inv.slot IN ('right_hand', 'both_hands') THEN i.damage_max ELSE 0 END), 0) AS weapon_damage_max
            FROM inventory inv
            JOIN items i ON i.id = inv.item_id
            WHERE inv.character_id = %s
            """,
            character_id,
        ) or (0, 0, 0)
        armor_bonus, weapon_damage_min, weapon_damage_max = equipped_bonus
        
        # Get mob stats
        mob = fetch_one("""
                 SELECT id, name, level, health_points, max_health_points, damage_min, damage_max,
                     armor_class, experience_reward, gold_reward, position_x, position_y, is_champion, champion_stars, mob_type
            FROM mobs WHERE id = %s
        """, mob_id)
        
        if not mob:
            raise HTTPException(status_code=404, detail="Mob not found")
        
        mob_id, mob_name, mob_lvl, mob_hp, mob_max_hp, mob_dmg_min, mob_dmg_max, mob_armor, mob_exp, mob_gold, mob_x, mob_y, is_champ, champ_stars, mob_type = mob
        is_humanoid = _is_humanoid_mob(mob_type)

        in_current_zone = fetch_val(
            """
            SELECT 1
            FROM characters c
            JOIN mob_zone_spawns mzs ON mzs.spawn_zone_id = c.current_zone_id
            WHERE c.id = %s
              AND mzs.mob_id = %s
            LIMIT 1
            """,
            character_id,
            mob_id,
        )
        if not in_current_zone:
            raise HTTPException(status_code=400, detail="Этот моб не находится в текущей зоне")

        active_zone_id = fetch_val("SELECT current_zone_id FROM characters WHERE id = %s", character_id)
        if active_zone_id:
            restore_zone_if_fully_dead(int(active_zone_id))
        population_row = fetch_zone_population_row(int(active_zone_id or 0), int(mob_id)) if active_zone_id else None
        if population_row and int(population_row.get("alive_count", 0)) <= 0:
            raise HTTPException(status_code=400, detail="Этот тип мобов сейчас полностью истреблен")

        if int(mob_hp or 0) <= 0:
            if population_row and int(population_row.get("alive_count", 0)) > 0:
                mob_hp = int(mob_max_hp or 1)
                execute("UPDATE mobs SET health_points = max_health_points WHERE id = %s", mob_id)
            else:
                raise HTTPException(status_code=400, detail="Этот моб сейчас недоступен")

        if population_row and population_row.get("is_boss"):
            party_size = fetch_val(
                """
                SELECT COUNT(*)
                FROM party_members pm2
                WHERE pm2.party_id = (
                    SELECT pm.party_id
                    FROM party_members pm
                    JOIN parties p ON p.id = pm.party_id
                    WHERE pm.character_id = %s
                      AND COALESCE(pm.status, 'active') = 'active'
                      AND COALESCE(p.status, 'active') = 'active'
                    LIMIT 1
                )
                  AND COALESCE(pm2.status, 'active') = 'active'
                """,
                character_id,
            ) or 0
            if int(party_size) < 2:
                raise HTTPException(status_code=400, detail="Босса можно атаковать только в группе")
        
        # Distance is still logged for telemetry, but we do not block combat by range in zones.
        distance = math.sqrt((mob_x - char_x)**2 + (mob_y - char_y)**2)
        
        # Champion bonuses
        if is_champ:
            champ_multiplier = 1 + (champ_stars * 0.3)  # +30% per star
            mob_hp = int(mob_hp * champ_multiplier)
            mob_max_hp = int(mob_max_hp * champ_multiplier)
            mob_dmg_min = int(mob_dmg_min * champ_multiplier)
            mob_dmg_max = int(mob_dmg_max * champ_multiplier)
            mob_exp = int(mob_exp * champ_multiplier)
            mob_gold = int(mob_gold * champ_multiplier)
        
        # Calculate hit/crit/block
        hit_chance = calculate_hit_chance(dex, 10)  # Mob has default 10 dex
        crit_chance = calculate_crit_chance(luck)
        block_chance = calculate_block_chance(10, 10)  # Mob has default stats
        
        is_hit = random.random() * 100 < hit_chance
        is_crit = random.random() * 100 < crit_chance if is_hit else False
        
        # Character attacks mob
        attacker_stats = {
            'damage_min': 5 + (str_val // 5) + int(weapon_damage_min or 0),  # Base + equipped weapon bonus
            'damage_max': 10 + (str_val // 3) + int(weapon_damage_max or 0),
            'strength': str_val,
            'luck': luck
        }
        defender_stats = {'armor_class': mob_armor}
        
        damage_dealt = 0
        combat_message = ""
        
        if not is_hit:
            combat_message = f"❌ {char_name} промахнулся по {mob_name}!"
        else:
            damage_dealt = calculate_damage(attacker_stats, defender_stats, is_crit)
            if is_crit:
                combat_message = f"⚔️ {char_name} нанёс КРИТИЧЕСКИЙ УДАР {mob_name} на {damage_dealt} урона!"
            else:
                combat_message = f"⚔️ {char_name} нанёс {damage_dealt} урона {mob_name}"
        
        # Update mob HP
        new_mob_hp = max(0, mob_hp - damage_dealt)
        mob_killed = new_mob_hp <= 0
        
        # Mob counter-attack (if alive)
        damage_taken = 0
        target_damage_taken = 0
        target_character_id = char_id
        target_character_name = char_name
        target_character_hp = char_hp
        attacker_new_hp = char_hp
        target_character_died = False
        mob_message = ""
        if not mob_killed:
            target_character_id, aggro_mode = _resolve_aggro_target(mob_id, char_id, _is_tank_class(class_name))
            target_char = fetch_one(
                """
                SELECT c.id, c.name, c.health_points, c.max_health_points,
                       COALESCE(s.dexterity, 10), COALESCE(s.constitution, 10)
                FROM characters c
                LEFT JOIN character_stats s ON s.character_id = c.id
                WHERE c.id = %s
                """,
                target_character_id,
            )

            if not target_char:
                target_character_id = char_id
                target_char = (char_id, char_name, char_hp, char_max_hp, dex, con)

            _, target_character_name, target_character_hp, _, target_dex, target_con = target_char
            target_block_chance = calculate_block_chance(target_dex, target_con)
            mob_is_hit = random.random() * 100 < calculate_hit_chance(10, target_dex)
            is_blocked = random.random() * 100 < target_block_chance
            
            if not mob_is_hit:
                mob_message = f"✓ {mob_name} промахнулся!"
            elif is_blocked:
                mob_message = f"🛡️ {target_character_name} заблокировал атаку {mob_name}!"
            else:
                target_damage_taken = random.randint(mob_dmg_min, mob_dmg_max)
                target_armor_bonus = fetch_val(
                    """
                    SELECT COALESCE(SUM(i.armor_class), 0)
                    FROM inventory inv
                    JOIN items i ON i.id = inv.item_id
                    WHERE inv.character_id = %s AND inv.equipped = TRUE
                    """,
                    target_character_id,
                ) or 0
                armor_reduction = (target_con - 10) * 0.3 + float(target_armor_bonus)  # Constitution + equipped armor
                target_damage_taken = max(1, int(target_damage_taken - armor_reduction))
                damage_taken = target_damage_taken
                mob_message = f"💥 {mob_name} нанёс {target_damage_taken} урона {target_character_name}"
                if target_character_id != char_id:
                    mob_message += f" (агр: {aggro_mode})"
        
            new_target_hp = max(0, target_character_hp - target_damage_taken)
            target_character_died = new_target_hp <= 0
            execute("UPDATE characters SET health_points = %s WHERE id = %s", new_target_hp, target_character_id)
            if target_character_id == char_id:
                attacker_new_hp = new_target_hp
        else:
            attacker_new_hp = char_hp
        
        # Calculate XP and gold with Lineage 2 penalties
        exp_gained = 0
        gold_gained = 0
        silver_gained = 0
        loot_items = []
        can_butcher = False

        exp_lost = 0
        death_territory = None
        dropped_items = []

        if target_character_died and target_character_id == char_id:
            exp_lost = max(1, int(int(char_exp or 0) * 0.08)) if int(char_exp or 0) > 0 else 0
            new_exp = max(0, int(char_exp or 0) - exp_lost)
            death_territory = _resolve_death_territory(character_id)
            dropped_items = _drop_inventory_on_death(character_id, death_territory)
            revive_hp = max(1, int(int(char_max_hp or 1) * 0.5))
            execute(
                "UPDATE characters SET experience = %s, health_points = %s WHERE id = %s",
                new_exp,
                revive_hp,
                character_id,
            )
            attacker_new_hp = revive_hp
        
        if mob_killed:
            exp_mult, gold_mult = get_exp_multiplier(char_lvl, mob_lvl)
            exp_gained = int(mob_exp * exp_mult)
            if is_humanoid:
                gold_gained = int(mob_gold * gold_mult)
                silver_gained = max(0, int((mob_gold * gold_mult * 12) // 1))
            else:
                gold_gained = 0
                silver_gained = 0
                can_butcher = True

            progression = apply_experience_and_level_up(character_id, exp_gained, gold_gained)
            if silver_gained > 0:
                execute("UPDATE characters SET silver = COALESCE(silver, 0) + %s WHERE id = %s", silver_gained, character_id)
            execute("UPDATE characters SET health_points = %s WHERE id = %s", attacker_new_hp, character_id)
            
            # Consume one unit from zone population and keep legacy mob hp state for compatibility.
            if active_zone_id:
                consume_mob_unit(int(active_zone_id), int(mob_id))
            execute("UPDATE mobs SET health_points = 0 WHERE id = %s", mob_id)
            execute("DELETE FROM mob_aggro_targets WHERE mob_id = %s", mob_id)

            # Auto-update active kill quests that target this mob.
            active_quest_ids = fetch_all(
                """
                SELECT cq.quest_id
                FROM character_quests cq
                JOIN quest_kill_targets qkt ON qkt.quest_id = cq.quest_id
                WHERE cq.character_id = %s
                  AND cq.status = 'active'
                  AND qkt.mob_id = %s
                """,
                character_id,
                mob_id,
            )
            for quest_row in active_quest_ids:
                quest_id = quest_row[0]
                existing_kill = fetch_one(
                    "SELECT id FROM character_quest_kills WHERE character_id = %s AND quest_id = %s AND mob_id = %s",
                    character_id,
                    quest_id,
                    mob_id,
                )
                if existing_kill:
                    execute(
                        "UPDATE character_quest_kills SET kill_count = kill_count + 1 WHERE id = %s",
                        existing_kill[0],
                    )
                else:
                    execute(
                        "INSERT INTO character_quest_kills (character_id, quest_id, mob_id, kill_count) VALUES (%s, %s, %s, 1)",
                        character_id,
                        quest_id,
                        mob_id,
                    )
            
            # Check for loot (simplified)
            # TODO: Implement full loot table system
            
            level_note = ""
            if progression.get("leveled_up"):
                level_note = f" | Уровень повышен до {progression.get('level')}"
            reward_note = f"+{exp_gained} опыта"
            if is_humanoid:
                reward_note += f", +{gold_gained} золота, +{silver_gained} серебра"
            mob_message = f"☠️ {mob_name} повержен! {reward_note}{level_note}"
        else:
            # Update mob HP
            execute("UPDATE mobs SET health_points = %s WHERE id = %s", new_mob_hp, mob_id)
        
        # Log combat
        execute("""
            INSERT INTO combat_log (character_id, mob_id, action_type, damage_dealt, damage_taken, 
                                    is_critical, is_miss, is_blocked, combat_message, distance)
            VALUES (%s, %s, 'attack', %s, %s, %s, %s, %s, %s, %s)
        """, character_id, mob_id, damage_dealt, damage_taken, is_crit, not is_hit, 
             False, combat_message + " | " + mob_message, distance)
        
        return {
            "success": True,
            "combat_log": [combat_message, mob_message],
            "damage_dealt": damage_dealt,
            "damage_taken": damage_taken,
            "is_critical": is_crit,
            "is_miss": not is_hit,
            "mob_killed": mob_killed,
            "character_died": target_character_died if target_character_id == char_id else False,
            "exp_gained": exp_gained,
            "gold_gained": gold_gained,
            "silver_gained": silver_gained,
            "loot": loot_items,
            "can_butcher": can_butcher,
            "mob_type": mob_type,
            "exp_lost": exp_lost,
            "death_territory": death_territory,
            "dropped_items": dropped_items,
            "character_hp": attacker_new_hp,
            "character_max_hp": char_max_hp,
            "mob_target_character_id": target_character_id,
            "mob_target_character_name": target_character_name,
            "mob_hp": new_mob_hp,
            "mob_max_hp": mob_max_hp
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@combat_router.get("/combat/log/{character_id}")
async def get_combat_log(character_id: int, limit: int = 20, current_user_id: int = Depends(get_current_user_id)):
    """
    Get recent combat log for character
    """
    try:
        ensure_character_owner(character_id, current_user_id)

        logs = fetch_all("""
            SELECT cl.combat_message, cl.damage_dealt, cl.damage_taken, cl.is_critical, cl.is_miss, cl.is_blocked, cl.timestamp,
                   m.name as mob_name
            FROM combat_log cl
            LEFT JOIN mobs m ON m.id = cl.mob_id
            WHERE cl.character_id = %s
            ORDER BY cl.timestamp DESC
            LIMIT %s
        """, character_id, limit)
        
        return {
            "logs": [
                {
                    "message": log[0],
                    "damage_dealt": log[1],
                    "damage_taken": log[2],
                    "is_critical": log[3],
                    "is_miss": log[4],
                    "is_blocked": log[5],
                    "timestamp": log[6].isoformat() if log[6] else None,
                    "mob_name": log[7]
                } for log in logs
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@combat_router.get("/combat/stats/{character_id}")
async def get_combat_stats(character_id: int, current_user_id: int = Depends(get_current_user_id)):
    """
    Get calculated combat statistics for character
    """
    try:
        ensure_character_owner(character_id, current_user_id)
        return _build_combat_stats_response(character_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@combat_router.post("/combat/stats/{character_id}/allocate")
async def allocate_stat_points(
    character_id: int,
    payload: StatAllocationRequest,
    current_user_id: int = Depends(get_current_user_id),
):
    """Allocate unspent stat points into character attributes."""
    try:
        ensure_character_owner(character_id, current_user_id)

        execute(
            """
            INSERT INTO character_stats (character_id)
            VALUES (%s)
            ON CONFLICT (character_id) DO NOTHING
            """,
            character_id,
        )

        allocation = {field: max(0, int(getattr(payload, field, 0) or 0)) for field in STAT_FIELDS}
        points_to_spend = sum(allocation.values())
        if points_to_spend <= 0:
            raise HTTPException(status_code=400, detail="No points provided for allocation")

        current = fetch_one(
            "SELECT COALESCE(available_stat_points, 0) FROM character_stats WHERE character_id = %s",
            character_id,
        )
        available_points = int(current[0] if current else 0)
        if points_to_spend > available_points:
            raise HTTPException(
                status_code=400,
                detail=f"Not enough available points: {available_points}",
            )

        updated = execute(
            """
            UPDATE character_stats
            SET strength = COALESCE(strength, 10) + %s,
                dexterity = COALESCE(dexterity, 10) + %s,
                constitution = COALESCE(constitution, 10) + %s,
                intelligence = COALESCE(intelligence, 10) + %s,
                wisdom = COALESCE(wisdom, 10) + %s,
                luck = COALESCE(luck, 10) + %s,
                available_stat_points = COALESCE(available_stat_points, 0) - %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE character_id = %s
              AND COALESCE(available_stat_points, 0) >= %s
            """,
            allocation["strength"],
            allocation["dexterity"],
            allocation["constitution"],
            allocation["intelligence"],
            allocation["wisdom"],
            allocation["luck"],
            points_to_spend,
            character_id,
            points_to_spend,
        )
        if not updated:
            raise HTTPException(status_code=400, detail="Failed to allocate points")

        # Derived pools react instantly to stat spending.
        con_gain = allocation["constitution"]
        int_gain = allocation["intelligence"]
        wis_gain = allocation["wisdom"]
        hp_gain = con_gain * 5
        mp_gain = (int_gain * 3) + (wis_gain * 2)
        if hp_gain > 0 or mp_gain > 0:
            execute(
                """
                UPDATE characters
                SET max_health_points = max_health_points + %s,
                    health_points = LEAST(max_health_points + %s, health_points + %s),
                    max_mana_points = max_mana_points + %s,
                    mana_points = LEAST(max_mana_points + %s, mana_points + %s)
                WHERE id = %s
                """,
                hp_gain,
                hp_gain,
                hp_gain,
                mp_gain,
                mp_gain,
                mp_gain,
                character_id,
            )

        return {
            "status": "success",
            "spent_points": points_to_spend,
            "allocation": allocation,
            "combat_stats": _build_combat_stats_response(character_id),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
