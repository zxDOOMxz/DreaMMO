"""
Routes for positioning, movement, and zone-based gameplay
"""

from fastapi import APIRouter, HTTPException, Depends
from database.connection import fetch_all, fetch_one, execute, fetch_val
from datetime import datetime, timedelta
import math
from security import ensure_character_owner, get_current_user_id

positioning_router = APIRouter()

VENDOR_ITEM_NAMES = [
    'Роба ученика',
    'Роба адепта',
    'Роба арканиста',
    'Легкий кожаный доспех',
    'Легкий охотничий доспех',
    'Легкий доспех следопыта',
    'Тяжелый панцирь рекрута',
    'Тяжелый панцирь стража',
    'Тяжелый панцирь бастиона',
    'Деревянный одноручный меч',
    'Костяной одноручный меч',
    'Каменный одноручный меч',
    'Учебный меч',
    'Потрепанная куртка',
    'Малое зелье лечения',
    'Лисья шкура',
    'Лисья кость',
    'Волчья шкура',
    'Зуб волка',
]


def _inventory_add(character_id: int, item_id: int, quantity: int) -> None:
    if quantity <= 0:
        return
    existing = fetch_one(
        "SELECT id FROM inventory WHERE character_id = %s AND item_id = %s AND equipped = FALSE AND slot IS NULL LIMIT 1",
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


def _inventory_remove_from_bag(character_id: int, item_id: int, quantity: int) -> None:
    if quantity <= 0:
        return
    rows = fetch_all(
        """
        SELECT id, quantity
        FROM inventory
        WHERE character_id = %s AND item_id = %s AND equipped = FALSE AND slot IS NULL
        ORDER BY created_at ASC
        """,
        character_id,
        item_id,
    )
    remaining = int(quantity)
    for row_id, row_qty in rows:
        if remaining <= 0:
            break
        available = int(row_qty or 0)
        take = min(available, remaining)
        if available - take <= 0:
            execute("DELETE FROM inventory WHERE id = %s", row_id)
        else:
            execute("UPDATE inventory SET quantity = quantity - %s WHERE id = %s", take, row_id)
        remaining -= take

    if remaining > 0:
        raise HTTPException(status_code=400, detail="Недостаточно предметов в рюкзаке")

# ===== POSITIONING AND ZONES API =====

@positioning_router.get("/world/zones/{location_id}")
async def get_location_zones(location_id: int, character_id: int, current_user_id: int = Depends(get_current_user_id)):
    """
    Get all zones and objects in a location with distances
    Returns table-style data for UI display
    """
    try:
        ensure_character_owner(character_id, current_user_id)

        # Get character current position
        char = fetch_one("""
            SELECT current_location_id, position_x, position_y, COALESCE(position_z, 0), level
            FROM characters WHERE id = %s
        """, character_id)
        
        if not char:
            raise HTTPException(status_code=404, detail="Character not found")
        
        char_location_id, char_x, char_y, char_z, char_level = char
        
        # Update character location if not set
        if not char_location_id:
            execute("UPDATE characters SET current_location_id = %s WHERE id = %s", location_id, character_id)
            char_location_id = location_id
            char_x = 0
            char_y = 0
            char_z = 0
        
        # Get mob spawn zones with distances
        zones = fetch_all("""
                        SELECT z.id, z.zone_name, z.zone_type, z.distance_from_center, z.position_x, z.position_y, COALESCE(z.position_z, 0),
                   z.min_level, z.max_level, z.is_aggressive_zone, z.max_mobs
            FROM mob_spawn_zones z
            WHERE z.location_id = %s
                            AND z.zone_type IN ('city', 'hunting', 'resource')
            ORDER BY z.distance_from_center
        """, location_id)
        
        zone_list = []
        seen_zone_names = set()
        for z in zones:
            zone_id, name, ztype, distance, zx, zy, zz, min_lvl, max_lvl, is_aggr, max_mobs = z
            normalized_zone_name = (name or "").strip().lower()
            if normalized_zone_name in seen_zone_names:
                continue
            seen_zone_names.add(normalized_zone_name)
            
            # Calculate actual distance from character to zone
            actual_distance = math.sqrt((zx - char_x) ** 2 + (zy - char_y) ** 2 + (zz - char_z) ** 2) if (zx, zy, zz) != (0, 0, 0) else distance
            
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
                "position": {"x": float(zx or 0), "y": float(zy or 0), "z": float(zz or 0)},
                "level_range": f"{min_lvl}-{max_lvl}",
                "is_aggressive": is_aggr,
                "mobs": mob_details,
                "can_interact": actual_distance <= 10  # 10 meter interaction range
            })
        
        location_type_row = fetch_one("SELECT location_type FROM locations WHERE id = %s", location_id)
        location_type = (location_type_row[0] or "") if location_type_row else ""

        existing_types = {str(zone.get("type") or "").lower() for zone in zone_list}
        missing_types = [ztype for ztype in ("hunting", "resource") if ztype not in existing_types]

        # In city hubs, expose at least one hunting/resource destination zone from connected world locations.
        if missing_types and location_type in {"city", "town", "hub"}:
            fallback_rows = fetch_all(
                """
                SELECT z.id, z.zone_name, z.zone_type, z.distance_from_center,
                       z.position_x, z.position_y, COALESCE(z.position_z, 0),
                       z.min_level, z.max_level, z.is_aggressive_zone, z.max_mobs,
                       l.name
                FROM mob_spawn_zones z
                JOIN locations l ON l.id = z.location_id
                WHERE z.location_id <> %s
                                    AND z.zone_type IN ('hunting', 'resource')
                ORDER BY z.zone_type, z.min_level ASC, z.distance_from_center ASC
                """,
                                location_id,
            )

            added_types = set()
            for row in fallback_rows:
                zone_id, zone_name, zone_type, base_distance, zx, zy, zz, min_lvl, max_lvl, is_aggr, max_mobs, loc_name = row
                if zone_type not in missing_types:
                    continue
                if zone_type in added_types:
                    continue
                composed_name = f"{zone_name} ({loc_name})"
                if composed_name.strip().lower() in seen_zone_names:
                    continue
                added_types.add(zone_type)
                seen_zone_names.add(composed_name.strip().lower())
                actual_distance = math.sqrt((zx - char_x) ** 2 + (zy - char_y) ** 2 + (zz - char_z) ** 2)
                zone_list.append(
                    {
                        "zone_id": zone_id,
                        "name": composed_name,
                        "type": zone_type,
                        "distance": round(actual_distance, 1),
                        "position": {"x": float(zx or 0), "y": float(zy or 0), "z": float(zz or 0)},
                        "level_range": f"{min_lvl}-{max_lvl}",
                        "is_aggressive": bool(is_aggr),
                        "mobs": [],
                        "can_interact": actual_distance <= 10,
                    }
                )
                if len(added_types) == len(missing_types):
                    break

        # NPCs are intentionally visible only in city locations.
        npcs = []
        if location_type in {"city", "town", "hub"}:
            npcs = fetch_all("""
                SELECT id, name, type, level, description, distance_from_center, position_x, position_y, COALESCE(position_z, 0)
                FROM npcs
                WHERE location_id = %s
                  AND type IN ('quest_giver', 'merchant', 'broker', 'crafting_station', 'guard')
            """, location_id)
        
        npc_list = []
        seen_npc_names = set()
        for npc in npcs:
            npc_id, name, ntype, lvl, desc, distance, nx, ny, nz = npc
            normalized_npc_name = (name or "").strip().lower()
            if normalized_npc_name in seen_npc_names:
                continue
            seen_npc_names.add(normalized_npc_name)
            actual_distance = math.sqrt((nx - char_x) ** 2 + (ny - char_y) ** 2 + (nz - char_z) ** 2) if (nx, ny, nz) != (0, 0, 0) else distance
            
            interaction_options = []
            if ntype == "quest_giver":
                interaction_options = ["Квесты", "Сдать квест"]
            elif ntype == "merchant":
                interaction_options = ["Купить", "Продать"]
            elif ntype == "broker":
                interaction_options = ["Аукцион"]
            elif ntype == "crafting_station":
                interaction_options = ["Крафт"]
            
            npc_list.append({
                "npc_id": npc_id,
                "name": name,
                "type": ntype,
                "level": lvl,
                "distance": round(actual_distance, 1),
                "position": {"x": float(nx or 0), "y": float(ny or 0), "z": float(nz or 0)},
                "can_interact": actual_distance <= 10,
                "interaction_options": interaction_options
            })
        
        return {
            "location_id": location_id,
            "character_position": {"x": char_x, "y": char_y, "z": char_z},
            "zones": zone_list,
            "npcs": npc_list
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@positioning_router.post("/world/move/{character_id}")
async def start_movement(character_id: int, target_type: str, target_id: int, current_user_id: int = Depends(get_current_user_id)):
    """
    Start moving character towards a target (zone, npc, mob)
    target_type: 'zone', 'npc', 'mob'
    """
    try:
        ensure_character_owner(character_id, current_user_id)

        char = fetch_one("""
            SELECT id, position_x, position_y, COALESCE(position_z, 0), movement_speed, is_moving
            FROM characters WHERE id = %s
        """, character_id)
        
        if not char:
            raise HTTPException(status_code=404, detail="Character not found")
        
        char_id, char_x, char_y, char_z, speed, is_moving = char
        
        # Get target position
        target_x, target_y, target_z, target_name = None, None, None, None
        
        if target_type == "zone":
            target = fetch_one("""
                SELECT position_x, position_y, COALESCE(position_z, 0), zone_name
                FROM mob_spawn_zones WHERE id = %s
            """, target_id)
            if target:
                target_x, target_y, target_z, target_name = target
                
        elif target_type == "npc":
            target = fetch_one("""
                SELECT position_x, position_y, COALESCE(position_z, 0), name
                FROM npcs WHERE id = %s
            """, target_id)
            if target:
                target_x, target_y, target_z, target_name = target
                
        elif target_type == "mob":
            target = fetch_one("""
                SELECT position_x, position_y, COALESCE(position_z, 0), name
                FROM mobs WHERE id = %s
            """, target_id)
            if target:
                target_x, target_y, target_z, target_name = target
        
        if target_x is None:
            raise HTTPException(status_code=404, detail="Target not found")
        
        # Calculate distance
        distance = math.sqrt((target_x - char_x) ** 2 + (target_y - char_y) ** 2 + (target_z - char_z) ** 2)
        
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
async def get_movement_status(character_id: int, current_user_id: int = Depends(get_current_user_id)):
    """
    Get current movement status and update position
    """
    try:
        ensure_character_owner(character_id, current_user_id)

        char = fetch_one("""
                 SELECT position_x, position_y, COALESCE(position_z, 0), target_object_id, target_object_type, 
                   distance_to_target, is_moving, movement_speed, last_position_update
            FROM characters WHERE id = %s
        """, character_id)
        
        if not char:
            raise HTTPException(status_code=404, detail="Character not found")
        
        char_x, char_y, char_z, target_id, target_type, distance, is_moving, speed, last_update = char
        
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
        target_x, target_y, target_z, target_name = None, None, None, None
        if target_type == "zone":
            target = fetch_one("SELECT position_x, position_y, COALESCE(position_z, 0), zone_name FROM mob_spawn_zones WHERE id = %s", target_id)
        elif target_type == "npc":
            target = fetch_one("SELECT position_x, position_y, COALESCE(position_z, 0), name FROM npcs WHERE id = %s", target_id)
        elif target_type == "mob":
            target = fetch_one("SELECT position_x, position_y, COALESCE(position_z, 0), name FROM mobs WHERE id = %s", target_id)
        
        if target:
            target_x, target_y, target_z, target_name = target
        
        # Update position
        if new_distance <= 0:
            # Arrived at destination
            execute("""
                UPDATE characters 
                SET position_x = %s, 
                    position_y = %s,
                    position_z = %s,
                    distance_to_target = 0,
                    is_moving = FALSE,
                    last_position_update = NOW()
                WHERE id = %s
            """, target_x or char_x, target_y or char_y, target_z or char_z, character_id)
            
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
                direction_z = (target_z or 0) - char_z
                total_distance = math.sqrt(direction_x ** 2 + direction_y ** 2 + direction_z ** 2)
                if total_distance > 0:
                    unit_x = direction_x / total_distance
                    unit_y = direction_y / total_distance
                    unit_z = direction_z / total_distance
                    new_x = char_x + unit_x * distance_moved
                    new_y = char_y + unit_y * distance_moved
                    new_z = char_z + unit_z * distance_moved
                else:
                    new_x, new_y, new_z = char_x, char_y, char_z
            else:
                new_x, new_y, new_z = char_x, char_y, char_z
            
            execute("""
                UPDATE characters 
                SET position_x = %s, 
                    position_y = %s,
                    position_z = %s,
                    distance_to_target = %s,
                    last_position_update = NOW()
                WHERE id = %s
            """, new_x, new_y, new_z, new_distance, character_id)
            
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
async def interact_with_object(character_id: int, target_type: str, target_id: int, action: str, current_user_id: int = Depends(get_current_user_id)):
    """
    Interact with an object (NPC, zone, mob)
    action: 'talk', 'attack', 'gather', 'enter', 'buy', 'sell', 'quest', 'turn_in_quest'
    """
    try:
        ensure_character_owner(character_id, current_user_id)

        # Check if character is close enough (10 meters)
        char = fetch_one("""
            SELECT position_x, position_y, COALESCE(position_z, 0) FROM characters WHERE id = %s
        """, character_id)
        
        if not char:
            raise HTTPException(status_code=404, detail="Character not found")
        
        char_x, char_y, char_z = char
        
        # Get target position and check distance
        target_info = None
        if target_type == "npc":
            target_info = fetch_one("""
                SELECT position_x, position_y, COALESCE(position_z, 0), name, type FROM npcs WHERE id = %s
            """, target_id)
        elif target_type == "zone":
            target_info = fetch_one("""
                SELECT position_x, position_y, COALESCE(position_z, 0), zone_name, zone_type FROM mob_spawn_zones WHERE id = %s
            """, target_id)
        
        if not target_info:
            raise HTTPException(status_code=404, detail="Target not found")
        
        target_x, target_y, target_z, target_name, target_subtype = target_info
        distance = math.sqrt((target_x - char_x) ** 2 + (target_y - char_y) ** 2 + (target_z - char_z) ** 2)
        
        if distance > 10:
            return {
                "success": False,
                "message": f"Слишком далеко! Расстояние: {round(distance, 1)}м. Подойдите ближе (макс. 10м)"
            }
        
        # Handle different actions
        if action == "quest" and target_type == "npc":
            # Return available quests from this NPC
            quests = fetch_all("""
                SELECT q.id, q.title, q.description, q.level_requirement
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

        elif action == "craft" and target_type == "npc":
            recipes_count = fetch_val("SELECT COUNT(*) FROM crafting_recipes") or 0
            return {
                "success": True,
                "action": "craft_station",
                "npc_name": target_name,
                "message": f"Открыт крафтовый станок: {target_name}. Доступно рецептов: {int(recipes_count)}"
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
            starter_goods = fetch_all(
                """
                SELECT id, name, item_type, rarity, COALESCE(value, 0), COALESCE(description, '')
                FROM items
                WHERE name = ANY(%s)
                ORDER BY value ASC, name ASC
                """,
                VENDOR_ITEM_NAMES,
            )

            wallet = fetch_one("SELECT COALESCE(gold, 0), COALESCE(silver, 0) FROM characters WHERE id = %s", character_id) or (0, 0)

            return {
                "success": True,
                "action": "shop_buy",
                "npc_id": target_id,
                "npc_name": target_name,
                "message": f"Открыт магазин {target_name}.",
                "wallet": {"gold": int(wallet[0] or 0), "silver": int(wallet[1] or 0)},
                "items": [
                    {
                        "item_id": row[0],
                        "name": row[1],
                        "type": row[2],
                        "rarity": row[3],
                        "price_silver": int(row[4] or 0),
                        "description": row[5],
                    }
                    for row in starter_goods
                ],
            }
        
        elif action == "sell" and target_type == "npc":
            sell_rows = fetch_all(
                """
                SELECT i.id, i.name, i.item_type, i.rarity, COALESCE(i.value, 0),
                       inv.quantity, COALESCE(i.description, '')
                FROM inventory inv
                JOIN items i ON i.id = inv.item_id
                WHERE inv.character_id = %s AND inv.equipped = FALSE AND inv.slot IS NULL
                ORDER BY i.value DESC, i.name ASC
                """,
                character_id,
            )
            wallet = fetch_one("SELECT COALESCE(gold, 0), COALESCE(silver, 0) FROM characters WHERE id = %s", character_id) or (0, 0)

            return {
                "success": True,
                "action": "shop_sell",
                "npc_id": target_id,
                "npc_name": target_name,
                "message": f"Открыта продажа торговцу {target_name}.",
                "wallet": {"gold": int(wallet[0] or 0), "silver": int(wallet[1] or 0)},
                "items": [
                    {
                        "item_id": row[0],
                        "name": row[1],
                        "type": row[2],
                        "rarity": row[3],
                        "sell_price_silver": max(1, int(row[4] or 0) // 2),
                        "quantity": int(row[5] or 0),
                        "description": row[6],
                    }
                    for row in sell_rows
                ],
            }
        
        elif action == "auction" and target_type == "npc":
            return {
                "success": True,
                "action": "auction",
                "npc_name": target_name,
                "message": "Открыт аукцион (функционал в разработке)"
            }
        
        elif action == "enter" and target_type == "zone":
            zone_info = fetch_one(
                "SELECT id, location_id, zone_name, position_x, position_y, COALESCE(position_z, 0) FROM mob_spawn_zones WHERE id = %s",
                target_id,
            )
            if not zone_info:
                raise HTTPException(status_code=404, detail="Zone not found")

            zone_id, zone_location_id, zone_name, zone_x, zone_y, zone_z = zone_info

            execute(
                """
                UPDATE characters
                SET current_location_id = %s,
                    current_zone_id = %s,
                    position_x = %s,
                    position_y = %s,
                    position_z = %s
                WHERE id = %s
                """,
                zone_location_id,
                zone_id,
                zone_x,
                zone_y,
                zone_z,
                character_id,
            )

            zone_mobs = fetch_all(
                """
                SELECT m.id, m.name, m.level, m.health_points, m.max_health_points,
                       m.damage_min, m.damage_max, m.aggression_type
                FROM mob_zone_spawns mzs
                JOIN mobs m ON m.id = mzs.mob_id
                WHERE mzs.spawn_zone_id = %s
                  AND m.health_points > 0
                ORDER BY m.level ASC, m.name ASC
                """,
                zone_id,
            )

            return {
                "success": True,
                "action": "enter_zone",
                "zone_id": zone_id,
                "location_id": zone_location_id,
                "zone_name": zone_name,
                "message": f"Вы вошли в зону: {zone_name}",
                "mobs": [
                    {
                        "id": row[0],
                        "name": row[1],
                        "level": row[2],
                        "health": row[3],
                        "max_health": row[4],
                        "damage_min": row[5],
                        "damage_max": row[6],
                        "aggression": row[7],
                    }
                    for row in zone_mobs
                ],
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


@positioning_router.post("/shop/buy/{character_id}")
async def buy_item_from_vendor(
    character_id: int,
    npc_id: int,
    item_id: int,
    quantity: int = 1,
    current_user_id: int = Depends(get_current_user_id),
):
    """Buy an item from merchant using silver (with gold auto-conversion)."""
    try:
        ensure_character_owner(character_id, current_user_id)

        qty = max(1, int(quantity))
        item = fetch_one(
            "SELECT id, name, COALESCE(value, 0) FROM items WHERE id = %s",
            item_id,
        )
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        allowed = fetch_one("SELECT id FROM npcs WHERE id = %s AND type = 'merchant'", npc_id)
        if not allowed:
            raise HTTPException(status_code=400, detail="NPC is not a merchant")

        if item[1] not in VENDOR_ITEM_NAMES:
            raise HTTPException(status_code=400, detail="Item is not sold by starter merchants")

        char_pos = fetch_one("SELECT position_x, position_y FROM characters WHERE id = %s", character_id)
        npc_pos = fetch_one("SELECT position_x, position_y FROM npcs WHERE id = %s", npc_id)
        if not char_pos or not npc_pos:
            raise HTTPException(status_code=404, detail="Character or NPC not found")

        distance = math.sqrt((npc_pos[0] - char_pos[0]) ** 2 + (npc_pos[1] - char_pos[1]) ** 2)
        if distance > 10:
            raise HTTPException(status_code=400, detail="Слишком далеко от торговца")

        unit_price_silver = int(item[2] or 0)
        total_price_silver = unit_price_silver * qty

        wallet = fetch_one("SELECT COALESCE(gold, 0), COALESCE(silver, 0) FROM characters WHERE id = %s", character_id)
        gold = int(wallet[0] or 0)
        silver = int(wallet[1] or 0)
        total_wallet_silver = gold * 100 + silver

        if total_wallet_silver < total_price_silver:
            raise HTTPException(status_code=400, detail="Недостаточно средств")

        remaining = total_wallet_silver - total_price_silver
        new_gold = remaining // 100
        new_silver = remaining % 100

        execute("UPDATE characters SET gold = %s, silver = %s WHERE id = %s", new_gold, new_silver, character_id)
        _inventory_add(character_id, int(item_id), qty)

        return {
            "success": True,
            "message": f"Куплено: {item[1]} x{qty}",
            "item_name": item[1],
            "quantity": qty,
            "spent_silver": total_price_silver,
            "wallet": {"gold": new_gold, "silver": new_silver},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@positioning_router.post("/shop/sell/{character_id}")
async def sell_item_to_vendor(
    character_id: int,
    npc_id: int,
    item_id: int,
    quantity: int = 1,
    current_user_id: int = Depends(get_current_user_id),
):
    """Sell backpack item to merchant for silver."""
    try:
        ensure_character_owner(character_id, current_user_id)

        qty = max(1, int(quantity))
        item = fetch_one("SELECT id, name, COALESCE(value, 0) FROM items WHERE id = %s", item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        allowed = fetch_one("SELECT id, position_x, position_y FROM npcs WHERE id = %s AND type = 'merchant'", npc_id)
        if not allowed:
            raise HTTPException(status_code=400, detail="NPC is not a merchant")

        char_pos = fetch_one("SELECT position_x, position_y FROM characters WHERE id = %s", character_id)
        if not char_pos:
            raise HTTPException(status_code=404, detail="Character not found")
        distance = math.sqrt((allowed[1] - char_pos[0]) ** 2 + (allowed[2] - char_pos[1]) ** 2)
        if distance > 10:
            raise HTTPException(status_code=400, detail="Слишком далеко от торговца")

        bag_qty = fetch_val(
            "SELECT COALESCE(SUM(quantity), 0) FROM inventory WHERE character_id = %s AND item_id = %s AND equipped = FALSE AND slot IS NULL",
            character_id,
            item_id,
        ) or 0
        if int(bag_qty) < qty:
            raise HTTPException(status_code=400, detail="Недостаточно предметов для продажи")

        unit_sell = max(1, int(item[2] or 0) // 2)
        total_sell_silver = unit_sell * qty

        wallet = fetch_one("SELECT COALESCE(gold, 0), COALESCE(silver, 0) FROM characters WHERE id = %s", character_id) or (0, 0)
        total_wallet_silver = int(wallet[0] or 0) * 100 + int(wallet[1] or 0)
        updated_wallet = total_wallet_silver + total_sell_silver
        new_gold = updated_wallet // 100
        new_silver = updated_wallet % 100

        _inventory_remove_from_bag(character_id, int(item_id), qty)
        execute("UPDATE characters SET gold = %s, silver = %s WHERE id = %s", new_gold, new_silver, character_id)

        return {
            "success": True,
            "message": f"Продано: {item[1]} x{qty}",
            "item_name": item[1],
            "quantity": qty,
            "earned_silver": total_sell_silver,
            "wallet": {"gold": new_gold, "silver": new_silver},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
