"""
Abilities and skills system routes (5 active + 1 ultimate)
"""

from fastapi import APIRouter, HTTPException
from database.connection import fetch_all, fetch_one, execute, fetch_val
from datetime import datetime, timedelta

ability_router = APIRouter()

# ===== ABILITIES SYSTEM API =====

@ability_router.get("/abilities/available/{character_id}")
async def get_available_abilities(character_id: int):
    """
    Get abilities available to character based on class and race
    """
    try:
        char = fetch_one("""
            SELECT class_id, race_id, level
            FROM characters WHERE id = %s
        """, character_id)
        
        if not char:
            raise HTTPException(status_code=404, detail="Character not found")
        
        class_id, race_id, level = char
        
        # Get class abilities (5 active + 1 ultimate)
        abilities = fetch_all("""
            SELECT id, name, description, ability_type, level_requirement, mana_cost,
                   cooldown, damage_min, damage_max, healing, effect_type, is_ultimate, tier
            FROM abilities
            WHERE (class_id = %s OR race_id = %s)
            AND level_requirement <= %s
            AND id NOT IN (SELECT ability_id FROM character_learned_abilities WHERE character_id = %s)
            ORDER BY is_ultimate ASC, tier ASC, level_requirement ASC
        """, class_id, race_id, level, character_id)
        
        active_count = fetch_val("""
            SELECT COUNT(*) FROM character_learned_abilities cla
            JOIN abilities a ON a.id = cla.ability_id
            WHERE cla.character_id = %s AND a.is_ultimate = FALSE
        """, character_id)
        
        ultimate_count = fetch_val("""
            SELECT COUNT(*) FROM character_learned_abilities cla
            JOIN abilities a ON a.id = cla.ability_id
            WHERE cla.character_id = %s AND a.is_ultimate = TRUE
        """, character_id)
        
        return {
            "available_abilities": [
                {
                    "ability_id": a[0],
                    "name": a[1],
                    "description": a[2],
                    "ability_type": a[3],
                    "level_requirement": a[4],
                    "mana_cost": a[5],
                    "cooldown": a[6],
                    "damage_min": a[7],
                    "damage_max": a[8],
                    "healing": a[9],
                    "effect_type": a[10],
                    "is_ultimate": a[11],
                    "tier": a[12]
                } for a in abilities
            ],
            "learned_active_count": active_count,
            "learned_ultimate_count": ultimate_count,
            "max_active": 5,
            "max_ultimate": 1
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ability_router.post("/abilities/learn/{character_id}/{ability_id}")
async def learn_ability(character_id: int, ability_id: int):
    """
    Learn a new ability (max 5 active + 1 ultimate)
    """
    try:
        # Check if already learned
        exists = fetch_one("""
            SELECT id FROM character_learned_abilities
            WHERE character_id = %s AND ability_id = %s
        """, character_id, ability_id)
        
        if exists:
            raise HTTPException(status_code=400, detail="Ability already learned")
        
        # Check ability type
        ability = fetch_one("""
            SELECT is_ultimate, level_requirement FROM abilities WHERE id = %s
        """, ability_id)
        
        if not ability:
            raise HTTPException(status_code=404, detail="Ability not found")
        
        is_ultimate, req_level = ability
        
        # Check character level
        char_level = fetch_val("SELECT level FROM characters WHERE id = %s", character_id)
        if char_level < req_level:
            raise HTTPException(status_code=400, detail=f"Требуется {req_level} уровень")
        
        # Check limits
        if is_ultimate:
            count = fetch_val("""
                SELECT COUNT(*) FROM character_learned_abilities cla
                JOIN abilities a ON a.id = cla.ability_id
                WHERE cla.character_id = %s AND a.is_ultimate = TRUE
            """, character_id)
            if count >= 1:
                raise HTTPException(status_code=400, detail="Can only learn 1 ultimate ability")
        else:
            count = fetch_val("""
                SELECT COUNT(*) FROM character_learned_abilities cla
                JOIN abilities a ON a.id = cla.ability_id
                WHERE cla.character_id = %s AND a.is_ultimate = FALSE
            """, character_id)
            if count >= 5:
                raise HTTPException(status_code=400, detail="Can only learn 5 active abilities")
        
        # Learn ability
        execute("""
            INSERT INTO character_learned_abilities (character_id, ability_id)
            VALUES (%s, %s)
        """, character_id, ability_id)
        
        return {"success": True, "message": "Ability learned"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ability_router.get("/abilities/learned/{character_id}")
async def get_learned_abilities(character_id: int):
    """
    Get all learned abilities for character
    """
    try:
        abilities = fetch_all("""
            SELECT a.id, a.name, a.description, a.ability_type, a.mana_cost, a.cooldown,
                   a.damage_min, a.damage_max, a.healing, a.effect_type, a.is_ultimate, a.tier,
                   cas.slot_number
            FROM character_learned_abilities cla
            JOIN abilities a ON a.id = cla.ability_id
            LEFT JOIN character_ability_slots cas ON cas.ability_id = a.id AND cas.character_id = cla.character_id
            WHERE cla.character_id = %s
            ORDER BY a.is_ultimate ASC, a.tier ASC
        """, character_id)
        
        return {
            "learned_abilities": [
                {
                    "ability_id": a[0],
                    "name": a[1],
                    "description": a[2],
                    "ability_type": a[3],
                    "mana_cost": a[4],
                    "cooldown": a[5],
                    "damage_min": a[6],
                    "damage_max": a[7],
                    "healing": a[8],
                    "effect_type": a[9],
                    "is_ultimate": a[10],
                    "tier": a[11],
                    "slot": a[12]
                } for a in abilities
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ability_router.post("/abilities/equip/{character_id}/{ability_id}")
async def equip_ability_to_slot(character_id: int, ability_id: int, slot_number: int):
    """
    Equip ability to a slot (1-5 for active, 6 for ultimate)
    """
    try:
        # Validate slot
        if slot_number < 1 or slot_number > 6:
            raise HTTPException(status_code=400, detail="Invalid slot number (1-6)")
        
        # Check if ability is learned
        learned = fetch_one("""
            SELECT a.is_ultimate
            FROM character_learned_abilities cla
            JOIN abilities a ON a.id = cla.ability_id
            WHERE cla.character_id = %s AND cla.ability_id = %s
        """, character_id, ability_id)
        
        if not learned:
            raise HTTPException(status_code=400, detail="Ability not learned")
        
        is_ultimate = learned[0]
        
        # Validate slot type
        if is_ultimate and slot_number != 6:
            raise HTTPException(status_code=400, detail="Ultimate must be in slot 6")
        if not is_ultimate and slot_number == 6:
            raise HTTPException(status_code=400, detail="Only ultimate can be in slot 6")
        
        # Upsert slot
        execute("""
            INSERT INTO character_ability_slots (character_id, slot_number, ability_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (character_id, slot_number) 
            DO UPDATE SET ability_id = EXCLUDED.ability_id
        """, character_id, slot_number, ability_id)
        
        return {"success": True, "message": f"Ability equipped to slot {slot_number}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ability_router.post("/abilities/use/{character_id}/{ability_id}")
async def use_ability(character_id: int, ability_id: int, target_id: int = None, target_type: str = "mob"):
    """
    Use an ability in combat
    """
    try:
        # Check if on cooldown
        cooldown = fetch_one("""
            SELECT cooldown_ends_at FROM character_ability_cooldowns
            WHERE character_id = %s AND ability_id = %s
        """, character_id, ability_id)
        
        if cooldown and cooldown[0] > datetime.now():
            remaining = (cooldown[0] - datetime.now()).total_seconds()
            raise HTTPException(status_code=400, detail=f"On cooldown for {remaining:.1f} seconds")
        
        # Get ability info
        ability = fetch_one("""
            SELECT name, mana_cost, cooldown, damage_min, damage_max, healing, effect_type
            FROM abilities WHERE id = %s
        """, ability_id)
        
        if not ability:
            raise HTTPException(status_code=404, detail="Ability not found")
        
        ab_name, mana_cost, cooldown_sec, dmg_min, dmg_max, healing, effect = ability
        
        # Check mana
        char_mana = fetch_val("SELECT mana_points FROM characters WHERE id = %s", character_id)
        if char_mana < mana_cost:
            raise HTTPException(status_code=400, detail="Not enough mana")
        
        # Use ability
        execute("UPDATE characters SET mana_points = mana_points - %s WHERE id = %s", mana_cost, character_id)
        
        # Set cooldown
        cooldown_end = datetime.now() + timedelta(seconds=cooldown_sec)
        execute("""
            INSERT INTO character_ability_cooldowns (character_id, ability_id, cooldown_ends_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (character_id, ability_id)
            DO UPDATE SET used_at = NOW(), cooldown_ends_at = EXCLUDED.cooldown_ends_at
        """, character_id, ability_id, cooldown_end)
        
        # Calculate effect
        import random
        damage = random.randint(dmg_min, dmg_max) if dmg_min > 0 else 0
        
        result_message = f"✨ Использовал {ab_name}"
        if damage > 0:
            result_message += f" и нанёс {damage} урона"
        if healing > 0:
            execute("UPDATE characters SET health_points = LEAST(health_points + %s, max_health_points) WHERE id = %s", 
                   healing, character_id)
            result_message += f" и восстановил {healing} HP"
        
        return {
            "success": True,
            "message": result_message,
            "damage": damage,
            "healing": healing,
            "mana_used": mana_cost,
            "cooldown_seconds": cooldown_sec
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ability_router.get("/abilities/cooldowns/{character_id}")
async def get_ability_cooldowns(character_id: int):
    """
    Get current cooldowns for all abilities
    """
    try:
        cooldowns = fetch_all("""
            SELECT a.id, a.name, c.cooldown_ends_at
            FROM character_ability_cooldowns c
            JOIN abilities a ON a.id = c.ability_id
            WHERE c.character_id = %s AND c.cooldown_ends_at > NOW()
        """, character_id)
        
        now = datetime.now()
        return {
            "cooldowns": [
                {
                    "ability_id": cd[0],
                    "ability_name": cd[1],
                    "ends_at": cd[2].isoformat(),
                    "remaining_seconds": (cd[2] - now).total_seconds()
                } for cd in cooldowns
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
