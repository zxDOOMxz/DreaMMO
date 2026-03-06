"""
Routes for positioning, movement, and zone-based gameplay
"""

from fastapi import APIRouter, HTTPException
from database.connection import fetch_all, fetch_one, execute, fetch_val
from datetime import datetime, timedelta
import math

positioning_router = APIRouter()

# ===== POSITIONING AND ZONES API =====

@positioning_router.get("/world/zones/{location_id}")
async def get_location_zones(location_id: int, character_id: int):
    """
    Get all zones and objects in a location with distances
    Returns table-style data for UI display
    """
    try:
        # Get character current position
        char = fetch_one("""
            SELECT current_location_id, position_x, position_y, level
            FROM characters WHERE id = %s
        """, character_id)
        
        if not char:
            raise HTTPException(status_code=404, detail="Character not found")
        
        char_location_id, char_x, char_y, char_level = char
        
        # Update character location if not set
        if not char_location_id:
            execute("UPDATE characters SET current_location_id = %s WHERE id = %s", location_id, character_id)
            char_location_id = location_id
            char_x = 0
            char_y = 0
        
        # Get mob spawn zones with distances
        zones = fetch_all("""
            SELECT z.id, z.zone_name, z.zone_type, z.distance_from_center, z.position_x, z.position_y,
                   z.min_level, z.max_level, z.is_aggressive_zone, z.max_mobs
            FROM mob_spawn_zones z
            WHERE z.location_id = %s
            ORDER BY z.distance_from_center
        """, location_id)
        
        zone_list = []
        for z in zones:
            zone_id, name, ztype, distance, zx, zy, min_lvl, max_lvl, is_aggr, max_mobs = z
            
            # Calculate actual distance from character to zone
            actual_distance = math.sqrt((zx - char_x)**2 + (zy - char_y)**2)if (zx, zy) != (0, 0) else distance
            
            # Get mobs in this zone
            mobs_in_zone = fetch_all("""
                SELECT m.id, m.name, m.level, m.aggression_type, m.is_champion, m.champion_stars
                FROM mob_zone_spawns mzs
                JOIN mobs m ON m.id = mzs.mob_id
                WHERE mzs.spawn_zone_id = %s
            """, zone_id)
            
            mob_details = []
            for mob in mobs_in_zone:
                mob_id, mob_name, mob_lvl, aggr, is_champ, stars = mob
                aggr_display = "АГР" if aggr == "aggressive" else "ПАС"
                champ_display = "*" * (stars or 0) if is_champ else ""
                mob_details.append({
                    "id": mob_id,
                    "name": f"{mob_name} {champ_display}".strip(),
                    "level": mob_lvl,
                    "aggression": aggr_display,
                    "is_champion": is_champ,
                    "stars": stars or 0
                })
            
            zone_list.append({
                "zone_id": zone_id,
                "name": name,
                "type": ztype,
                "distance": round(actual_distance, 1),
                "level_range": f"{min_lvl}-{max_lvl}",
                "is_aggressive": is_aggr,
                "mobs": mob_details,
                "can_interact": actual_distance <= 10  # 10 meter interaction range
            })
        
        # Get NPCs with distances
        npcs = fetch_all("""
            SELECT id, name, type, level, description, distance_from_center, position_x, position_y
            FROM npcs
            WHERE location_id = %s
        """, location_id)
        
        npc_list = []
        for npc in npcs:
            npc_id, name, ntype, lvl, desc, distance, nx, ny = npc
            actual_distance = math.sqrt((nx - char_x)**2 + (ny - char_y)**2) if (nx, ny) != (0, 0) else distance
            
            interaction_options = []
            if ntype == "quest_giver":
                interaction_options = ["Квесты", "Сдать квест"]
            elif ntype == "merchant":
                interaction_options = ["Купить", "Продать"]
            elif ntype == "broker":
                interaction_options = ["Аукцион"]
            
            npc_list.append({
                "npc_id": npc_id,
                "name": name,
                "type": ntype,
                "level": lvl,
                "distance": round(actual_distance, 1),
                "can_interact": actual_distance <= 10,
                "interaction_options": interaction_options
            })
        
        return {
            "location_id": location_id,
            "character_position": {"x": char_x, "y": char_y},
            "zones": zone_list,
            "npcs": npc_list
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@positioning_router.post("/world/move/{character_id}")
async def start_movement(character_id: int, target_type: str, target_id: int):
    """
    Start moving character towards a target (zone, npc, mob)
    target_type: 'zone', 'npc', 'mob'
    """
    try:
        char = fetch_one("""
            SELECT id, position_x, position_y, movement_speed, is_moving
            FROM characters WHERE id = %s
        """, character_id)
        
        if not char:
            raise HTTPException(status_code=404, detail="Character not found")
        
        char_id, char_x, char_y, speed, is_moving = char
        
        # Get target position
        target_x, target_y, target_name = None, None, None
        
        if target_type == "zone":
            target = fetch_one("""
                SELECT position_x, position_y, zone_name
                FROM mob_spawn_zones WHERE id = %s
            """, target_id)
            if target:
                target_x, target_y, target_name = target
                
        elif target_type == "npc":
            target = fetch_one("""
                SELECT position_x, position_y, name
                FROM npcs WHERE id = %s
            """, target_id)
            if target:
                target_x, target_y, target_name = target
                
        elif target_type == "mob":
            target = fetch_one("""
                SELECT position_x, position_y, name
                FROM mobs WHERE id = %s
            """, target_id)
            if target:
                target_x, target_y, target_name = target
        
        if target_x is None:
            raise HTTPException(status_code=404, detail="Target not found")
        
        # Calculate distance
        distance = math.sqrt((target_x - char_x)**2 + (target_y - char_y)**2)
        
        # Update character movement state
        execute("""
            UPDATE characters 
            SET target_object_id = %s, 
                target_object_type = %s,
                distance_to_target = %s,
                is_moving = TRUE,
                last_position_update = NOW()
            WHERE id = %s
        """, target_id, target_type, distance, character_id)
        
        # Calculate arrival time
        arrival_time = distance / speed if speed > 0 else 0
        
        return {
            "status": "moving",
            "target_name": target_name,
            "target_type": target_type,
            "distance": round(distance, 1),
            "speed": speed,
            "eta_seconds": round(arrival_time, 1)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@positioning_router.get("/world/movement-status/{character_id}")
async def get_movement_status(character_id: int):
    """
    Get current movement status and update position
    """
    try:
        char = fetch_one("""
            SELECT position_x, position_y, target_object_id, target_object_type, 
                   distance_to_target, is_moving, movement_speed, last_position_update
            FROM characters WHERE id = %s
        """, character_id)
        
        if not char:
            raise HTTPException(status_code=404, detail="Character not found")
        
        char_x, char_y, target_id, target_type, distance, is_moving, speed, last_update = char
        
        if not is_moving or not target_id:
            return {
                "is_moving": False,
                "distance_remaining": 0
            }
        
        # Calculate time elapsed since last update
        time_elapsed = (datetime.now() - last_update).total_seconds()
        
        # Calculate distance moved
        distance_moved = speed * time_elapsed
        new_distance = max(0, distance - distance_moved)
        
        # Get target position
        target_x, target_y, target_name = None, None, None
        if target_type == "zone":
            target = fetch_one("SELECT position_x, position_y, zone_name FROM mob_spawn_zones WHERE id = %s", target_id)
        elif target_type == "npc":
            target = fetch_one("SELECT position_x, position_y, name FROM npcs WHERE id = %s", target_id)
        elif target_type == "mob":
            target = fetch_one("SELECT position_x, position_y, name FROM mobs WHERE id = %s", target_id)
        
        if target:
            target_x, target_y, target_name = target
        
        # Update position
        if new_distance <= 0:
            # Arrived at destination
            execute("""
                UPDATE characters 
                SET position_x = %s, 
                    position_y = %s,
                    distance_to_target = 0,
                    is_moving = FALSE,
                    last_position_update = NOW()
                WHERE id = %s
            """, target_x or char_x, target_y or char_y, character_id)
            
            return {
                "is_moving": False,
                "distance_remaining": 0,
                "arrived": True,
                "target_name": target_name
            }
        else:
            # Still moving
            # Calculate new position (move towards target)
            if target_x is not None and target_y is not None:
                direction_x = target_x - char_x
                direction_y = target_y - char_y
                total_distance = math.sqrt(direction_x**2 + direction_y**2)
                if total_distance > 0:
                    unit_x = direction_x / total_distance
                    unit_y = direction_y / total_distance
                    new_x = char_x + unit_x * distance_moved
                    new_y = char_y + unit_y * distance_moved
                else:
                    new_x, new_y = char_x, char_y
            else:
                new_x, new_y = char_x, char_y
            
            execute("""
                UPDATE characters 
                SET position_x = %s, 
                    position_y = %s,
                    distance_to_target = %s,
                    last_position_update = NOW()
                WHERE id = %s
            """, new_x, new_y, new_distance, character_id)
            
            eta = new_distance / speed if speed > 0 else 0
            
            return {
                "is_moving": True,
                "distance_remaining": round(new_distance, 1),
                "target_name": target_name,
                "eta_seconds": round(eta, 1)
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@positioning_router.post("/world/interact/{character_id}")
async def interact_with_object(character_id: int, target_type: str, target_id: int, action: str):
    """
    Interact with an object (NPC, zone, mob)
    action: 'talk', 'attack', 'gather', 'enter', 'buy', 'sell', 'quest', 'turn_in_quest'
    """
    try:
        # Check if character is close enough (10 meters)
        char = fetch_one("""
            SELECT position_x, position_y FROM characters WHERE id = %s
        """, character_id)
        
        if not char:
            raise HTTPException(status_code=404, detail="Character not found")
        
        char_x, char_y = char
        
        # Get target position and check distance
        target_info = None
        if target_type == "npc":
            target_info = fetch_one("""
                SELECT position_x, position_y, name, type FROM npcs WHERE id = %s
            """, target_id)
        elif target_type == "zone":
            target_info = fetch_one("""
                SELECT position_x, position_y, zone_name, zone_type FROM mob_spawn_zones WHERE id = %s
            """, target_id)
        
        if not target_info:
            raise HTTPException(status_code=404, detail="Target not found")
        
        target_x, target_y, target_name, target_subtype = target_info
        distance = math.sqrt((target_x - char_x)**2 + (target_y - char_y)**2)
        
        if distance > 10:
            return {
                "success": False,
                "message": f"Слишком далеко! Расстояние: {round(distance, 1)}м. Подойдите ближе (макс. 10м)"
            }
        
        # Handle different actions
        if action == "quest" and target_type == "npc":
            # Return available quests from this NPC
            quests = fetch_all("""
                SELECT q.id, q.title, q.description, q.required_level
                FROM quests q
                WHERE q.npc_id = %s
                AND q.id NOT IN (
                    SELECT quest_id FROM character_quests 
                    WHERE character_id = %s AND status IN ('active', 'completed')
                )
            """, target_id, character_id)
            
            return {
                "success": True,
                "action": "quest_list",
                "npc_name": target_name,
                "quests": [{"id": q[0], "title": q[1], "description": q[2], "required_level": q[3]} for q in quests]
            }
        
        elif action == "turn_in_quest" and target_type == "npc":
            # Get completed quests for this NPC
            completed = fetch_all("""
                SELECT cq.quest_id, q.title, q.gold_reward, q.experience_reward
                FROM character_quests cq
                JOIN quests q ON q.id = cq.quest_id
                WHERE cq.character_id = %s AND q.npc_id = %s AND cq.status = 'active' AND cq.is_completed = TRUE
            """, character_id, target_id)
            
            return {
                "success": True,
                "action": "turn_in_quests",
                "npc_name": target_name,
                "quests": [{"id": q[0], "title": q[1], "gold_reward": q[2], "exp_reward": q[3]} for q in completed]
            }
        
        elif action == "buy" and target_type == "npc":
            return {
                "success": True,
                "action": "shop_buy",
                "npc_name": target_name,
                "message": "Открыт магазин покупок (функционал в разработке)"
            }
        
        elif action == "sell" and target_type == "npc":
            return {
                "success": True,
                "action": "shop_sell",
                "npc_name": target_name,
                "message": "Открыт магазин продажи (функционал в разработке)"
            }
        
        elif action == "auction" and target_type == "npc":
            return {
                "success": True,
                "action": "auction",
                "npc_name": target_name,
                "message": "Открыт аукцион (функционал в разработке)"
            }
        
        elif action == "enter" and target_type == "zone":
            return {
                "success": True,
                "action": "enter_zone",
                "zone_name": target_name,
                "message": f"Вы вошли в зону: {target_name}"
            }
        
        else:
            return {
                "success": False,
                "message": f"Неизвестное действие: {action}"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
