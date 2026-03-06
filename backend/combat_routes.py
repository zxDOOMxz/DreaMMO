"""
Combat system routes with Lineage 2-style mechanics
"""

from fastapi import APIRouter, HTTPException
from database.connection import fetch_all, fetch_one, execute, fetch_val
from datetime import datetime
import random
import math

combat_router = APIRouter()

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


# ===== COMBAT API ENDPOINTS =====

@combat_router.post("/combat/attack/{character_id}/{mob_id}")
async def attack_mob(character_id: int, mob_id: int, ability_id: int = None):
    """
    Attack a mob (or use ability)
    Returns combat log entry with damage, XP, gold, loot
    """
    try:
        # Get character stats
        char = fetch_one("""
            SELECT c.id, c.name, c.level, c.health_points, c.max_health_points, c.position_x, c.position_y,
                   s.strength, s.dexterity, s.constitution, s.intelligence, s.wisdom, s.luck
            FROM characters c
            LEFT JOIN character_stats s ON s.character_id = c.id
            WHERE c.id = %s
        """, character_id)
        
        if not char:
            raise HTTPException(status_code=404, detail="Character not found")
        
        char_id, char_name, char_lvl, char_hp, char_max_hp, char_x, char_y, str_val, dex, con, int_val, wis, luck = char
        
        # Get mob stats
        mob = fetch_one("""
            SELECT id, name, level, health_points, max_health_points, damage_min, damage_max, 
                   armor_class, experience_reward, gold_reward, position_x, position_y, is_champion, champion_stars
            FROM mobs WHERE id = %s
        """, mob_id)
        
        if not mob:
            raise HTTPException(status_code=404, detail="Mob not found")
        
        mob_id, mob_name, mob_lvl, mob_hp, mob_max_hp, mob_dmg_min, mob_dmg_max, mob_armor, mob_exp, mob_gold, mob_x, mob_y, is_champ, champ_stars = mob
        
        # Check distance (must be within 10 meters)
        distance = math.sqrt((mob_x - char_x)**2 + (mob_y - char_y)**2)
        if distance > 10:
            raise HTTPException(status_code=400, detail=f"Слишком далеко! Расстояние: {round(distance, 1)}м. Подойдите ближе.")
        
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
            'damage_min': 5 + (str_val // 5),  # Base 5 + strength bonus
            'damage_max': 10 + (str_val // 3),
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
        mob_message = ""
        if not mob_killed:
            mob_is_hit = random.random() * 100 < calculate_hit_chance(10, dex)
            is_blocked = random.random() * 100 < block_chance
            
            if not mob_is_hit:
                mob_message = f"✓ {mob_name} промахнулся!"
            elif is_blocked:
                mob_message = f"🛡️ {char_name} заблокировал атаку {mob_name}!"
            else:
                damage_taken = random.randint(mob_dmg_min, mob_dmg_max)
                armor_reduction = (con - 10) * 0.3  # Constitution provides armor
                damage_taken = max(1, int(damage_taken - armor_reduction))
                mob_message = f"💥 {mob_name} нанёс {damage_taken} урона {char_name}"
        
        # Update character HP
        new_char_hp = max(0, char_hp - damage_taken)
        char_died = new_char_hp <= 0
        
        # Calculate XP and gold with Lineage 2 penalties
        exp_gained = 0
        gold_gained = 0
        loot_items = []
        
        if mob_killed:
            exp_mult, gold_mult = get_exp_multiplier(char_lvl, mob_lvl)
            exp_gained = int(mob_exp * exp_mult)
            gold_gained = int(mob_gold * gold_mult)
            
            # Update character
            execute("""
                UPDATE characters
                SET experience = experience + %s,
                    gold = gold + %s,
                    health_points = %s
                WHERE id = %s
            """, exp_gained, gold_gained, new_char_hp, character_id)
            
            # Respawn mob or mark as dead
            execute("UPDATE mobs SET health_points = 0 WHERE id = %s", mob_id)
            
            # Check for loot (simplified)
            # TODO: Implement full loot table system
            
            mob_message = f"☠️ {mob_name} повержен! +{exp_gained} опыта, +{gold_gained} золота"
        else:
            # Update mob HP
            execute("UPDATE mobs SET health_points = %s WHERE id = %s", new_mob_hp, mob_id)
            # Update character HP
            execute("UPDATE characters SET health_points = %s WHERE id = %s", new_char_hp, character_id)
        
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
            "character_died": char_died,
            "exp_gained": exp_gained,
            "gold_gained": gold_gained,
            "loot": loot_items,
            "character_hp": new_char_hp,
            "character_max_hp": char_max_hp,
            "mob_hp": new_mob_hp,
            "mob_max_hp": mob_max_hp
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@combat_router.get("/combat/log/{character_id}")
async def get_combat_log(character_id: int, limit: int = 20):
    """
    Get recent combat log for character
    """
    try:
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
async def get_combat_stats(character_id: int):
    """
    Get calculated combat statistics for character
    """
    try:
        char = fetch_one("""
            SELECT c.level, s.strength, s.dexterity, s.constitution, s.intelligence, s.wisdom, s.luck
            FROM characters c
            LEFT JOIN character_stats s ON s.character_id = c.id
            WHERE c.id = %s
        """, character_id)
        
        if not char:
            raise HTTPException(status_code=404, detail="Character not found")
        
        lvl, str_val, dex, con, int_val, wis, luck = char
        
        # Calculate all combat stats
        base_dmg_min = 5 + (str_val // 5)
        base_dmg_max = 10 + (str_val // 3)
        hit_chance = calculate_hit_chance(dex, 10)
        crit_chance = calculate_crit_chance(luck)
        block_chance = calculate_block_chance(dex, con)
        attack_speed = calculate_attack_speed(60, dex)  # Base 60 attacks/min
        armor_value = (con - 10) * 0.3
        
        return {
            "level": lvl,
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
                "armor_value": round(armor_value, 1)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
