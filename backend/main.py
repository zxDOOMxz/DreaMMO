from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from database.connection import init_db_pool, close_db_pool, fetch_one, execute, fetch_val
from routes import router as game_router
from positioning_routes import positioning_router
from combat_routes import combat_router
from party_routes import party_router
from ability_routes import ability_router

# === Жизненный цикл приложения ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Инициализация при старте и очистка при остановке.
    """
    # STARTUP: Подключение к БД
    await init_db_pool()
    
    # Initialize database schema and test data
    try:
        from database.connection import execute
        from pathlib import Path
        
        schema_path = Path(__file__).parent / "database" / "schema.sql"
        if schema_path.exists():
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            execute(schema_sql)
            print("[OK] Database schema initialized")
        
        # Load positioning and party system extensions
        positioning_path = Path(__file__).parent / "database" / "positioning_system.sql"
        if positioning_path.exists():
            with open(positioning_path, 'r', encoding='utf-8') as f:
                positioning_sql = f.read()
            execute(positioning_sql)
            print("[OK] Positioning and party system initialized")
        
        # Load party invitations system
        invitations_path = Path(__file__).parent / "database" / "party_invitations.sql"
        if invitations_path.exists():
            with open(invitations_path, 'r', encoding='utf-8') as f:
                invitations_sql = f.read()
            execute(invitations_sql)
            print("[OK] Party invitations system initialized")
        
        # Migration: Add race_id to characters if not exists
        try:
            execute("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='characters' AND column_name='race_id'
                    ) THEN
                        ALTER TABLE characters ADD COLUMN race_id INTEGER REFERENCES races(id) ON DELETE SET NULL;
                    END IF;
                    
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='characters' AND column_name='class_id'
                    ) THEN
                        ALTER TABLE characters ADD COLUMN class_id INTEGER REFERENCES character_classes(id) ON DELETE SET NULL;
                    END IF;
                    
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='characters' AND column_name='mana_points'
                    ) THEN
                        ALTER TABLE characters ADD COLUMN mana_points INTEGER DEFAULT 50;
                        ALTER TABLE characters ADD COLUMN max_mana_points INTEGER DEFAULT 50;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='characters' AND column_name='silver'
                    ) THEN
                        ALTER TABLE characters ADD COLUMN silver INTEGER DEFAULT 0;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='ability_skill_coin_costs' AND column_name='required_completed_quests'
                    ) THEN
                        ALTER TABLE ability_skill_coin_costs ADD COLUMN required_completed_quests INTEGER DEFAULT 0;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='character_stats' AND column_name='available_stat_points'
                    ) THEN
                        ALTER TABLE character_stats ADD COLUMN available_stat_points INTEGER DEFAULT 0;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='character_classes' AND column_name='base_strength'
                    ) THEN
                        ALTER TABLE character_classes ADD COLUMN base_strength INTEGER DEFAULT 10;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='character_classes' AND column_name='base_dexterity'
                    ) THEN
                        ALTER TABLE character_classes ADD COLUMN base_dexterity INTEGER DEFAULT 10;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='character_classes' AND column_name='base_constitution'
                    ) THEN
                        ALTER TABLE character_classes ADD COLUMN base_constitution INTEGER DEFAULT 10;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='character_classes' AND column_name='base_intelligence'
                    ) THEN
                        ALTER TABLE character_classes ADD COLUMN base_intelligence INTEGER DEFAULT 10;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='character_classes' AND column_name='base_wisdom'
                    ) THEN
                        ALTER TABLE character_classes ADD COLUMN base_wisdom INTEGER DEFAULT 10;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='character_classes' AND column_name='base_luck'
                    ) THEN
                        ALTER TABLE character_classes ADD COLUMN base_luck INTEGER DEFAULT 10;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='characters' AND column_name='current_zone_id'
                    ) THEN
                        ALTER TABLE characters ADD COLUMN current_zone_id INTEGER;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='characters' AND column_name='position_z'
                    ) THEN
                        ALTER TABLE characters ADD COLUMN position_z DOUBLE PRECISION DEFAULT 0;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='mob_spawn_zones' AND column_name='position_z'
                    ) THEN
                        ALTER TABLE mob_spawn_zones ADD COLUMN position_z DOUBLE PRECISION DEFAULT 0;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='mobs' AND column_name='position_z'
                    ) THEN
                        ALTER TABLE mobs ADD COLUMN position_z DOUBLE PRECISION DEFAULT 0;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='npcs' AND column_name='position_z'
                    ) THEN
                        ALTER TABLE npcs ADD COLUMN position_z DOUBLE PRECISION DEFAULT 0;
                    END IF;
                END $$;
            """)
            print("[OK] Migration: character columns added/verified")
        except Exception as e:
            print(f"[WARNING] Migration failed: {e}")

        execute(
            """
            CREATE TABLE IF NOT EXISTS mob_aggro_targets (
                mob_id INTEGER PRIMARY KEY REFERENCES mobs(id) ON DELETE CASCADE,
                target_character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                aggro_mode VARCHAR(20) NOT NULL DEFAULT 'first_hit',
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Testing economy bootstrap: every character has at least 100 gold and 100 silver.
        execute("UPDATE characters SET gold = GREATEST(COALESCE(gold, 0), 100), silver = GREATEST(COALESCE(silver, 0), 100)")
        
        # Add test data
        from database.connection import fetch_val
        loc_count = fetch_val("SELECT COUNT(*) FROM locations")
        if loc_count == 0:
            execute("""
                INSERT INTO locations (name, description, location_type, danger_level) VALUES 
                ('Элдория', 'Главная деревня - место начала приключений. Здесь находятся торговцы, квестодатели и все необходимое для выживания', 'city', 1),
                ('Лес Охотников', 'Безопасный лес рядом с деревней, идеален для новичков', 'forest', 1),
                ('Горные пещеры', 'Пещеры в горах где можно добывать руду и камни', 'cave', 2),
                ('Болотистые земли', 'Опасное болото с агрессивными существами', 'swamp', 3),
                ('Темный лес', 'Очень опасный лес с сильными врагами', 'forest', 4),
                ('Горы Дракона', 'Высокие горы с древними руинами и боссами', 'mountain', 5)
            """)
        
        # Add races with passive abilities
        # Ensure races exist and are correct (use UPSERT to handle existing data)
        race_names = ['Гном', 'Орк', 'Эльф', 'Человек']
        if fetch_val("SELECT COUNT(*) FROM races") == 0 or fetch_val("SELECT COUNT(*) FROM races WHERE name = ANY(%s)", (race_names,)) < 4:
            # Delete existing incorrect races to rebuild
            execute("DELETE FROM race_passive_abilities WHERE race_id IN (SELECT id FROM races WHERE name = ANY(%s))", (race_names,))
            execute("DELETE FROM races WHERE name = ANY(%s)", (race_names,))
            
            # First, add race passive abilities
            execute("""
                INSERT INTO abilities (name, description, ability_type, level_requirement, effect_type) VALUES 
                ('Каменная кожа', '-3 урона от каждого физического удара', 'passive', 1, 'buff'),
                ('Горная выносливость', '+18% к сопротивлению усталости и оглушению', 'passive', 1, 'buff'),
                ('Грузовой хребет', '+60 кг к переносимому весу', 'passive', 1, 'buff'),
                
                ('Ярость клана', '+6% урона в ближнем бою', 'passive', 1, 'buff'),
                ('Кровавый трофей', 'Восстановление 4% HP после убийства', 'passive', 1, 'buff'),
                ('Сокрушительный удар', '+12% шанс тяжелого удара', 'passive', 1, 'buff'),
                
                ('Танец клинка', '+8% скорость передвижения и атаки', 'passive', 1, 'buff'),
                ('Эфирный канал', '-10% расход маны на заклинания', 'passive', 1, 'buff'),
                ('Острый глаз', '+10% дальность обнаружения и точность', 'passive', 1, 'buff'),
                
                ('Стальная воля', '+8% к восстановлению HP и MP вне боя', 'passive', 1, 'buff'),
                ('Адаптивность', '+1 ко всем характеристикам', 'passive', 1, 'buff'),
                ('Кодекс выжившего', '+8% к ремеслу, торговле и обучению навыков', 'passive', 1, 'buff')
            ON CONFLICT DO NOTHING
            """)
            
            # Now add races
            execute("""
                INSERT INTO races (name, description, strength_bonus, dexterity_bonus, constitution_bonus, 
                                   intelligence_bonus, wisdom_bonus, luck_bonus, health_bonus, mana_bonus) VALUES 
                ('Гном', 'Выше выживаемость и ремесло: +3 к выносливости, +3 к мудрости, +20 HP', 
                 0, -1, 3, 1, 3, 0, 20, 10),
                ('Орк', 'Максимум ближнего урона: +4 к силе, +2 к выносливости, +30 HP', 
                 4, 0, 2, -1, -1, 0, 30, -10),
                ('Эльфа', 'Лучшая мобильность и магия: +3 к ловкости, +3 к интеллекту, +20 MP', 
                 -1, 3, -1, 3, 1, 2, 0, 20),
                 ('Человек', 'Выносливый старт: +2 к силе, +20 HP, +20 MP', 
                  2, 0, 0, 0, 0, 0, 20, 20)
            ON CONFLICT DO NOTHING
            """)
            
            # Link race passive abilities
            execute("""
                INSERT INTO race_passive_abilities (race_id, ability_id) 
                SELECT r.id, a.id FROM races r, abilities a 
                WHERE r.name = 'Гном' AND a.name IN ('Каменная кожа', 'Горная выносливость', 'Грузовой хребет')
                ON CONFLICT DO NOTHING
            """)
            
            execute("""
                INSERT INTO race_passive_abilities (race_id, ability_id) 
                SELECT r.id, a.id FROM races r, abilities a 
                WHERE r.name = 'Орк' AND a.name IN ('Ярость клана', 'Кровавый трофей', 'Сокрушительный удар')
                ON CONFLICT DO NOTHING
            """)
            
            execute("""
                INSERT INTO race_passive_abilities (race_id, ability_id) 
                SELECT r.id, a.id FROM races r, abilities a 
                WHERE r.name = 'Эльф' AND a.name IN ('Танец клинка', 'Эфирный канал', 'Острый глаз')
                ON CONFLICT DO NOTHING
            """)
            
            execute("""
                INSERT INTO race_passive_abilities (race_id, ability_id) 
                SELECT r.id, a.id FROM races r, abilities a 
                WHERE r.name = 'Человек' AND a.name IN ('Стальная воля', 'Адаптивность', 'Кодекс выжившего')
                ON CONFLICT DO NOTHING
            """)

        # Keep race descriptions unified even for existing databases
        execute("""
            UPDATE races
            SET description = CASE
                WHEN name IN ('Гнома', 'Гном') THEN 'Выше выживаемость и ремесло: +3 к выносливости, +3 к мудрости, +20 HP'
                WHEN name IN ('Орка', 'Орк') THEN 'Максимум ближнего урона: +4 к силе, +2 к выносливости, +30 HP'
                WHEN name IN ('Эльфа', 'Эльф') THEN 'Лучшая мобильность и магия: +3 к ловкости, +3 к интеллекту, +20 MP'
                WHEN name IN ('Человека', 'Человек') THEN 'Выносливый старт: +2 к силе, +20 HP, +20 MP'
                ELSE description
            END
            WHERE name IN ('Гнома', 'Гном', 'Орка', 'Орк', 'Эльфа', 'Эльф', 'Человека', 'Человек')
        """)

        # Normalize requested human race bonuses on existing databases.
        execute("""
            UPDATE races
            SET
                strength_bonus = 2,
                dexterity_bonus = 0,
                constitution_bonus = 0,
                intelligence_bonus = 0,
                wisdom_bonus = 0,
                luck_bonus = 0,
                health_bonus = 20,
                mana_bonus = 20,
                description = 'Выносливый старт: +2 к силе, +20 HP, +20 MP'
            WHERE name IN ('Человека', 'Человек')
        """)

        # Remove duplicate race-passive links that may exist in legacy databases.
        execute("""
            DELETE FROM race_passive_abilities r1
            USING race_passive_abilities r2
            WHERE r1.id > r2.id
              AND r1.race_id = r2.race_id
              AND r1.ability_id = r2.ability_id
        """)

        execute("""
            DELETE FROM races old_r
            WHERE old_r.name = 'Гнома' AND EXISTS (SELECT 1 FROM races r WHERE r.name = 'Гном')
        """)
        execute("""
            DELETE FROM races old_r
            WHERE old_r.name = 'Орка' AND EXISTS (SELECT 1 FROM races r WHERE r.name = 'Орк')
        """)
        execute("""
            DELETE FROM races old_r
            WHERE old_r.name = 'Эльфа' AND EXISTS (SELECT 1 FROM races r WHERE r.name = 'Эльф')
        """)
        execute("""
            DELETE FROM races old_r
            WHERE old_r.name = 'Человека' AND EXISTS (SELECT 1 FROM races r WHERE r.name = 'Человек')
        """)

        # Cleanup legacy bootstrap data from init scripts (Old Sage / Newbie Town etc.).
        execute("""
            DELETE FROM npcs
            WHERE name IN ('Old Sage', 'Guard Captain', 'Wandering Merchant')
        """)

        # Cleanup duplicate zones with same name in the same location.
        execute("""
            DELETE FROM mob_spawn_zones z1
            USING mob_spawn_zones z2
            WHERE z1.id > z2.id
              AND z1.location_id = z2.location_id
              AND z1.zone_name = z2.zone_name
        """)

        # Normalize zone ownership and coordinates (city vs hunting/gathering) for legacy DBs.
        execute("""
            UPDATE mob_spawn_zones
            SET location_id = 1
            WHERE zone_name IN ('Рыночная площадь', 'Корчма "Золотой кубок"', 'Лавка ремесленника', 'Оружейная мастерская', 'Палатка алхимика', 'Крафтовый квартал')
        """)
        execute("""
            UPDATE mob_spawn_zones
            SET location_id = 2
            WHERE zone_name IN ('Поляна с кроликами', 'Логово лис', 'Волчий лес', 'Лагерь гоблинов', 'Стая волков')
        """)
        execute("""
            UPDATE mob_spawn_zones
            SET location_id = 3
            WHERE zone_name IN ('Железные жилы', 'Медные залежи', 'Пещерный лес', 'Кристальные образования')
        """)

        execute("UPDATE mob_spawn_zones SET position_x = 0, position_y = 0, distance_from_center = 0 WHERE location_id = 1 AND zone_name = 'Рыночная площадь'")
        execute("UPDATE mob_spawn_zones SET position_x = 10, position_y = 5, distance_from_center = 11 WHERE location_id = 1 AND zone_name = 'Корчма \"Золотой кубок\"'")
        execute("UPDATE mob_spawn_zones SET position_x = 15, position_y = 10, distance_from_center = 18 WHERE location_id = 1 AND zone_name = 'Лавка ремесленника'")
        execute("UPDATE mob_spawn_zones SET position_x = 20, position_y = 15, distance_from_center = 25 WHERE location_id = 1 AND zone_name = 'Оружейная мастерская'")
        execute("UPDATE mob_spawn_zones SET position_x = 25, position_y = 20, distance_from_center = 32 WHERE location_id = 1 AND zone_name = 'Палатка алхимика'")
        execute("UPDATE mob_spawn_zones SET position_x = 30, position_y = 15, distance_from_center = 34 WHERE location_id = 1 AND zone_name = 'Крафтовый квартал'")

        execute("UPDATE mob_spawn_zones SET position_x = 30, position_y = 30, distance_from_center = 42 WHERE location_id = 2 AND zone_name = 'Поляна с кроликами'")
        execute("UPDATE mob_spawn_zones SET position_x = 60, position_y = 40, distance_from_center = 72 WHERE location_id = 2 AND zone_name = 'Логово лис'")
        execute("UPDATE mob_spawn_zones SET position_x = 100, position_y = 70, distance_from_center = 122 WHERE location_id = 2 AND zone_name IN ('Волчий лес', 'Стая волков')")
        execute("UPDATE mob_spawn_zones SET position_x = 140, position_y = 90, distance_from_center = 166 WHERE location_id = 2 AND zone_name = 'Лагерь гоблинов'")
        execute("UPDATE mob_spawn_zones SET position_z = COALESCE(position_z, 0)")

        # Strict zone taxonomy: only city, hunting, resource.
        execute(
            """
            UPDATE mob_spawn_zones
            SET zone_type = CASE
                WHEN location_id = 1 THEN 'city'
                WHEN zone_name IN ('Лесная деревня', 'Шахтерский поселок') THEN 'city'
                WHEN location_id = 2 THEN 'hunting'
                WHEN location_id = 3 THEN 'resource'
                ELSE zone_type
            END
            WHERE location_id IN (1, 2, 3)
            """
        )

        execute("""
            UPDATE races
            SET name = CASE
                WHEN name = 'Гнома' THEN 'Гном'
                WHEN name = 'Орка' THEN 'Орк'
                WHEN name = 'Эльфа' THEN 'Эльф'
                WHEN name = 'Человека' THEN 'Человек'
                ELSE name
            END
            WHERE name IN ('Гнома', 'Орка', 'Эльфа', 'Человека')
        """)

        # Fix legacy mojibake race name for elf on old databases
        execute("""
            UPDATE races
            SET name = 'Эльф'
            WHERE name NOT IN ('Гном', 'Орк', 'Эльф', 'Человек')
              AND dexterity_bonus = 3
              AND intelligence_bonus = 3
        """)

        # Keep passive abilities unified even for existing databases
        execute("""
            UPDATE abilities
            SET
                name = CASE
                    WHEN name = 'Толстая шкура гнома' THEN 'Каменная кожа'
                    WHEN name = 'Боевой клич гнома' THEN 'Горная выносливость'
                    WHEN name = 'Шахтерское чутье' THEN 'Грузовой хребет'
                    WHEN name = 'Боевой клич Орка' THEN 'Ярость клана'
                    WHEN name = 'Жажда крови' THEN 'Кровавый трофей'
                    WHEN name = 'Сокрушитель' THEN 'Сокрушительный удар'
                    WHEN name = 'Быстрый бег эльфа' THEN 'Танец клинка'
                    WHEN name = 'Магический щит' THEN 'Эфирный канал'
                    WHEN name = 'Лесной охотник' THEN 'Острый глаз'
                    WHEN name = 'Прочное телосложение человека' THEN 'Стальная воля'
                    WHEN name = 'Универсальность' THEN 'Адаптивность'
                    WHEN name = 'Харизма' THEN 'Кодекс выжившего'
                    ELSE name
                END,
                description = CASE
                    WHEN name IN ('Толстая шкура гнома', 'Каменная кожа') THEN '-3 урона от каждого физического удара'
                    WHEN name IN ('Боевой клич гнома', 'Горная выносливость') THEN '+18% к сопротивлению усталости и оглушению'
                    WHEN name IN ('Шахтерское чутье', 'Грузовой хребет') THEN '+60 кг к переносимому весу'
                    WHEN name IN ('Боевой клич Орка', 'Ярость клана') THEN '+6% урона в ближнем бою'
                    WHEN name IN ('Жажда крови', 'Кровавый трофей') THEN 'Восстановление 4% HP после убийства'
                    WHEN name IN ('Сокрушитель', 'Сокрушительный удар') THEN '+12% шанс тяжелого удара'
                    WHEN name IN ('Быстрый бег эльфа', 'Танец клинка') THEN '+8% скорость передвижения и атаки'
                    WHEN name IN ('Магический щит', 'Эфирный канал') THEN '-10% расход маны на заклинания'
                    WHEN name IN ('Лесной охотник', 'Острый глаз') THEN '+10% дальность обнаружения и точность'
                    WHEN name IN ('Прочное телосложение человека', 'Стальная воля') THEN '+8% к восстановлению HP и MP вне боя'
                    WHEN name IN ('Универсальность', 'Адаптивность') THEN '+1 ко всем характеристикам'
                    WHEN name IN ('Харизма', 'Кодекс выжившего') THEN '+8% к ремеслу, торговле и обучению навыков'
                    ELSE description
                END
            WHERE ability_type = 'passive'
              AND (
                name IN (
                    'Толстая шкура гнома', 'Боевой клич гнома', 'Шахтерское чутье',
                    'Боевой клич Орка', 'Жажда крови', 'Сокрушитель',
                    'Быстрый бег эльфа', 'Магический щит', 'Лесной охотник',
                    'Прочное телосложение человека', 'Универсальность', 'Харизма',
                    'Каменная кожа', 'Горная выносливость', 'Грузовой хребет',
                    'Ярость клана', 'Кровавый трофей', 'Сокрушительный удар',
                    'Танец клинка', 'Эфирный канал', 'Острый глаз',
                    'Стальная воля', 'Адаптивность', 'Кодекс выжившего'
                )
              )
        """)
        
        # Add character classes - ensure all classes exist
        class_count = fetch_val("SELECT COUNT(*) FROM character_classes WHERE name IN ('Танк', 'Воин', 'Лучник', 'Целитель', 'Маг Огня', 'Некромант', 'Ледяной Маг')")
        if class_count < 7:
            execute("""
                INSERT INTO character_classes (
                    name, description, base_health, base_mana,
                    base_strength, base_dexterity, base_constitution, base_intelligence, base_wisdom, base_luck,
                    health_per_level, mana_per_level, primary_stat
                ) VALUES
                ('Танк', 'Могучий защитник с высоким здоровьем и броней', 150, 40, 11, 8, 14, 8, 10, 9, 20, 4, 'constitution'),
                ('Воин', 'Боевой класс ближнего боя с балансом урона и защиты', 120, 50, 14, 11, 12, 8, 9, 10, 15, 5, 'strength'),
                ('Лучник', 'Стрелок дальнего боя с высокой скоростью атаки', 100, 60, 9, 14, 10, 10, 10, 11, 12, 6, 'dexterity'),
                ('Целитель', 'Лекарь с мощными исцеляющими заклинаниями', 90, 120, 8, 10, 10, 11, 15, 10, 10, 15, 'wisdom'),
                ('Маг Огня', 'Элементалист огня с разрушительными заклинаниями', 80, 130, 7, 10, 9, 16, 11, 9, 8, 17, 'intelligence'),
                ('Некромант', 'Повелитель мертвых с темными заклинаниями', 85, 125, 8, 10, 10, 15, 12, 9, 9, 16, 'intelligence'),
                ('Ледяной Маг', 'Маг холода с замораживающими заклинаниями', 82, 128, 8, 11, 10, 15, 13, 9, 8, 17, 'intelligence')
            ON CONFLICT (name) DO UPDATE SET
                description = EXCLUDED.description,
                base_health = EXCLUDED.base_health,
                base_mana = EXCLUDED.base_mana,
                base_strength = EXCLUDED.base_strength,
                base_dexterity = EXCLUDED.base_dexterity,
                base_constitution = EXCLUDED.base_constitution,
                base_intelligence = EXCLUDED.base_intelligence,
                base_wisdom = EXCLUDED.base_wisdom,
                base_luck = EXCLUDED.base_luck,
                health_per_level = EXCLUDED.health_per_level,
                mana_per_level = EXCLUDED.mana_per_level,
                primary_stat = EXCLUDED.primary_stat
            """)

        # Keep class base stats synchronized for existing databases.
        execute("""
            UPDATE character_classes
            SET
                description = CASE
                    WHEN name = 'Танк' THEN 'Могучий защитник с высоким здоровьем и броней'
                    WHEN name = 'Воин' THEN 'Боевой класс ближнего боя с балансом урона и защиты'
                    WHEN name = 'Лучник' THEN 'Стрелок дальнего боя с высокой скоростью атаки'
                    WHEN name = 'Целитель' THEN 'Лекарь с мощными исцеляющими заклинаниями'
                    WHEN name = 'Маг Огня' THEN 'Элементалист огня с разрушительными заклинаниями'
                    WHEN name = 'Некромант' THEN 'Повелитель мертвых с темными заклинаниями'
                    WHEN name = 'Ледяной Маг' THEN 'Маг холода с замораживающими заклинаниями'
                    ELSE description
                END,
                base_health = CASE
                    WHEN name = 'Танк' THEN 150
                    WHEN name = 'Воин' THEN 120
                    WHEN name = 'Лучник' THEN 100
                    WHEN name = 'Целитель' THEN 90
                    WHEN name = 'Маг Огня' THEN 80
                    WHEN name = 'Некромант' THEN 85
                    WHEN name = 'Ледяной Маг' THEN 82
                    ELSE base_health
                END,
                base_mana = CASE
                    WHEN name = 'Танк' THEN 40
                    WHEN name = 'Воин' THEN 50
                    WHEN name = 'Лучник' THEN 60
                    WHEN name = 'Целитель' THEN 120
                    WHEN name = 'Маг Огня' THEN 130
                    WHEN name = 'Некромант' THEN 125
                    WHEN name = 'Ледяной Маг' THEN 128
                    ELSE base_mana
                END,
                base_strength = CASE
                    WHEN name = 'Танк' THEN 11
                    WHEN name = 'Воин' THEN 14
                    WHEN name = 'Лучник' THEN 9
                    WHEN name = 'Целитель' THEN 8
                    WHEN name = 'Маг Огня' THEN 7
                    WHEN name = 'Некромант' THEN 8
                    WHEN name = 'Ледяной Маг' THEN 8
                    ELSE base_strength
                END,
                base_dexterity = CASE
                    WHEN name = 'Танк' THEN 8
                    WHEN name = 'Воин' THEN 11
                    WHEN name = 'Лучник' THEN 14
                    WHEN name = 'Целитель' THEN 10
                    WHEN name = 'Маг Огня' THEN 10
                    WHEN name = 'Некромант' THEN 10
                    WHEN name = 'Ледяной Маг' THEN 11
                    ELSE base_dexterity
                END,
                base_constitution = CASE
                    WHEN name = 'Танк' THEN 14
                    WHEN name = 'Воин' THEN 12
                    WHEN name = 'Лучник' THEN 10
                    WHEN name = 'Целитель' THEN 10
                    WHEN name = 'Маг Огня' THEN 9
                    WHEN name = 'Некромант' THEN 10
                    WHEN name = 'Ледяной Маг' THEN 10
                    ELSE base_constitution
                END,
                base_intelligence = CASE
                    WHEN name = 'Танк' THEN 8
                    WHEN name = 'Воин' THEN 8
                    WHEN name = 'Лучник' THEN 10
                    WHEN name = 'Целитель' THEN 11
                    WHEN name = 'Маг Огня' THEN 16
                    WHEN name = 'Некромант' THEN 15
                    WHEN name = 'Ледяной Маг' THEN 15
                    ELSE base_intelligence
                END,
                base_wisdom = CASE
                    WHEN name = 'Танк' THEN 10
                    WHEN name = 'Воин' THEN 9
                    WHEN name = 'Лучник' THEN 10
                    WHEN name = 'Целитель' THEN 15
                    WHEN name = 'Маг Огня' THEN 11
                    WHEN name = 'Некромант' THEN 12
                    WHEN name = 'Ледяной Маг' THEN 13
                    ELSE base_wisdom
                END,
                base_luck = CASE
                    WHEN name = 'Танк' THEN 9
                    WHEN name = 'Воин' THEN 10
                    WHEN name = 'Лучник' THEN 11
                    WHEN name = 'Целитель' THEN 10
                    WHEN name = 'Маг Огня' THEN 9
                    WHEN name = 'Некромант' THEN 9
                    WHEN name = 'Ледяной Маг' THEN 9
                    ELSE base_luck
                END,
                health_per_level = CASE
                    WHEN name = 'Танк' THEN 20
                    WHEN name = 'Воин' THEN 15
                    WHEN name = 'Лучник' THEN 12
                    WHEN name = 'Целитель' THEN 10
                    WHEN name = 'Маг Огня' THEN 8
                    WHEN name = 'Некромант' THEN 9
                    WHEN name = 'Ледяной Маг' THEN 8
                    ELSE health_per_level
                END,
                mana_per_level = CASE
                    WHEN name = 'Танк' THEN 4
                    WHEN name = 'Воин' THEN 5
                    WHEN name = 'Лучник' THEN 6
                    WHEN name = 'Целитель' THEN 15
                    WHEN name = 'Маг Огня' THEN 17
                    WHEN name = 'Некромант' THEN 16
                    WHEN name = 'Ледяной Маг' THEN 17
                    ELSE mana_per_level
                END,
                primary_stat = CASE
                    WHEN name = 'Танк' THEN 'constitution'
                    WHEN name = 'Воин' THEN 'strength'
                    WHEN name = 'Лучник' THEN 'dexterity'
                    WHEN name = 'Целитель' THEN 'wisdom'
                    WHEN name = 'Маг Огня' THEN 'intelligence'
                    WHEN name = 'Некромант' THEN 'intelligence'
                    WHEN name = 'Ледяной Маг' THEN 'intelligence'
                    ELSE primary_stat
                END
            WHERE name IN ('Танк', 'Воин', 'Лучник', 'Целитель', 'Маг Огня', 'Некромант', 'Ледяной Маг')
        """)
        
        # Add abilities
        ability_count = fetch_val("SELECT COUNT(*) FROM abilities")
        if ability_count == 0:
            execute("""
                INSERT INTO abilities (name, description, ability_type, class_id, level_requirement, mana_cost, cooldown, damage_min, damage_max, healing, effect_type, range_m) VALUES 
                ('Удар щитом', 'Мощный удар щитом оглушает противника', 'skill', 1, 1, 0, 3, 12, 18, 0, 'damage', 1),
                ('Защитная стойка', 'Увеличивает защиту на 50%', 'skill', 1, 1, 0, 10, 0, 0, 0, 'buff', 0),
                ('Провокация', 'Заставляет врагов атаковать только вас', 'skill', 1, 3, 0, 15, 0, 0, 0, 'taunt', 5),
                
                ('Удар мечом', 'Сильный удар мечом', 'skill', 2, 1, 0, 2, 10, 15, 0, 'damage', 1),
                ('Кровавый удар', 'Наносит урон и восстанавливает здоровье', 'skill', 2, 3, 0, 8, 15, 22, 0, 'damage', 1),
                
                ('Выстрел из лука', 'Точный выстрел', 'skill', 3, 1, 0, 2, 8, 12, 0, 'damage', 25),
                ('Залп стрел', 'Несколько быстрых выстрелов', 'skill', 3, 2, 0, 6, 6, 9, 0, 'damage', 25),
                ('Отравленная стрела', 'Стрела с ядом', 'skill', 3, 4, 0, 12, 12, 18, 0, 'damage', 25),
                
                ('Исцеление', 'Восстанавливает здоровье союзника', 'spell', 4, 1, 25, 5, 0, 0, 35, 'heal', 15),
                ('Массовое исцеление', 'Исцеляет всех союзников', 'spell', 4, 3, 50, 15, 0, 0, 25, 'heal', 10),
                ('Благословение', 'Увеличивает защиту союзников', 'spell', 4, 2, 30, 20, 0, 0, 0, 'buff', 10),
                
                ('Огненный шар', 'Шар огня', 'spell', 5, 1, 20, 3, 15, 22, 0, 'damage', 15),
                ('Стена огня', 'Создает стену огня вокруг', 'spell', 5, 3, 40, 12, 8, 12, 0, 'damage', 8),
                ('Огненная буря', 'Мощная огненная атака по области', 'spell', 5, 5, 60, 20, 25, 35, 0, 'damage', 12),
                
                ('Призыв скелета', 'Призывает скелета-воина', 'spell', 6, 1, 30, 10, 0, 0, 0, 'summon', 5),
                ('Проклятие слабости', 'Снижает силу противника', 'spell', 6, 2, 25, 15, 0, 0, 0, 'debuff', 10),
                ('Взрыв смерти', 'Наносит урон нежити и исцеляет некроманта', 'spell', 6, 4, 45, 18, 20, 30, 15, 'damage', 8),
                
                ('Ледяная стрела', 'Замораживающая стрела', 'spell', 7, 1, 18, 3, 12, 18, 0, 'damage', 18),
                ('Ледяной щит', 'Защитный ледяной барьер', 'spell', 7, 2, 35, 12, 0, 0, 0, 'buff', 0),
                ('Ледяная буря', 'Мощная ледяная атака по области', 'spell', 7, 4, 55, 22, 18, 28, 0, 'damage', 10)
            """)

        # Starter active race skills (one per race).
        race_starter_skills = {
            'Гном': ('Гном: Первый путь', 'Крепкий размах молотом: +15% к шансу блока на 6 сек', 'buff', 0, 10, 0, 0),
            'Орк': ('Орк: Первый путь', 'Клич берсерка: +12% урона на 6 сек', 'buff', 0, 12, 0, 0),
            'Эльф': ('Эльф: Первый путь', 'Стремительный выпад: наносит легкий урон и ускоряет шаг', 'damage', 6, 10, 9, 13),
            'Человек': ('Человек: Первый путь', 'Тактическая готовность: +10% к урону и защите на 6 сек', 'buff', 0, 10, 0, 0),
        }
        for _, skill in race_starter_skills.items():
            class_id = fetch_val("SELECT id FROM character_classes WHERE name = 'Воин' LIMIT 1") or 2
            execute(
                """
                INSERT INTO abilities (name, description, ability_type, class_id, level_requirement, mana_cost, cooldown, damage_min, damage_max, effect_type, range_m)
                SELECT %s, %s, 'skill', %s, 1, %s, %s, %s, %s, %s, 1
                WHERE NOT EXISTS (SELECT 1 FROM abilities WHERE name = %s)
                """,
                skill[0],
                skill[1],
                class_id,
                skill[3],
                skill[4],
                skill[5],
                skill[6],
                skill[2],
                skill[0],
            )

        # Strict race+class identity set: 5 skills (2 attack, 2 defense, 1 recovery) + 1 ultimate.
        race_list = ['Гном', 'Орк', 'Эльф', 'Человек']
        race_class_ability_kits = {
            'Танк': [
                ('[ATK1]', 'Щитовое крушение', 'damage', 0, 6, 10, 14, 0, 1, 1),
                ('[ATK2]', 'Пролом строя', 'damage', 0, 9, 14, 20, 0, 2, 2),
                ('[DEF1]', 'Крепкий бастион', 'buff', 0, 10, 0, 0, 0, 3, 2),
                ('[DEF2]', 'Железная стойка', 'buff', 0, 12, 0, 0, 0, 4, 3),
                ('[REC]', 'Второе дыхание', 'heal', 14, 14, 0, 0, 26, 5, 3),
                ('[ULT]', 'Непробиваемая линия', 'buff', 24, 22, 0, 0, 0, 8, 5),
            ],
            'Воин': [
                ('[ATK1]', 'Рубящий натиск', 'damage', 0, 6, 11, 16, 0, 1, 1),
                ('[ATK2]', 'Карающий разрез', 'damage', 0, 9, 15, 22, 0, 2, 2),
                ('[DEF1]', 'Боевой гард', 'buff', 0, 10, 0, 0, 0, 3, 2),
                ('[DEF2]', 'Стойкость легиона', 'buff', 0, 13, 0, 0, 0, 4, 3),
                ('[REC]', 'Кровавый драйв', 'heal', 12, 14, 0, 0, 22, 5, 3),
                ('[ULT]', 'Вихрь берсерка', 'damage', 18, 20, 26, 34, 0, 8, 5),
            ],
            'Лучник': [
                ('[ATK1]', 'Прицельный выстрел', 'damage', 0, 6, 10, 15, 0, 1, 1),
                ('[ATK2]', 'Серия стрел', 'damage', 0, 9, 14, 21, 0, 2, 2),
                ('[DEF1]', 'Уклон мангуста', 'buff', 0, 10, 0, 0, 0, 3, 2),
                ('[DEF2]', 'Дымовой шаг', 'buff', 0, 13, 0, 0, 0, 4, 3),
                ('[REC]', 'Полевая перевязка', 'heal', 12, 14, 0, 0, 20, 5, 3),
                ('[ULT]', 'Ливень наконечников', 'damage', 20, 20, 24, 33, 0, 8, 5),
            ],
            'Целитель': [
                ('[ATK1]', 'Световой импульс', 'damage', 10, 6, 9, 14, 0, 1, 1),
                ('[ATK2]', 'Кара света', 'damage', 14, 9, 13, 19, 0, 2, 2),
                ('[DEF1]', 'Священный покров', 'buff', 12, 10, 0, 0, 0, 3, 2),
                ('[DEF2]', 'Барьер милосердия', 'buff', 16, 13, 0, 0, 0, 4, 3),
                ('[REC]', 'Большое исцеление', 'heal', 18, 12, 0, 0, 34, 5, 3),
                ('[ULT]', 'Чудо возрождения', 'heal', 30, 22, 0, 0, 62, 8, 5),
            ],
            'Маг Огня': [
                ('[ATK1]', 'Пылающий заряд', 'damage', 12, 6, 12, 17, 0, 1, 1),
                ('[ATK2]', 'Огненная комета', 'damage', 16, 9, 16, 23, 0, 2, 2),
                ('[DEF1]', 'Пепельный покров', 'buff', 12, 10, 0, 0, 0, 3, 2),
                ('[DEF2]', 'Круг тлеющих рун', 'buff', 15, 13, 0, 0, 0, 4, 3),
                ('[REC]', 'Жаркое восстановление', 'heal', 16, 14, 0, 0, 24, 5, 3),
                ('[ULT]', 'Солнечный катаклизм', 'damage', 32, 22, 30, 40, 0, 8, 5),
            ],
            'Некромант': [
                ('[ATK1]', 'Сгусток морока', 'damage', 12, 6, 11, 16, 0, 1, 1),
                ('[ATK2]', 'Разлом тени', 'damage', 16, 9, 15, 22, 0, 2, 2),
                ('[DEF1]', 'Костяной заслон', 'buff', 12, 10, 0, 0, 0, 3, 2),
                ('[DEF2]', 'Печать склепа', 'buff', 15, 13, 0, 0, 0, 4, 3),
                ('[REC]', 'Похищение жизни', 'heal', 16, 14, 0, 0, 25, 5, 3),
                ('[ULT]', 'Владыка праха', 'damage', 30, 22, 28, 38, 0, 8, 5),
            ],
            'Ледяной Маг': [
                ('[ATK1]', 'Ледяной осколок', 'damage', 11, 6, 10, 15, 0, 1, 1),
                ('[ATK2]', 'Морозный луч', 'damage', 15, 9, 15, 21, 0, 2, 2),
                ('[DEF1]', 'Хрустальный заслон', 'buff', 11, 10, 0, 0, 0, 3, 2),
                ('[DEF2]', 'Панцирь инея', 'buff', 14, 13, 0, 0, 0, 4, 3),
                ('[REC]', 'Стужа покоя', 'heal', 16, 14, 0, 0, 24, 5, 3),
                ('[ULT]', 'Сердце метели', 'damage', 30, 22, 27, 37, 0, 8, 5),
            ],
        }

        for race_name in race_list:
            for class_name, kit in race_class_ability_kits.items():
                class_id = fetch_val("SELECT id FROM character_classes WHERE name = %s LIMIT 1", class_name)
                if not class_id:
                    continue

                for tag, display_name, effect_type, mana_cost, cooldown, dmg_min, dmg_max, healing, lvl_req, req_quests in kit:
                    ability_name = f"{race_name} {class_name}: {tag} {display_name}"
                    ability_desc = f"{race_name} {class_name} - {display_name}"
                    execute(
                        """
                        INSERT INTO abilities (
                            name, description, ability_type, class_id, level_requirement,
                            mana_cost, cooldown, damage_min, damage_max, healing, effect_type, range_m
                        )
                        SELECT %s, %s, 'skill', %s, %s, %s, %s, %s, %s, %s, %s, 12
                        WHERE NOT EXISTS (SELECT 1 FROM abilities WHERE name = %s)
                        """,
                        ability_name,
                        ability_desc,
                        class_id,
                        lvl_req,
                        mana_cost,
                        cooldown,
                        dmg_min,
                        dmg_max,
                        healing,
                        effect_type,
                        ability_name,
                    )

                    ability_id = fetch_val("SELECT id FROM abilities WHERE name = %s LIMIT 1", ability_name)
                    if ability_id:
                        execute(
                            """
                            INSERT INTO ability_skill_coin_costs (
                                ability_id, skill_coin_cost, class_id, unlocked_at_level, required_completed_quests
                            )
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (ability_id) DO UPDATE SET
                                skill_coin_cost = EXCLUDED.skill_coin_cost,
                                class_id = EXCLUDED.class_id,
                                unlocked_at_level = EXCLUDED.unlocked_at_level,
                                required_completed_quests = EXCLUDED.required_completed_quests
                            """,
                            ability_id,
                            10,
                            class_id,
                            lvl_req,
                            req_quests,
                        )
        
        obj_count = fetch_val("SELECT COUNT(*) FROM location_objects")
        if obj_count == 0:
            execute("""
                INSERT INTO location_objects (location_id, object_type, name, distance_km, interaction_type) VALUES 
                (1, 'building', 'Таверна "Золотой дракон"', 0.1, 'enter'),
                (1, 'npc', 'Охотник Раймонд', 0.05, 'talk'),
                (1, 'npc', 'Страж Тордек', 0.08, 'talk'),
                (1, 'npc', 'Собиратель Элиза', 0.12, 'talk'),
                (2, 'building', 'Охотничий домик', 0.2, 'enter'),
                (2, 'npc', 'Лесник', 0.15, 'talk'),
                (3, 'building', 'Древний храм', 0.5, 'enter'),
                (3, 'npc', 'Страж гор', 0.3, 'talk')
            """)
        
        # Add mobs to first location
        mob_count = fetch_val("SELECT COUNT(*) FROM mobs")
        if mob_count == 0:
            execute("""
                INSERT INTO mobs (name, level, health_points, max_health_points, damage_min, damage_max, armor_class, experience_reward, gold_reward, location_id, mob_type, aggression_type, respawn_time) VALUES 
                ('Кролик', 1, 20, 20, 2, 4, 0, 5, 1, 1, 'animal', 'passive', 60),
                ('Волк', 2, 35, 35, 5, 8, 2, 15, 3, 1, 'animal', 'aggressive', 120),
                ('Гоблин', 3, 50, 50, 7, 12, 3, 25, 5, 1, 'humanoid', 'aggressive', 180),
                ('Лесной волк', 2, 40, 40, 6, 9, 1, 18, 4, 2, 'animal', 'aggressive', 120),
                ('Огр', 3, 80, 80, 10, 15, 5, 35, 8, 2, 'giant', 'aggressive', 300),
                ('Лис', 1, 25, 25, 3, 5, 1, 8, 2, 1, 'animal', 'passive', 90)
            """)

        # Wolf progression variants for hunting content.
        execute("""
            INSERT INTO mobs (name, level, health_points, max_health_points, damage_min, damage_max, armor_class, experience_reward, gold_reward, location_id, mob_type, aggression_type, respawn_time)
            SELECT 'Старый волк', 2, 32, 32, 4, 7, 1, 12, 2, 2, 'animal', 'aggressive', 120
            WHERE NOT EXISTS (SELECT 1 FROM mobs WHERE name = 'Старый волк' AND location_id = 2)
        """)
        execute("""
            INSERT INTO mobs (name, level, health_points, max_health_points, damage_min, damage_max, armor_class, experience_reward, gold_reward, location_id, mob_type, aggression_type, respawn_time)
            SELECT 'Молодой волк', 3, 48, 48, 7, 11, 2, 20, 4, 2, 'animal', 'aggressive', 130
            WHERE NOT EXISTS (SELECT 1 FROM mobs WHERE name = 'Молодой волк' AND location_id = 2)
        """)
        execute("""
            INSERT INTO mobs (name, level, health_points, max_health_points, damage_min, damage_max, armor_class, experience_reward, gold_reward, location_id, mob_type, aggression_type, respawn_time)
            SELECT 'Матерый волк', 5, 88, 88, 13, 19, 5, 42, 10, 2, 'animal', 'aggressive', 180
            WHERE NOT EXISTS (SELECT 1 FROM mobs WHERE name = 'Матерый волк' AND location_id = 2)
        """)
        execute("""
            INSERT INTO mobs (name, level, health_points, max_health_points, damage_min, damage_max, armor_class, experience_reward, gold_reward, location_id, mob_type, aggression_type, respawn_time)
            SELECT 'Вожак волков', 8, 180, 180, 22, 34, 10, 110, 30, 2, 'animal', 'aggressive', 360
            WHERE NOT EXISTS (SELECT 1 FROM mobs WHERE name = 'Вожак волков' AND location_id = 2)
        """)
        
        # Create mob spawn zones (EVE Online style with distances)
        spawn_zone_count = fetch_val("SELECT COUNT(*) FROM mob_spawn_zones WHERE location_id IN (1,2,3)")
        if spawn_zone_count < 8:
            execute("""
                INSERT INTO mob_spawn_zones (location_id, zone_name, zone_type, distance_from_center, position_x, position_y, position_z, radius, min_level, max_level, is_aggressive_zone, respawn_timer, max_mobs) VALUES 
                -- City zones (Элдория - location 1)
                (1, 'Рыночная площадь', 'city', 0, 0, 0, 0, 30, 1, 1, FALSE, 0, 0),
                (1, 'Корчма "Золотой кубок"', 'city', 10, 10, 5, 0, 20, 1, 1, FALSE, 0, 0),
                (1, 'Лавка ремесленника', 'city', 15, 15, 10, 0, 20, 1, 1, FALSE, 0, 0),
                (1, 'Оружейная мастерская', 'city', 20, 5, 15, 0, 20, 1, 1, FALSE, 0, 0),
                (1, 'Палатка алхимика', 'city', 25, 20, 20, 0, 20, 1, 1, FALSE, 0, 0),
                (1, 'Крафтовый квартал', 'city', 35, 30, 15, 0, 24, 1, 2, FALSE, 0, 0),
                
                -- Hunting zones near city (Лес Охотников - location 2)
                (2, 'Лесная деревня', 'city', 20, 18, 12, 0, 22, 1, 2, FALSE, 0, 0),
                (2, 'Поляна с кроликами', 'hunting', 30, 30, 30, 0, 20, 1, 1, FALSE, 60, 8),
                (2, 'Логово лис', 'hunting', 75, 75, 50, 0, 25, 1, 2, FALSE, 90, 6),
                (2, 'Волчий лес', 'hunting', 150, 100, 100, 0, 30, 2, 8, TRUE, 120, 5),
                (2, 'Лагерь гоблинов', 'hunting', 200, 150, 80, 0, 40, 3, 4, TRUE, 180, 8),
                
                -- Gathering zones (Горные пещеры - location 3)
                (3, 'Шахтерский поселок', 'city', 25, 20, 18, 0, 24, 1, 2, FALSE, 0, 0),
                (3, 'Железные жилы', 'resource', 50, 50, 50, 0, 30, 1, 2, FALSE, 0, 0),
                (3, 'Медные залежи', 'resource', 80, 100, 70, 0, 25, 1, 1, FALSE, 0, 0),
                (3, 'Пещерный лес', 'resource', 100, 30, 100, 0, 40, 2, 3, TRUE, 120, 6),
                (3, 'Кристальные образования', 'resource', 150, 150, 150, 0, 35, 3, 4, TRUE, 180, 4)
            """)

        if (fetch_val("SELECT COUNT(*) FROM mob_spawn_zones WHERE location_id = 2 AND zone_name = 'Лесная деревня'") or 0) == 0:
            execute(
                """
                INSERT INTO mob_spawn_zones
                    (location_id, zone_name, zone_type, distance_from_center, position_x, position_y, position_z, radius, min_level, max_level, is_aggressive_zone, respawn_timer, max_mobs)
                VALUES (2, 'Лесная деревня', 'city', 20, 18, 12, 0, 22, 1, 2, FALSE, 0, 0)
                """
            )

        if (fetch_val("SELECT COUNT(*) FROM mob_spawn_zones WHERE location_id = 3 AND zone_name = 'Шахтерский поселок'") or 0) == 0:
            execute(
                """
                INSERT INTO mob_spawn_zones
                    (location_id, zone_name, zone_type, distance_from_center, position_x, position_y, position_z, radius, min_level, max_level, is_aggressive_zone, respawn_timer, max_mobs)
                VALUES (3, 'Шахтерский поселок', 'city', 25, 20, 18, 0, 24, 1, 2, FALSE, 0, 0)
                """
            )

        # Ensure crafting district exists for older databases.
        if (fetch_val("SELECT COUNT(*) FROM mob_spawn_zones WHERE location_id = 1 AND zone_name = 'Крафтовый квартал'") or 0) == 0:
            execute("""
                INSERT INTO mob_spawn_zones
                    (location_id, zone_name, zone_type, distance_from_center, position_x, position_y, position_z, radius, min_level, max_level, is_aggressive_zone, respawn_timer, max_mobs)
                VALUES (1, 'Крафтовый квартал', 'city', 35, 30, 15, 0, 24, 1, 2, FALSE, 0, 0)
            """)
            
            # Link mobs to spawn zones (safe join: only existing mobs/zones are inserted)
            execute("""
                INSERT INTO mob_zone_spawns (spawn_zone_id, mob_id, spawn_chance, min_count, max_count, is_champion_spawn, champion_chance)
                SELECT z.id, m.id, v.spawn_chance, v.min_count, v.max_count, v.is_champion_spawn, v.champion_chance
                FROM (
                    VALUES
                        ('Поляна с кроликами', 2, 'Кролик', 1.0, 5, 8, FALSE, 0.0),
                        ('Логово лис', 2, 'Лис', 1.0, 3, 5, TRUE, 0.08),
                        ('Волчий лес', 2, 'Лесной волк', 1.0, 2, 4, TRUE, 0.12),
                        ('Лагерь гоблинов', 2, 'Гоблин', 1.0, 4, 7, TRUE, 0.15),
                        ('Пещерный лес', 3, 'Огр', 1.0, 2, 4, TRUE, 0.20)
                ) AS v(zone_name, location_id, mob_name, spawn_chance, min_count, max_count, is_champion_spawn, champion_chance)
                JOIN mob_spawn_zones z ON z.zone_name = v.zone_name AND z.location_id = v.location_id
                JOIN mobs m ON m.name = v.mob_name
                WHERE NOT EXISTS (
                    SELECT 1 FROM mob_zone_spawns s
                    WHERE s.spawn_zone_id = z.id AND s.mob_id = m.id
                )
            """)

        # Fallback for old databases: guarantee at least starter zones in city and hunting area
        if fetch_val("SELECT COUNT(*) FROM mob_spawn_zones WHERE location_id = 1") == 0:
            execute("""
                INSERT INTO mob_spawn_zones (location_id, zone_name, zone_type, distance_from_center, position_x, position_y, radius, min_level, max_level, is_aggressive_zone, respawn_timer, max_mobs) VALUES
                (1, 'Рыночная площадь', 'city', 0, 0, 0, 30, 1, 1, FALSE, 0, 0),
                (1, 'Корчма "Золотой кубок"', 'city', 10, 10, 5, 20, 1, 1, FALSE, 0, 0)
            """)

        if fetch_val("SELECT COUNT(*) FROM mob_spawn_zones WHERE location_id = 2") == 0:
            execute("""
                INSERT INTO mob_spawn_zones (location_id, zone_name, zone_type, distance_from_center, position_x, position_y, radius, min_level, max_level, is_aggressive_zone, respawn_timer, max_mobs) VALUES
                (2, 'Поляна с кроликами', 'hunting', 30, 30, 30, 20, 1, 1, FALSE, 60, 8),
                (2, 'Логово лис', 'hunting', 75, 75, 50, 25, 1, 2, FALSE, 90, 6)
            """)

        execute(
            """
            INSERT INTO mob_zone_spawns (spawn_zone_id, mob_id, spawn_chance, min_count, max_count, is_champion_spawn, champion_chance)
            SELECT z.id, m.id, v.spawn_chance, v.min_count, v.max_count, v.is_champion_spawn, v.champion_chance
            FROM (
                VALUES
                    ('Поляна с кроликами', 2, 'Кролик', 1.0, 5, 8, FALSE, 0.0),
                    ('Логово лис', 2, 'Лис', 1.0, 3, 5, TRUE, 0.08),
                    ('Волчий лес', 2, 'Старый волк', 1.0, 2, 4, FALSE, 0.0),
                    ('Волчий лес', 2, 'Молодой волк', 0.85, 2, 3, TRUE, 0.06),
                    ('Волчий лес', 2, 'Матерый волк', 0.55, 1, 2, TRUE, 0.10),
                    ('Волчий лес', 2, 'Вожак волков', 0.20, 1, 1, TRUE, 0.15),
                    ('Лагерь гоблинов', 2, 'Гоблин', 1.0, 4, 7, TRUE, 0.15),
                    ('Пещерный лес', 3, 'Огр', 1.0, 2, 4, TRUE, 0.20)
            ) AS v(zone_name, location_id, mob_name, spawn_chance, min_count, max_count, is_champion_spawn, champion_chance)
            JOIN mob_spawn_zones z ON z.zone_name = v.zone_name AND z.location_id = v.location_id
            JOIN mobs m ON m.name = v.mob_name AND m.location_id = v.location_id
            WHERE NOT EXISTS (
                SELECT 1 FROM mob_zone_spawns s
                WHERE s.spawn_zone_id = z.id AND s.mob_id = m.id
            )
            """
        )
        
        # Add items (материалы для разделки и т.д.)
        items_count = fetch_val("SELECT COUNT(*) FROM items")
        if items_count == 0:
            execute("""
                INSERT INTO items (name, item_type, description, rarity, weight, value) VALUES 
                ('Лисья шкура', 'material', 'Пушистая шкура лисы', 'common', 0.5, 10),
                ('Лисья кость', 'material', 'Крепкая кость лисы', 'common', 0.2, 5),
                ('Зуб волка', 'material', 'Острый зуб волка', 'common', 0.1, 8),
                ('Волчья шкура', 'material', 'Толстая волчья шкура', 'uncommon', 0.8, 15),
                ('Кожа гоблина', 'material', 'Зеленоватая кожа гоблина', 'common', 0.6, 12),
                ('Коготь гоблина', 'material', 'Острый коготь гоблина', 'common', 0.1, 7),
                ('Шкура огра', 'material', 'Очень толстая и прочная', 'rare', 2.0, 50),
                ('Позвонок огра', 'material', 'Огромный позвонок', 'rare', 0.5, 30)
            """)

        # Ensure starter butchering materials exist on legacy databases too.
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value)
            SELECT 'Лисья шкура', 'material', 'Пушистая шкура лисы', 'common', 0.5, 10
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Лисья шкура')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value)
            SELECT 'Лисья кость', 'material', 'Крепкая кость лисы', 'common', 0.2, 5
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Лисья кость')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value)
            SELECT 'Зуб волка', 'material', 'Острый зуб волка', 'common', 0.1, 8
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Зуб волка')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value)
            SELECT 'Волчья шкура', 'material', 'Толстая волчья шкура', 'uncommon', 0.8, 15
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Волчья шкура')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value)
            SELECT 'Кожа гоблина', 'material', 'Зеленоватая кожа гоблина', 'common', 0.6, 12
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Кожа гоблина')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value)
            SELECT 'Коготь гоблина', 'material', 'Острый коготь гоблина', 'common', 0.1, 7
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Коготь гоблина')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value)
            SELECT 'Шкура огра', 'material', 'Очень толстая и прочная', 'rare', 2.0, 50
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Шкура огра')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value)
            SELECT 'Позвонок огра', 'material', 'Огромный позвонок', 'rare', 0.5, 30
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Позвонок огра')
        """)

        # Ensure starter consumables and starter gear exist for first character experience.
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value, damage_min, damage_max)
            SELECT 'Учебный меч', 'weapon', 'Простой учебный меч для первых боев', 'common', 1.2, 20, 3, 5
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Учебный меч')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value, damage_min, damage_max)
            SELECT 'Учебный двуручный меч', 'two_handed_weapon', 'Базовый двуручный меч для мили-классов', 'common', 2.2, 24, 4, 7
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Учебный двуручный меч')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value, armor_class)
            SELECT 'Учебный щит', 'shield', 'Простой щит для начальной защиты', 'common', 1.8, 16, 1
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Учебный щит')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value, damage_min, damage_max)
            SELECT 'Учебный посох', 'two_handed_weapon', 'Начальный посох для магических классов', 'common', 1.6, 22, 3, 6
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Учебный посох')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value, damage_min, damage_max)
            SELECT 'Учебный лук', 'two_handed_weapon', 'Базовый лук для дальнего боя', 'common', 1.4, 21, 3, 6
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Учебный лук')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value, armor_class)
            SELECT 'Потрепанная куртка', 'armor', 'Легкая куртка новичка', 'common', 1.0, 18, 1
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Потрепанная куртка')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value, health_recovery)
            SELECT 'Малое зелье лечения', 'consumable', 'Восстанавливает немного здоровья', 'common', 0.3, 12, 25
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Малое зелье лечения')
        """)

        # Backfill starter pack for previously created characters.
        starter_item_names = {
            'Малое зелье лечения': 3,
        }
        for item_name, required_qty in starter_item_names.items():
            item_id = fetch_val("SELECT id FROM items WHERE name = %s LIMIT 1", item_name)
            if not item_id:
                continue
            execute(
                """
                UPDATE inventory inv
                SET quantity = GREATEST(COALESCE(inv.quantity, 0), %s)
                WHERE inv.item_id = %s
                  AND inv.slot IS NULL
                  AND inv.character_id IN (SELECT id FROM characters)
                """,
                int(required_qty),
                int(item_id),
            )
            execute(
                """
                INSERT INTO inventory (character_id, item_id, quantity, equipped, slot)
                SELECT c.id, %s, %s, FALSE, NULL
                FROM characters c
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM inventory inv
                    WHERE inv.character_id = c.id
                      AND inv.item_id = %s
                      AND inv.slot IS NULL
                )
                """,
                int(item_id),
                int(required_qty),
                int(item_id),
            )

        # Vendor armor sets (mage robe, light, heavy) with ascending stats and silver prices.
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value, armor_class)
            SELECT 'Роба ученика', 'armor', 'Сет мага T1: +магическая устойчивость, +восстановление маны', 'common', 1.0, 10, 1
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Роба ученика')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value, armor_class)
            SELECT 'Роба адепта', 'armor', 'Сет мага T2: выше магическая защита и контроль маны', 'common', 1.2, 20, 2
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Роба адепта')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value, armor_class)
            SELECT 'Роба арканиста', 'armor', 'Сет мага T3: повышенная маг. защита и стабильность каста', 'uncommon', 1.4, 35, 3
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Роба арканиста')
        """)

        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value, armor_class)
            SELECT 'Легкий кожаный доспех', 'armor', 'Легкая броня T1: скорость атаки, уклонение и шанс крита', 'common', 1.1, 12, 1
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Легкий кожаный доспех')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value, armor_class)
            SELECT 'Легкий охотничий доспех', 'armor', 'Легкая броня T2: лучшее уклонение и точность для дальнего боя', 'common', 1.3, 24, 2
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Легкий охотничий доспех')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value, armor_class)
            SELECT 'Легкий доспех следопыта', 'armor', 'Легкая броня T3: максимальная мобильность и высокий крит-потенциал', 'uncommon', 1.6, 38, 3
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Легкий доспех следопыта')
        """)

        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value, armor_class)
            SELECT 'Тяжелый панцирь рекрута', 'armor', 'Тяжелая броня T1: физическая защита и снижение входящего крита', 'common', 2.8, 15, 2
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Тяжелый панцирь рекрута')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value, armor_class)
            SELECT 'Тяжелый панцирь стража', 'armor', 'Тяжелая броня T2: усиленная физ. защита и стойкость к контролю', 'common', 3.2, 28, 3
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Тяжелый панцирь стража')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value, armor_class)
            SELECT 'Тяжелый панцирь бастиона', 'armor', 'Тяжелая броня T3: максимум защиты и снижение критического урона', 'uncommon', 3.6, 45, 4
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Тяжелый панцирь бастиона')
        """)

        # Vendor one-handed swords with ascending stats.
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value, damage_min, damage_max)
            SELECT 'Деревянный одноручный меч', 'weapon', 'T1 одноручный меч: базовое оружие новичка', 'common', 1.0, 10, 3, 5
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Деревянный одноручный меч')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value, damage_min, damage_max)
            SELECT 'Костяной одноручный меч', 'weapon', 'T2 одноручный меч: усиленный клинок из кости', 'common', 1.2, 22, 5, 8
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Костяной одноручный меч')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value, damage_min, damage_max)
            SELECT 'Каменный одноручный меч', 'weapon', 'T3 одноручный меч: тяжелый клинок с высоким уроном', 'uncommon', 1.5, 36, 7, 11
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Каменный одноручный меч')
        """)
        
        # Add loot tables
        loot_table_count = fetch_val("SELECT COUNT(*) FROM loot_tables")
        if loot_table_count == 0:
            execute("""
                INSERT INTO loot_tables (name, description) VALUES 
                ('Лис', 'Лут от убитых лис'),
                ('Волков', 'Лут от убитых волков'),
                ('Гоблинов', 'Лут от убитых гоблинов'),
                ('Огров', 'Лут от убитых огров')
            """)
            
            # Добавим лут для каждой таблицы
            execute("""
                INSERT INTO loot_items (loot_table_id, item_id, drop_chance, min_quantity, max_quantity) VALUES 
                (1, 1, 80.0, 1, 2),   -- Лисья шкура 80% шанс
                (1, 2, 50.0, 1, 1),   -- Лисья кость 50% шанс
                (2, 4, 70.0, 1, 1),   -- Волчья шкура 70%
                (2, 3, 60.0, 1, 3),   -- Зуб волка 60%
                (3, 5, 75.0, 1, 2),   -- Кожа гоблина 75%
                (3, 6, 40.0, 1, 2),   -- Коготь гоблина 40%
                (4, 7, 90.0, 1, 1),   -- Шкура огра 90%
                (4, 8, 85.0, 1, 1)    -- Позвонок огра 85%
            """)

        # Populate loot items for legacy DBs where loot_tables exist but loot_items is empty.
        if (fetch_val("SELECT COUNT(*) FROM loot_items") or 0) == 0:
            fox_table_id = fetch_val("SELECT id FROM loot_tables WHERE name = 'Лис' LIMIT 1")
            wolf_table_id = fetch_val("SELECT id FROM loot_tables WHERE name = 'Волков' LIMIT 1")
            goblin_table_id = fetch_val("SELECT id FROM loot_tables WHERE name = 'Гоблинов' LIMIT 1")
            ogre_table_id = fetch_val("SELECT id FROM loot_tables WHERE name = 'Огров' LIMIT 1")

            fox_hide_id = fetch_val("SELECT id FROM items WHERE name = 'Лисья шкура' LIMIT 1")
            fox_bone_id = fetch_val("SELECT id FROM items WHERE name = 'Лисья кость' LIMIT 1")
            wolf_tooth_id = fetch_val("SELECT id FROM items WHERE name = 'Зуб волка' LIMIT 1")
            wolf_hide_id = fetch_val("SELECT id FROM items WHERE name = 'Волчья шкура' LIMIT 1")
            goblin_skin_id = fetch_val("SELECT id FROM items WHERE name = 'Кожа гоблина' LIMIT 1")
            goblin_claw_id = fetch_val("SELECT id FROM items WHERE name = 'Коготь гоблина' LIMIT 1")
            ogre_hide_id = fetch_val("SELECT id FROM items WHERE name = 'Шкура огра' LIMIT 1")
            ogre_spine_id = fetch_val("SELECT id FROM items WHERE name = 'Позвонок огра' LIMIT 1")

            loot_rows = [
                (fox_table_id, fox_hide_id, 80.0, 1, 2),
                (fox_table_id, fox_bone_id, 50.0, 1, 1),
                (wolf_table_id, wolf_hide_id, 70.0, 1, 1),
                (wolf_table_id, wolf_tooth_id, 60.0, 1, 3),
                (goblin_table_id, goblin_skin_id, 75.0, 1, 2),
                (goblin_table_id, goblin_claw_id, 40.0, 1, 2),
                (ogre_table_id, ogre_hide_id, 90.0, 1, 1),
                (ogre_table_id, ogre_spine_id, 85.0, 1, 1),
            ]

            for table_id, item_id, chance, min_qty, max_qty in loot_rows:
                if table_id and item_id:
                    execute(
                        """
                        INSERT INTO loot_items (loot_table_id, item_id, drop_chance, min_quantity, max_quantity)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        table_id,
                        item_id,
                        chance,
                        min_qty,
                        max_qty,
                    )

        # Ensure starter-zone mobs are linked with loot tables.
        execute("""
            UPDATE mobs
            SET loot_table_id = (SELECT id FROM loot_tables WHERE name = 'Лис' LIMIT 1)
            WHERE name = 'Лис' AND location_id IN (1, 2)
        """)
        execute("""
            UPDATE mobs
            SET loot_table_id = (SELECT id FROM loot_tables WHERE name = 'Лис' LIMIT 1)
            WHERE name = 'Кролик' AND location_id IN (1, 2)
        """)
        execute("""
            UPDATE mobs
            SET loot_table_id = (SELECT id FROM loot_tables WHERE name = 'Волков' LIMIT 1)
            WHERE name IN ('Волк', 'Лесной волк') AND location_id IN (1, 2)
        """)
        execute("""
            UPDATE mobs
            SET loot_table_id = (SELECT id FROM loot_tables WHERE name = 'Гоблинов' LIMIT 1)
            WHERE name = 'Гоблин' AND location_id IN (1, 2)
        """)

        # Add beginner craft result items if missing.
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value, armor_class)
            SELECT 'Кожаные перчатки новичка', 'armor', 'Простые перчатки из шкур', 'common', 0.4, 25, 1
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Кожаные перчатки новичка')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value, armor_class)
            SELECT 'Кожаная куртка новичка', 'armor', 'Легкая куртка из шкур для начинающих', 'common', 1.4, 55, 2
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Кожаная куртка новичка')
        """)
        execute("""
            INSERT INTO items (name, item_type, description, rarity, weight, value, damage_min, damage_max)
            SELECT 'Костяной кинжал', 'weapon', 'Грубый кинжал из кости', 'common', 0.8, 45, 4, 7
            WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Костяной кинжал')
        """)

        # Ensure beginner crafting recipes exist (materials from starter mobs).
        fox_hide_id = fetch_val("SELECT id FROM items WHERE name = 'Лисья шкура' LIMIT 1")
        fox_bone_id = fetch_val("SELECT id FROM items WHERE name = 'Лисья кость' LIMIT 1")
        wolf_tooth_id = fetch_val("SELECT id FROM items WHERE name = 'Зуб волка' LIMIT 1")
        wolf_hide_id = fetch_val("SELECT id FROM items WHERE name = 'Волчья шкура' LIMIT 1")
        ogre_hide_id = fetch_val("SELECT id FROM items WHERE name = 'Шкура огра' LIMIT 1")
        gloves_id = fetch_val("SELECT id FROM items WHERE name = 'Кожаные перчатки новичка' LIMIT 1")
        jacket_id = fetch_val("SELECT id FROM items WHERE name = 'Кожаная куртка новичка' LIMIT 1")
        dagger_id = fetch_val("SELECT id FROM items WHERE name = 'Костяной кинжал' LIMIT 1")

        if fox_hide_id and gloves_id:
            materials = f'[{"{"}"item_id": {fox_hide_id}, "quantity": 2{"}"}]'
            exists = fetch_val("SELECT id FROM crafting_recipes WHERE result_item_id = %s LIMIT 1", gloves_id)
            if not exists:
                execute(
                    """
                    INSERT INTO crafting_recipes
                        (result_item_id, result_quantity, crafting_type, required_skill_level, required_materials, crafting_time_seconds, success_rate)
                    VALUES (%s, 1, 'tailoring', 1, %s, 10, 95)
                    """,
                    gloves_id,
                    materials,
                )

        if fox_hide_id and wolf_hide_id and jacket_id:
            materials = (
                f'[{"{"}"item_id": {fox_hide_id}, "quantity": 2{"}"}, '
                f'{{"item_id": {wolf_hide_id}, "quantity": 1}}]'
            )
            exists = fetch_val("SELECT id FROM crafting_recipes WHERE result_item_id = %s LIMIT 1", jacket_id)
            if not exists:
                execute(
                    """
                    INSERT INTO crafting_recipes
                        (result_item_id, result_quantity, crafting_type, required_skill_level, required_materials, crafting_time_seconds, success_rate)
                    VALUES (%s, 1, 'tailoring', 1, %s, 14, 90)
                    """,
                    jacket_id,
                    materials,
                )

        if fox_bone_id and wolf_tooth_id and dagger_id:
            materials = (
                f'[{"{"}"item_id": {fox_bone_id}, "quantity": 1{"}"}, '
                f'{{"item_id": {wolf_tooth_id}, "quantity": 2}}]'
            )
            exists = fetch_val("SELECT id FROM crafting_recipes WHERE result_item_id = %s LIMIT 1", dagger_id)
            if not exists:
                execute(
                    """
                    INSERT INTO crafting_recipes
                        (result_item_id, result_quantity, crafting_type, required_skill_level, required_materials, crafting_time_seconds, success_rate)
                    VALUES (%s, 1, 'blacksmith', 1, %s, 12, 92)
                    """,
                    dagger_id,
                    materials,
                )

        # Craft recipes for vendor gear: simple progression with familiar materials.
        wooden_sword_id = fetch_val("SELECT id FROM items WHERE name = 'Деревянный одноручный меч' LIMIT 1")
        bone_sword_id = fetch_val("SELECT id FROM items WHERE name = 'Костяной одноручный меч' LIMIT 1")
        stone_sword_id = fetch_val("SELECT id FROM items WHERE name = 'Каменный одноручный меч' LIMIT 1")
        ogre_spine_id = fetch_val("SELECT id FROM items WHERE name = 'Позвонок огра' LIMIT 1")

        robe_t1_id = fetch_val("SELECT id FROM items WHERE name = 'Роба ученика' LIMIT 1")
        light_t1_id = fetch_val("SELECT id FROM items WHERE name = 'Легкий кожаный доспех' LIMIT 1")
        heavy_t1_id = fetch_val("SELECT id FROM items WHERE name = 'Тяжелый панцирь рекрута' LIMIT 1")

        if fox_bone_id and wooden_sword_id:
            materials = f'[{"{"}"item_id": {fox_bone_id}, "quantity": 2{"}"}]'
            exists = fetch_val("SELECT id FROM crafting_recipes WHERE result_item_id = %s LIMIT 1", wooden_sword_id)
            if not exists:
                execute(
                    """
                    INSERT INTO crafting_recipes
                        (result_item_id, result_quantity, crafting_type, required_skill_level, required_materials, crafting_time_seconds, success_rate)
                    VALUES (%s, 1, 'blacksmith', 1, %s, 8, 97)
                    """,
                    wooden_sword_id,
                    materials,
                )

        if fox_bone_id and wolf_tooth_id and bone_sword_id:
            materials = (
                f'[{"{"}"item_id": {fox_bone_id}, "quantity": 2{"}"}, '
                f'{{"item_id": {wolf_tooth_id}, "quantity": 2}}]'
            )
            exists = fetch_val("SELECT id FROM crafting_recipes WHERE result_item_id = %s LIMIT 1", bone_sword_id)
            if not exists:
                execute(
                    """
                    INSERT INTO crafting_recipes
                        (result_item_id, result_quantity, crafting_type, required_skill_level, required_materials, crafting_time_seconds, success_rate)
                    VALUES (%s, 1, 'blacksmith', 1, %s, 12, 92)
                    """,
                    bone_sword_id,
                    materials,
                )

        if wolf_tooth_id and ogre_spine_id and stone_sword_id:
            materials = (
                f'[{"{"}"item_id": {wolf_tooth_id}, "quantity": 3{"}"}, '
                f'{{"item_id": {ogre_spine_id}, "quantity": 1}}]'
            )
            exists = fetch_val("SELECT id FROM crafting_recipes WHERE result_item_id = %s LIMIT 1", stone_sword_id)
            if not exists:
                execute(
                    """
                    INSERT INTO crafting_recipes
                        (result_item_id, result_quantity, crafting_type, required_skill_level, required_materials, crafting_time_seconds, success_rate)
                    VALUES (%s, 1, 'blacksmith', 2, %s, 16, 86)
                    """,
                    stone_sword_id,
                    materials,
                )

        if fox_hide_id and robe_t1_id:
            materials = f'[{"{"}"item_id": {fox_hide_id}, "quantity": 3{"}"}]'
            exists = fetch_val("SELECT id FROM crafting_recipes WHERE result_item_id = %s LIMIT 1", robe_t1_id)
            if not exists:
                execute(
                    """
                    INSERT INTO crafting_recipes
                        (result_item_id, result_quantity, crafting_type, required_skill_level, required_materials, crafting_time_seconds, success_rate)
                    VALUES (%s, 1, 'tailoring', 1, %s, 10, 95)
                    """,
                    robe_t1_id,
                    materials,
                )

        if fox_hide_id and wolf_hide_id and light_t1_id:
            materials = (
                f'[{"{"}"item_id": {fox_hide_id}, "quantity": 2{"}"}, '
                f'{{"item_id": {wolf_hide_id}, "quantity": 1}}]'
            )
            exists = fetch_val("SELECT id FROM crafting_recipes WHERE result_item_id = %s LIMIT 1", light_t1_id)
            if not exists:
                execute(
                    """
                    INSERT INTO crafting_recipes
                        (result_item_id, result_quantity, crafting_type, required_skill_level, required_materials, crafting_time_seconds, success_rate)
                    VALUES (%s, 1, 'tailoring', 1, %s, 11, 93)
                    """,
                    light_t1_id,
                    materials,
                )

        if wolf_hide_id and ogre_hide_id and heavy_t1_id:
            materials = (
                f'[{"{"}"item_id": {wolf_hide_id}, "quantity": 2{"}"}, '
                f'{{"item_id": {ogre_hide_id}, "quantity": 1}}]'
            )
            exists = fetch_val("SELECT id FROM crafting_recipes WHERE result_item_id = %s LIMIT 1", heavy_t1_id)
            if not exists:
                execute(
                    """
                    INSERT INTO crafting_recipes
                        (result_item_id, result_quantity, crafting_type, required_skill_level, required_materials, crafting_time_seconds, success_rate)
                    VALUES (%s, 1, 'tailoring', 2, %s, 15, 85)
                    """,
                    heavy_t1_id,
                    materials,
                )
        
        # Add NPCs with quests
        quest_npcs_count = fetch_val("SELECT COUNT(*) FROM npcs WHERE location_id = 1")
        if quest_npcs_count < 5:
            # Delete any existing quests for these NPCs first (in case of duplicates from failed init)
            execute("""
                DELETE FROM quests WHERE id IN (
                    SELECT q.id FROM quests q JOIN npcs n ON q.npc_id = n.id 
                    WHERE n.name IN ('Охотник Раймонд', 'Страж Тордек', 'Собиратель Элиза', 'Торговец Маркус', 'Брокер Валериан')
                )
            """)
            
            # Delete any existing quest NPCs
            execute("""
                DELETE FROM npcs WHERE name IN ('Охотник Раймонд', 'Страж Тордек', 'Собиратель Элиза', 'Торговец Маркус', 'Брокер Валериан')
            """)
            
            # Now insert fresh quest NPCs and merchants in Элдория (location 1)
            execute("""
                INSERT INTO npcs (location_id, name, type, level, health_points, max_health_points, description, has_quest, position_x, position_y, distance_from_center) VALUES 
                -- Квестодатели
                (1, 'Охотник Раймонд', 'quest_giver', 5, 100, 100, 'Опытный охотник. Дает квесты на убийство животных', TRUE, 10, 10, 15),
                (1, 'Страж Тордек', 'quest_giver', 8, 150, 150, 'Боевой страж деревни. Защищает от бандитов', TRUE, 5, 5, 8),
                (1, 'Собиратель Элиза', 'quest_giver', 3, 80, 80, 'Занимается сбором ресурсов. Нужны материалы', TRUE, 15, 8, 18),
                -- Продавцы
                (1, 'Торговец Маркус', 'merchant', 10, 200, 200, 'Продает и покупает товары, оружие и броню', FALSE, 8, 12, 14),
                (1, 'Травница Миганела', 'merchant', 7, 100, 100, 'Продает зелья и травы', FALSE, 12, 18, 20),
                (1, 'Кузнец Грогварт', 'merchant', 12, 250, 250, 'Мастер оружия и брони. Покупает ресурсы', FALSE, 18, 2, 20),
                -- Брокер и банкир
                (1, 'Брокер Валериан', 'broker', 15, 250, 250, 'Аукционист. Торгует редкими предметами', FALSE, 20, 5, 21),
                (1, 'Банкир Лоян', 'merchant', 20, 300, 300, 'Хранит ваше золото и серебро', FALSE, 25, 25, 35)
            """)
            
            # Добавим квесты для охотника
            execute("""
                INSERT INTO quests (npc_id, title, description, quest_type, level_requirement, reward_experience, reward_gold, is_available) VALUES 
                ((SELECT id FROM npcs WHERE name = 'Охотник Раймонд' LIMIT 1), 
                 'Охота на кроликов', 
                 'Охотник просит убить 5 кроликов для мяса и шкур', 
                 'kill', 1, 300, 75, TRUE),
                ((SELECT id FROM npcs WHERE name = 'Охотник Раймонд' LIMIT 1), 
                 'Лисья охота', 
                 'Охотник просит убить 5 лис для их красивых шкур', 
                 'kill', 1, 400, 100, TRUE),
                ((SELECT id FROM npcs WHERE name = 'Охотник Раймонд' LIMIT 1), 
                 'Опасные волки', 
                 'Охотник просит убить 5 волков в окрестностях деревни', 
                 'kill', 2, 600, 150, TRUE)
            """)
            
            # Добавим квесты для стража
            execute("""
                INSERT INTO quests (npc_id, title, description, quest_type, level_requirement, reward_experience, reward_gold, is_available) VALUES 
                ((SELECT id FROM npcs WHERE name = 'Страж Тордек' LIMIT 1), 
                 'Защита от волков', 
                 'Волки атакуют караваны. Помоги стражу - убей 10 волков', 
                 'kill', 2, 800, 200, TRUE),
                ((SELECT id FROM npcs WHERE name = 'Страж Тордек' LIMIT 1), 
                 'Охота на гоблинов', 
                 'Гоблины совершают нападения. Убей 8 гоблинов за награду', 
                 'kill', 3, 1200, 300, TRUE)
            """)
            
            # Добавим квесты для собирателя Элизы
            execute("""
                INSERT INTO quests (npc_id, title, description, quest_type, level_requirement, reward_experience, reward_gold, is_available) VALUES 
                ((SELECT id FROM npcs WHERE name = 'Собиратель Элиза' LIMIT 1), 
                 'Собери цветы', 
                 'Мне нужны 20 целебных цветов. Найди их в лесу', 
                 'collect', 1, 250, 60, TRUE),
                ((SELECT id FROM npcs WHERE name = 'Собиратель Элиза' LIMIT 1), 
                 'Добыча трав', 
                 'Помоги собрать 15 лекарственных трав для зелий', 
                 'collect', 2, 400, 100, TRUE)
            """)
            
            # Добавим цели для квестов убийства
            execute("""
                INSERT INTO quest_kill_targets (quest_id, mob_id, required_count) VALUES 
                ((SELECT id FROM quests WHERE title = 'Охота на кроликов' LIMIT 1), 1, 5),
                ((SELECT id FROM quests WHERE title = 'Лисья охота' LIMIT 1), 6, 5),
                ((SELECT id FROM quests WHERE title = 'Опасные волки' LIMIT 1), 2, 5),
                ((SELECT id FROM quests WHERE title = 'Защита от волков' LIMIT 1), 2, 10),
                ((SELECT id FROM quests WHERE title = 'Охота на гоблинов' LIMIT 1), 3, 8)
            """)

        # Ensure core quests exist even when legacy DB already has many NPCs.
        execute("""
            INSERT INTO quests (npc_id, title, description, quest_type, level_requirement, reward_experience, reward_gold, is_available)
            SELECT n.id, 'Охота на кроликов', 'Охотник просит убить 5 кроликов для мяса и шкур', 'kill', 1, 300, 75, TRUE
            FROM npcs n
            WHERE n.name = 'Охотник Раймонд'
              AND NOT EXISTS (
                  SELECT 1 FROM quests q
                  WHERE q.npc_id = n.id AND q.title = 'Охота на кроликов'
              )
        """)
        execute("""
            INSERT INTO quests (npc_id, title, description, quest_type, level_requirement, reward_experience, reward_gold, is_available)
            SELECT n.id, 'Лисья охота', 'Охотник просит убить 5 лис для их красивых шкур', 'kill', 1, 400, 100, TRUE
            FROM npcs n
            WHERE n.name = 'Охотник Раймонд'
              AND NOT EXISTS (
                  SELECT 1 FROM quests q
                  WHERE q.npc_id = n.id AND q.title = 'Лисья охота'
              )
        """)
        execute("""
            INSERT INTO quests (npc_id, title, description, quest_type, level_requirement, reward_experience, reward_gold, is_available)
            SELECT n.id, 'Опасные волки', 'Охотник просит убить 5 волков в окрестностях деревни', 'kill', 2, 600, 150, TRUE
            FROM npcs n
            WHERE n.name = 'Охотник Раймонд'
              AND NOT EXISTS (
                  SELECT 1 FROM quests q
                  WHERE q.npc_id = n.id AND q.title = 'Опасные волки'
              )
        """)
        execute("""
            INSERT INTO quests (npc_id, title, description, quest_type, level_requirement, reward_experience, reward_gold, is_available)
            SELECT n.id, 'Защита от волков', 'Волки атакуют караваны. Помоги стражу - убей 10 волков', 'kill', 2, 800, 200, TRUE
            FROM npcs n
            WHERE n.name = 'Страж Тордек'
              AND NOT EXISTS (
                  SELECT 1 FROM quests q
                  WHERE q.npc_id = n.id AND q.title = 'Защита от волков'
              )
        """)
        execute("""
            INSERT INTO quests (npc_id, title, description, quest_type, level_requirement, reward_experience, reward_gold, is_available)
            SELECT n.id, 'Охота на гоблинов', 'Гоблины совершают нападения. Убей 8 гоблинов за награду', 'kill', 3, 1200, 300, TRUE
            FROM npcs n
            WHERE n.name = 'Страж Тордек'
              AND NOT EXISTS (
                  SELECT 1 FROM quests q
                  WHERE q.npc_id = n.id AND q.title = 'Охота на гоблинов'
              )
        """)

        # Ensure quest kill targets exist for starter kill quests.
        execute("""
            INSERT INTO quest_kill_targets (quest_id, mob_id, required_count)
            SELECT q.id, 1, 5
            FROM quests q
            WHERE q.title = 'Охота на кроликов'
              AND NOT EXISTS (
                  SELECT 1 FROM quest_kill_targets t WHERE t.quest_id = q.id AND t.mob_id = 1
              )
        """)
        execute("""
            INSERT INTO quest_kill_targets (quest_id, mob_id, required_count)
            SELECT q.id, 6, 5
            FROM quests q
            WHERE q.title = 'Лисья охота'
              AND NOT EXISTS (
                  SELECT 1 FROM quest_kill_targets t WHERE t.quest_id = q.id AND t.mob_id = 6
              )
        """)
        execute("""
            INSERT INTO quest_kill_targets (quest_id, mob_id, required_count)
            SELECT q.id, 2, 5
            FROM quests q
            WHERE q.title = 'Опасные волки'
              AND NOT EXISTS (
                  SELECT 1 FROM quest_kill_targets t WHERE t.quest_id = q.id AND t.mob_id = 2
              )
        """)
        execute("""
            INSERT INTO quest_kill_targets (quest_id, mob_id, required_count)
            SELECT q.id, 2, 10
            FROM quests q
            WHERE q.title = 'Защита от волков'
              AND NOT EXISTS (
                  SELECT 1 FROM quest_kill_targets t WHERE t.quest_id = q.id AND t.mob_id = 2
              )
        """)
        execute("""
            INSERT INTO quest_kill_targets (quest_id, mob_id, required_count)
            SELECT q.id, 3, 8
            FROM quests q
            WHERE q.title = 'Охота на гоблинов'
              AND NOT EXISTS (
                  SELECT 1 FROM quest_kill_targets t WHERE t.quest_id = q.id AND t.mob_id = 3
              )
        """)

        # Fallback for old databases: guarantee city NPCs
        if fetch_val("SELECT COUNT(*) FROM npcs WHERE location_id = 1") == 0:
            execute("""
                INSERT INTO npcs (location_id, name, type, level, health_points, max_health_points, description, has_quest, position_x, position_y, distance_from_center) VALUES
                (1, 'Охотник Раймонд', 'quest_giver', 5, 100, 100, 'Опытный охотник. Дает квесты', TRUE, 10, 10, 15),
                (1, 'Страж Тордек', 'quest_giver', 8, 150, 150, 'Страж города', TRUE, 5, 5, 8),
                (1, 'Собиратель Элиза', 'quest_giver', 3, 80, 80, 'Собирает ресурсы', TRUE, 15, 8, 18),
                (1, 'Торговец Маркус', 'merchant', 10, 200, 200, 'Продает и покупает товары', FALSE, 8, 12, 14),
                (1, 'Брокер Валериан', 'broker', 15, 250, 250, 'Аукционист', FALSE, 20, 5, 21)
            """)

        # Add crafting station NPCs in city if missing.
        crafting_stations = [
            ('Оружейный верстак', 32, 14, 35),
            ('Бронная наковальня', 45, 18, 48),
            ('Стол кожевника', 58, 22, 62),
            ('Лучный станок', 71, 26, 76),
            ('Щитовая стойка', 84, 30, 89),
        ]
        for station_name, px, py, dist in crafting_stations:
            execute(
                """
                INSERT INTO npcs (location_id, name, type, level, health_points, max_health_points, description, has_quest, position_x, position_y, distance_from_center)
                SELECT 1, %s, 'crafting_station', 1, 1, 1, 'Крафтовый станок для изготовления снаряжения', FALSE, %s, %s, %s
                WHERE NOT EXISTS (SELECT 1 FROM npcs WHERE location_id = 1 AND name = %s)
                """,
                station_name,
                px,
                py,
                dist,
                station_name,
            )

        # Normalize city NPC coordinates to avoid overlap (>=10m between key NPCs).
        execute("UPDATE npcs SET position_x = 10, position_y = 10, distance_from_center = 14 WHERE name = 'Охотник Раймонд' AND location_id = 1")
        execute("UPDATE npcs SET position_x = 22, position_y = 10, distance_from_center = 24 WHERE name = 'Страж Тордек' AND location_id = 1")
        execute("UPDATE npcs SET position_x = 34, position_y = 10, distance_from_center = 35 WHERE name = 'Собиратель Элиза' AND location_id = 1")
        execute("UPDATE npcs SET position_x = 46, position_y = 10, distance_from_center = 47 WHERE name = 'Торговец Маркус' AND location_id = 1")
        execute("UPDATE npcs SET position_x = 58, position_y = 10, distance_from_center = 59 WHERE name = 'Травница Миганела' AND location_id = 1")
        execute("UPDATE npcs SET position_x = 70, position_y = 10, distance_from_center = 71 WHERE name = 'Кузнец Грогварт' AND location_id = 1")
        execute("UPDATE npcs SET position_x = 82, position_y = 10, distance_from_center = 83 WHERE name = 'Брокер Валериан' AND location_id = 1")
        execute("UPDATE npcs SET position_x = 94, position_y = 10, distance_from_center = 95 WHERE name = 'Банкир Лоян' AND location_id = 1")
        
        # Add resource nodes (trees, ores)
        resource_count = fetch_val("SELECT COUNT(*) FROM npcs WHERE type IN ('tree', 'ore', 'herb')")
        if resource_count == 0:
            execute("""
                INSERT INTO npcs (location_id, name, type, level, health_points, max_health_points, description, has_quest, position_x, position_y, distance_from_center) VALUES 
                (1, 'Дубовое дерево', 'tree', 1, 50, 50, 'Крепкое дерево. Можно срубить топором', FALSE, 25, 30, 40),
                (1, 'Сосновое дерево', 'tree', 1, 40, 40, 'Высокая сосна. Дает древесину', FALSE, 30, 25, 38),
                (1, 'Березовое дерево', 'tree', 1, 35, 35, 'Белая береза. Легко рубится', FALSE, 35, 20, 42),
                (1, 'Железная руда', 'ore', 2, 80, 80, 'Залежи железной руды. Нужна кирка', FALSE, 60, 70, 92),
                (1, 'Медная руда', 'ore', 1, 60, 60, 'Медная жила. Легко добывается', FALSE, 55, 65, 85),
                (1, 'Кустарник с ягодами', 'herb', 1, 10, 10, 'Куст с целебными ягодами', FALSE, 18, 22, 28),
                (1, 'Лекарственная трава', 'herb', 1, 5, 5, 'Редкая трава с лечебными свойствами', FALSE, 22, 18, 30)
            """)
        
        # Инициализируем умения коинов
        ability_coins_count = fetch_val("SELECT COUNT(*) FROM ability_skill_coin_costs")
        if ability_coins_count == 0:
            # Получим все умения и добавим им стоимость в коинах
            execute("""
                INSERT INTO ability_skill_coin_costs (ability_id, skill_coin_cost, class_id, unlocked_at_level, required_completed_quests) 
                SELECT id, 10, class_id, GREATEST(COALESCE(level_requirement, 1), 1), 0
                FROM abilities
            """)

        # Ensure newly seeded abilities always have pricing rows.
        execute(
            """
            INSERT INTO ability_skill_coin_costs (ability_id, skill_coin_cost, class_id, unlocked_at_level, required_completed_quests)
            SELECT a.id,
                   10,
                   a.class_id,
                   COALESCE(a.level_requirement, 1),
                   0
            FROM abilities a
            WHERE NOT EXISTS (SELECT 1 FROM ability_skill_coin_costs c WHERE c.ability_id = a.id)
            """
        )
        
        # Ensure old characters without location are initialized, but keep existing coordinates intact.
        execute("""
            UPDATE characters
            SET current_location_id = COALESCE(current_location_id, 1),
                position_x = COALESCE(position_x, 0),
                position_y = COALESCE(position_y, 0)
            WHERE current_location_id IS NULL OR position_x IS NULL OR position_y IS NULL
        """)
        
        print("[OK] Test data initialized")
    except Exception as e:
        import traceback
        print(f"[WARNING] Database init failed: {e}")
        traceback.print_exc()
    
    print(f"[STARTED] {settings.APP_NAME} v{settings.APP_VERSION} запущен!")
    yield
    # SHUTDOWN: Отключение от БД
    await close_db_pool()
    print("[STOPPED] Приложение остановлено")


# === Создание приложения ===
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Text-based MMORPG API with mobile-first UI",
    lifespan=lifespan,
    docs_url="/api/docs",  # Swagger UI
    redoc_url="/api/redoc"  # ReDoc
)

# === CORS Middleware (разрешаем frontend доступ) ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Include game routes ===
app.include_router(game_router)
app.include_router(positioning_router, prefix='/api')
app.include_router(combat_router, prefix='/api')
app.include_router(party_router, prefix='/api')
app.include_router(ability_router, prefix='/api')


# === Простой health check ===
@app.get("/api/health")
async def health_check():
    """Проверка работоспособности API"""
    db_status = "disconnected"
    online_players = 0
    try:
        # Попробуем выполнить простейший запрос, если пул инициализирован
        val = fetch_val("SELECT 1")
        if val == 1:
            db_status = "connected"
            count = fetch_val("SELECT COUNT(*) FROM characters WHERE is_online = TRUE")
            online_players = int(count or 0)
    except Exception:
        db_status = "disconnected"
        online_players = 0
    return {
        "status": "online",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "online_players": online_players,
    }


# === Тест подключения к БД ===
@app.get("/api/test-db")
def test_database():
    """Тестовый запрос к базе данных"""
    try:
        # psycopg2 функции синхронные - без await
        count = fetch_val("SELECT COUNT(*) FROM users")
        return {
            "status": "ok",
            "users_count": count,
            "message": "Database connection successful"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


# === WebSocket менеджер (заглушка для MVP) ===
class ConnectionManager:
    """Управление WebSocket подключениями игроков"""
    
    def __init__(self):
        # {user_id: WebSocket}
        self.active_connections: dict = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """Подключение игрока"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        print(f"🔗 Player {user_id} connected via WebSocket")
    
    def disconnect(self, user_id: str):
        """Отключение игрока"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            print(f"🔌 Player {user_id} disconnected")
    
    async def send_personal_message(self, message: dict, user_id: str):
        """Отправка сообщения конкретному игроку"""
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json(message)
    
    async def broadcast_location(self, message: dict, location_id: int):
        """Рассылка сообщения всем игрокам в локации (заглушка)"""
        # TODO: реализовать фильтрацию по location_id
        for connection in self.active_connections.values():
            await connection.send_json(message)

# Глобальный экземпляр менеджера
manager = ConnectionManager()


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """
    WebSocket эндпоинт для real-time связи с клиентом.
    """
    # TODO: Добавить проверку JWT токена здесь
    await manager.connect(websocket, user_id)
    try:
        while True:
            # Получение сообщения от клиента
            data = await websocket.receive_json()
            
            # Эхо-ответ для тестирования (удалить в продакшене)
            await manager.send_personal_message(
                {"type": "echo", "received": data}, 
                user_id
            )
            
            # TODO: Здесь будет обработка команд:
            # - move: перемещение
            # - attack: атака
            # - chat: сообщение в чат
            # - interact: взаимодействие с объектом
    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception as e:
        print(f"❌ WebSocket error for {user_id}: {e}")
        manager.disconnect(user_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


# === Корневой эндпоинт ===
@app.get("/")
async def root():
    """Информация об API"""
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "docs": "/api/docs",
        "health": "/api/health",
        "websocket": "/ws/{user_id}"
    }