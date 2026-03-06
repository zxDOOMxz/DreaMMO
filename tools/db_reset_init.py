#!/usr/bin/env python3
import os
import ssl
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import pg8000

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / 'backend' / 'database' / 'schema.sql'
ENV_PATH = ROOT / 'backend' / '.env'


def load_database_url() -> str:
    # Prefer env var, fallback to backend/.env
    url = os.getenv('DATABASE_URL')
    if url:
        return url
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding='utf-8').splitlines():
            if line.startswith('DATABASE_URL='):
                return line.split('=', 1)[1].strip()
    raise RuntimeError('DATABASE_URL not found in environment or backend/.env')


def connect_db(dsn: str):
    u = urlparse(dsn)
    assert u.scheme.startswith('postgres'), 'Only postgres URLs supported'
    user = u.username
    password = u.password
    host = u.hostname
    port = u.port or 5432
    database = u.path.lstrip('/')
    qs = parse_qs(u.query)
    # Force SSL
    ssl_context = ssl.create_default_context()
    conn = pg8000.connect(user=user, password=password, host=host, port=port, database=database, ssl_context=ssl_context)
    conn.autocommit = True
    return conn


def reset_schema(conn):
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS public CASCADE;")
        cur.execute("CREATE SCHEMA public;")
        cur.execute("GRANT ALL ON SCHEMA public TO public;")
        cur.execute("COMMENT ON SCHEMA public IS 'standard public schema';")
    print('✅ Schema reset complete')


def execute_schema(conn):
    sql = SCHEMA_PATH.read_text(encoding='utf-8')
    with conn.cursor() as cur:
        cur.execute(sql)
    print('✅ Schema applied from', SCHEMA_PATH)


def seed_initial_data(conn):
    with conn.cursor() as cur:
        # Check existing locations
        cur.execute('SELECT COUNT(*) FROM locations')
        count = cur.fetchone()[0]
        if count and count > 0:
            print('ℹ️  Locations already seeded, skipping...')
            return
        print('🌱 Seeding initial data...')
        locations = [
            ("Newbie Town", "A safe haven for new adventurers", "town", 0, True, 50),
            ("Dark Forest", "A dangerous forest filled with monsters", "wilderness", 5, True, 30),
            ("Ore Mine", "Rich mineral deposits for gathering", "dungeon", 3, False, 20),
            ("Blacksmith's Forge", "Legendary weapons and armor", "building", 1, False, 10),
            ("Tavern", "A place to rest and socialize", "town", 0, False, 100),
        ]
        for name, desc, loc_type, danger, pvp, capacity in locations:
            cur.execute(
                """
                INSERT INTO locations (name, description, location_type, danger_level, is_pvp_enabled, capacity)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (name, desc, loc_type, danger, pvp, capacity)
            )
        # first location id
        cur.execute('SELECT id FROM locations ORDER BY id LIMIT 1')
        row = cur.fetchone()
        if row:
            location_id = row[0]
            npcs = [
                ("Guard Captain", "guard", 5, 100),
                ("Wandering Merchant", "merchant", 2, 50),
                ("Old Sage", "quest_giver", 10, 200),
            ]
            for name, npc_type, level, hp in npcs:
                cur.execute(
                    """
                    INSERT INTO npcs (location_id, name, type, level, health_points, max_health_points)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (location_id, name, npc_type, level, hp, hp)
                )
        items = [
            ("Iron Sword", "weapon", "common", 5.0, 50, 10, 15),
            ("Wooden Shield", "armor", "common", 8.0, 30, 5, 0),
            ("Health Potion", "consumable", "common", 0.5, 20, 0, 0),
            ("Iron Ore", "material", "common", 2.0, 15, 0, 0),
        ]
        for name, item_type, rarity, weight, value, dmg_min, dmg_max in items:
            cur.execute(
                """
                INSERT INTO items (name, item_type, rarity, weight, value, damage_min, damage_max)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (name, item_type, rarity, weight, value, dmg_min, dmg_max)
            )
    print('✅ Initial data seeded')


def main():
    dsn = load_database_url()
    print('Connecting to:', dsn.split('@')[-1])
    conn = connect_db(dsn)
    try:
        reset_schema(conn)
        execute_schema(conn)
        seed_initial_data(conn)
        print('✅ Database reset and initialized successfully')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
