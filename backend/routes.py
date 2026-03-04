"""
🎮 DreaMMO API Routes
Main game mechanics endpoints
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from .database.connection import fetch_one, fetch_all, execute, fetch_val

# ===== Route Definitions =====
router = APIRouter(prefix="/api", tags=["game"])

# ===== Characters =====
class CharacterCreate(BaseModel):
    name: str
    user_id: int

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

@router.post("/characters/create", response_model=dict)
async def create_character(character: CharacterCreate):
    """Create new character for player"""
    try:
        # Check if character name exists
        existing = fetch_one("SELECT id FROM characters WHERE name = %s", character.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Character name already taken"
            )
        
        # Create character
        execute(
            """
            INSERT INTO characters (user_id, name, level, experience, health_points, max_health_points)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            character.user_id, character.name, 1, 0, 100, 100
        )
        
        # Get new character
        char = fetch_one("SELECT id, name, level, experience, health_points FROM characters WHERE name = %s", character.name)
        
        return {
            "status": "created",
            "character": {
                "id": char[0],
                "name": char[1],
                "level": char[2],
                "experience": char[3],
                "health_points": char[4]
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Character creation failed: {str(e)}"
        )

@router.get("/characters/{character_id}", response_model=dict)
async def get_character(character_id: int):
    """Get character details"""
    try:
        char = fetch_one(
            """
            SELECT id, name, level, experience, health_points, max_health_points, created_at
            FROM characters WHERE id = %s
            """,
            character_id
        )
        
        if not char:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Character not found"
            )
        
        # Get character stats
        stats = fetch_one(
            """
            SELECT strength, dexterity, constitution, intelligence, wisdom, luck, stamina
            FROM character_stats WHERE character_id = %s
            """,
            character_id
        )
        
        return {
            "id": char[0],
            "name": char[1],
            "level": char[2],
            "experience": char[3],
            "health_points": char[4],
            "max_health_points": char[5],
            "created_at": str(char[6]),
            "stats": {
                "strength": stats[0] if stats else 10,
                "dexterity": stats[1] if stats else 10,
                "constitution": stats[2] if stats else 10,
                "intelligence": stats[3] if stats else 10,
                "wisdom": stats[4] if stats else 10,
                "luck": stats[5] if stats else 10,
                "stamina": stats[6] if stats else 100
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/characters", response_model=dict)
async def list_characters(user_id: int):
    """Get all characters for a user"""
    try:
        characters = fetch_all(
            "SELECT id, name, level, experience, health_points FROM characters WHERE user_id = %s ORDER BY created_at DESC",
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
                    "health_points": c[4]
                }
                for c in characters
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

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
