#!/usr/bin/env python3
"""
Database initialization script for DreaMMO
Initializes database schema and seed data
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.config import settings
from backend.database.connection import init_db_pool, close_db_pool, execute_sql_file, execute


async def init_database():
    """Initialize database schema"""
    # если .env отсутствует, попытаться создать копию из примера
    env_path = Path(__file__).parent / ".env"
    example_path = Path(__file__).parent / ".env.example"
    if not env_path.exists():
        if example_path.exists():
            print("⚠️  Файл .env не найден, создаю из .env.example")
            with open(example_path, 'r', encoding='utf-8') as src, open(env_path, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
            print("✅ .env создан. Обновите строку DATABASE_URL в .env перед запуском.")
        else:
            print("⚠️  Ни .env, ни .env.example не найдены. Создайте вручную")
    
    try:
        print("🎮 DreaMMO Database Initialization")
        print("=" * 50)
        
        # Initialize connection pool
        await init_db_pool()
        
        # Get database file path
        db_schema_path = Path(__file__).parent / "backend" / "database" / "schema.sql"
        
        if not db_schema_path.exists():
            print(f"❌ Schema file not found: {db_schema_path}")
            return False
        
        print(f"📋 Executing schema from: {db_schema_path}")
        
        # Execute schema
        execute_sql_file(str(db_schema_path))
        
        # Seed initial data
        print("🌱 Seeding initial data...")
        seed_initial_data()
        
        print("✅ Database initialization complete!")
        return True
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False
    finally:
        await close_db_pool()


def seed_initial_data():
    """Insert initial seed data"""
    try:
        # Check if data already exists
        from backend.database.connection import fetch_val
        
        location_count = fetch_val("SELECT COUNT(*) FROM locations")
        if location_count and location_count > 0:
            print("ℹ️  Locations already seeded, skipping...")
            return
        
        print("  • Adding starter locations...")
        
        # Add starter locations
        locations = [
            ("Newbie Town", "A safe haven for new adventurers", "town", 0, True, 50),
            ("Dark Forest", "A dangerous forest filled with monsters", "wilderness", 5, True, 30),
            ("Ore Mine", "Rich mineral deposits for gathering", "dungeon", 3, False, 20),
            ("Blacksmith's Forge", "Legendary weapons and armor", "building", 1, False, 10),
            ("Tavern", "A place to rest and socialize", "town", 0, False, 100),
        ]
        
        for name, desc, loc_type, danger, pvp, capacity in locations:
            execute("""
                INSERT INTO locations (name, description, location_type, danger_level, is_pvp_enabled, capacity)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, name, desc, loc_type, danger, pvp, capacity)
        
        print("  • Adding sample NPCs...")
        
        # Get first location ID
        from backend.database.connection import fetch_one
        first_location = fetch_one("SELECT id FROM locations LIMIT 1")
        
        if first_location:
            location_id = first_location[0]
            npcs = [
                ("Страж Тордек", "guard", 5, 100),
                ("Торговец Маркус", "merchant", 2, 50),
                ("Охотник Раймонд", "quest_giver", 10, 200),
            ]
            
            for name, npc_type, level, hp in npcs:
                execute("""
                    INSERT INTO npcs (location_id, name, type, level, health_points, max_health_points)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, location_id, name, npc_type, level, hp, hp)
        
        print("  • Adding sample items...")
        
        items = [
            ("Iron Sword", "weapon", "common", 5.0, 50, 10, 15),
            ("Wooden Shield", "armor", "common", 8.0, 30, 5, 0),
            ("Health Potion", "consumable", "common", 0.5, 20, 0, 0),
            ("Iron Ore", "material", "common", 2.0, 15, 0, 0),
        ]
        
        for name, item_type, rarity, weight, value, dmg_min, dmg_max in items:
            execute("""
                INSERT INTO items (name, item_type, rarity, weight, value, damage_min, damage_max)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, name, item_type, rarity, weight, value, dmg_min, dmg_max)
        
        print("✅ Initial data seeded successfully!")
        
    except Exception as e:
        print(f"⚠️  Error seeding data: {e}")
        # Don't fail completely if seeding fails


async def main():
    """Main entry point"""
    success = await init_database()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
