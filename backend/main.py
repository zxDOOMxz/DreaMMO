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
                END $$;
            """)
            print("[OK] Migration: character columns added/verified")
        except Exception as e:
            print(f"[WARNING] Migration failed: {e}")
        
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
                ('Человек', 'Сбалансированный старт: +1 ко всем характеристикам, +10 HP, +10 MP', 
                 1, 1, 1, 1, 1, 1, 10, 10)
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
                WHEN name IN ('Человека', 'Человек') THEN 'Сбалансированный старт: +1 ко всем характеристикам, +10 HP, +10 MP'
                ELSE description
            END
            WHERE name IN ('Гнома', 'Гном', 'Орка', 'Орк', 'Эльфа', 'Эльф', 'Человека', 'Человек')
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
                INSERT INTO character_classes (name, description, base_health, base_mana, health_per_level, mana_per_level, primary_stat) VALUES 
                ('Танк', 'Могучий защитник с высоким здоровьем и броней', 150, 40, 20, 4, 'constitution'),
                ('Воин', 'Боевой класс ближнего боя с балансом урона и защиты', 120, 50, 15, 5, 'strength'),
                ('Лучник', 'Стрелок дальнего боя с высокой скоростью атаки', 100, 60, 12, 6, 'dexterity'),
                ('Целитель', 'Лекарь с мощными исцеляющими заклинаниями', 90, 120, 10, 15, 'wisdom'),
                ('Маг Огня', 'Элементалист огня с разрушительными заклинаниями', 80, 130, 8, 17, 'intelligence'),
                ('Некромант', 'Повелитель мертвых с темными заклинаниями', 85, 125, 9, 16, 'intelligence'),
                ('Ледяной Маг', 'Маг холода с замораживающими заклинаниями', 82, 128, 8, 17, 'intelligence')
            ON CONFLICT (name) DO UPDATE SET
                description = EXCLUDED.description,
                base_health = EXCLUDED.base_health,
                base_mana = EXCLUDED.base_mana
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
        
        # Create mob spawn zones (EVE Online style with distances)
        spawn_zone_count = fetch_val("SELECT COUNT(*) FROM mob_spawn_zones WHERE location_id IN (1,2,3)")
        if spawn_zone_count < 8:
            execute("""
                INSERT INTO mob_spawn_zones (location_id, zone_name, zone_type, distance_from_center, position_x, position_y, radius, min_level, max_level, is_aggressive_zone, respawn_timer, max_mobs) VALUES 
                -- City zones (Элдория - location 1)
                (1, 'Рыночная площадь', 'city', 0, 0, 0, 30, 1, 1, FALSE, 0, 0),
                (1, 'Корчма "Золотой кубок"', 'city', 10, 10, 5, 20, 1, 1, FALSE, 0, 0),
                (1, 'Лавка ремесленника', 'city', 15, 15, 10, 20, 1, 1, FALSE, 0, 0),
                (1, 'Оружейная мастерская', 'city', 20, 5, 15, 20, 1, 1, FALSE, 0, 0),
                (1, 'Палатка алхимика', 'city', 25, 20, 20, 20, 1, 1, FALSE, 0, 0),
                
                -- Hunting zones near city (Лес Охотников - location 2)
                (2, 'Поляна с кроликами', 'pack', 30, 30, 30, 20, 1, 1, FALSE, 60, 8),
                (2, 'Логово лис', 'pack', 75, 75, 50, 25, 1, 2, FALSE, 90, 6),
                (2, 'Волчий лес', 'pack', 150, 100, 100, 30, 2, 3, TRUE, 120, 5),
                (2, 'Лагерь гоблинов', 'pack', 200, 150, 80, 40, 3, 4, TRUE, 180, 8),
                
                -- Gathering zones (Горные пещеры - location 3)
                (3, 'Железные жилы', 'resource', 50, 50, 50, 30, 1, 2, FALSE, 0, 0),
                (3, 'Медные залежи', 'resource', 80, 100, 70, 25, 1, 1, FALSE, 0, 0),
                (3, 'Пещерный лес', 'resource', 100, 30, 100, 40, 2, 3, TRUE, 120, 6),
                (3, 'Кристальные образования', 'resource', 150, 150, 150, 35, 3, 4, TRUE, 180, 4)
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
                (2, 'Поляна с кроликами', 'pack', 30, 30, 30, 20, 1, 1, FALSE, 60, 8),
                (2, 'Логово лис', 'pack', 75, 75, 50, 25, 1, 2, FALSE, 90, 6)
            """)
        
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
                INSERT INTO ability_skill_coin_costs (ability_id, skill_coin_cost, class_id, unlocked_at_level) 
                SELECT id, CASE 
                    WHEN level_requirement <= 1 THEN 0
                    WHEN level_requirement <= 3 THEN 50
                    ELSE 100
                END as cost, class_id, level_requirement
                FROM abilities
            """)
        
        # Ensure all characters have a spawn location (default to Элдория - location_id 1)
        # This fixes old characters without location
        execute("UPDATE characters SET current_location_id = 1, position_x = 0, position_y = 0")
        
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