-- ===== DREAMMO DATABASE SCHEMA =====
-- Text-based MMORPG with game mechanics
-- Last updated: 2026-03-04

-- ===== USERS & AUTHENTICATION =====
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- ===== CHARACTERS =====
CREATE TABLE IF NOT EXISTS characters (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(50) UNIQUE NOT NULL,
    level INTEGER DEFAULT 1,
    experience INTEGER DEFAULT 0,
    health_points INTEGER DEFAULT 100,
    max_health_points INTEGER DEFAULT 100,
    mana_points INTEGER DEFAULT 50,
    max_mana_points INTEGER DEFAULT 50,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_online TIMESTAMP,
    is_online BOOLEAN DEFAULT FALSE
);

-- ===== CHARACTER STATS (EVE Online style - основные параметры) =====
CREATE TABLE IF NOT EXISTS character_stats (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL UNIQUE REFERENCES characters(id) ON DELETE CASCADE,
    strength INTEGER DEFAULT 10,           -- Сила (урон в бою)
    dexterity INTEGER DEFAULT 10,          -- Ловкость (скорость бега, блок, точность)
    constitution INTEGER DEFAULT 10,       -- Выносливость (магазин HP, стамина)
    intelligence INTEGER DEFAULT 10,       -- Интеллект (магия, крафт)
    wisdom INTEGER DEFAULT 10,             -- Мудрость (рессурсосборка, ремонт)
    luck INTEGER DEFAULT 10,               -- Удача (крит удары, редкие дропы)
    stamina INTEGER DEFAULT 100,           -- Текущая выносливость для боя
    max_stamina INTEGER DEFAULT 100,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== LOCATIONS (как в EVE Online - таблица с объектами) =====
CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    region_id INTEGER,                    -- Регион (континент, система)
    location_type VARCHAR(50),            -- town, dungeon, wilderness, cave, etc.
    danger_level SMALLINT DEFAULT 0,      -- 0-10 опасность
    is_pvp_enabled BOOLEAN DEFAULT FALSE,
    capacity INTEGER DEFAULT 100,         -- Максимум игроков в локации
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== LOCATION OBJECTS (объекты в локциях как в EVE) =====
CREATE TABLE IF NOT EXISTS location_objects (
    id SERIAL PRIMARY KEY,
    location_id INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    object_type VARCHAR(50) NOT NULL,     -- npc, building, resource, dungeon_entrance, etc
    name VARCHAR(100) NOT NULL,
    description TEXT,
    distance_km INTEGER,                  -- Расстояние в км (как в EVE)
    is_interactive BOOLEAN DEFAULT TRUE,
    interaction_type VARCHAR(50),         -- talk, gather, enter, buy, sell, etc
    object_data_id INTEGER,               -- Ссылка на конкретный объект (NPC, Building, Resource)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== NPCs =====
CREATE TABLE IF NOT EXISTS npcs (
    id SERIAL PRIMARY KEY,
    location_id INTEGER NOT NULL REFERENCES locations(id) ON DELETE SET NULL,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50),                     -- merchant, quest_giver, guard, enemy, etc
    level INTEGER DEFAULT 1,
    health_points INTEGER DEFAULT 50,
    max_health_points INTEGER DEFAULT 50,
    description TEXT,
    dialogue_id INTEGER,                  -- Ссылка на диалоги
    has_quest BOOLEAN DEFAULT FALSE,
    faction_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== BUILDINGS =====
CREATE TABLE IF NOT EXISTS buildings (
    id SERIAL PRIMARY KEY,
    location_id INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    building_type VARCHAR(50),            -- shop, inn, bank, blacksmith, tavern, etc
    description TEXT,
    owner_player_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    can_loot BOOLEAN DEFAULT FALSE,
    locked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== ITEMS (предметы для крафта, боя, использования) =====
CREATE TABLE IF NOT EXISTS items (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    item_type VARCHAR(50),                -- weapon, armor, material, consumable, quest_item, etc
    description TEXT,
    rarity VARCHAR(20),                   -- common, uncommon, rare, epic, legendary
    weight DECIMAL(5,2),
    value INTEGER,                        -- Стоимость в золоте
    damage_min INTEGER,                   -- Для оружия
    damage_max INTEGER,
    armor_class INTEGER,                  -- Для брони
    health_recovery INTEGER,              -- Для зелий
    is_tradeable BOOLEAN DEFAULT TRUE,
    is_droppable BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== CHARACTER INVENTORY =====
CREATE TABLE IF NOT EXISTS inventory (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    quantity INTEGER DEFAULT 1,
    equipped BOOLEAN DEFAULT FALSE,
    slot VARCHAR(50),                     -- head, chest, legs, feet, hands, main_hand, off_hand, etc
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(character_id, item_id, slot)
);

-- ===== QUESTS (Квесты как в Mortal Online) =====
CREATE TABLE IF NOT EXISTS quests (
    id SERIAL PRIMARY KEY,
    npc_id INTEGER REFERENCES npcs(id) ON DELETE SET NULL,
    title VARCHAR(100) NOT NULL,
    description TEXT,
    quest_type VARCHAR(50),               -- kill, collect, deliver, explore, craft, etc
    level_requirement INTEGER DEFAULT 1,
    reward_experience INTEGER DEFAULT 0,
    reward_gold INTEGER DEFAULT 0,
    reward_item_id INTEGER REFERENCES items(id) ON DELETE SET NULL,
    completion_condition TEXT,            -- JSON с условиями завершения
    is_repeatable BOOLEAN DEFAULT FALSE,
    is_available BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== CHARACTER QUESTS (прогресс квестов) =====
CREATE TABLE IF NOT EXISTS character_quests (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    quest_id INTEGER NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
    status VARCHAR(50),                   -- active, completed, failed, abandoned
    progress_data TEXT,                   -- JSON с прогрессом (убийства, предметы и т.д.)
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    UNIQUE(character_id, quest_id)
);

-- ===== COMBAT LOG (Логирование боев) =====
CREATE TABLE IF NOT EXISTS combat_logs (
    id SERIAL PRIMARY KEY,
    initiator_id INTEGER REFERENCES characters(id) ON DELETE SET NULL,
    defender_id INTEGER REFERENCES characters(id) ON DELETE SET NULL,
    npc_id INTEGER REFERENCES npcs(id) ON DELETE SET NULL,
    location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    action_type VARCHAR(50),              -- attack, block, dodge, skill, item_use, etc
    damage_dealt INTEGER,
    damage_taken INTEGER,
    hit_location VARCHAR(50),             -- Куда попал удар (head, chest, legs, etc)
    block_status VARCHAR(20),             -- blocked, parried, hit, missed, critical
    action_description TEXT,              -- Подробное описание действия
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== CRAFTING RECIPES (Рецепты крафта) =====
CREATE TABLE IF NOT EXISTS crafting_recipes (
    id SERIAL PRIMARY KEY,
    result_item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    result_quantity INTEGER DEFAULT 1,
    crafting_type VARCHAR(50),            -- blacksmith, alchemy, tailoring, carpentry, etc
    required_skill_level INTEGER DEFAULT 1,
    required_materials TEXT,              -- JSON array с item_id и количеством
    crafting_time_seconds INTEGER DEFAULT 30,
    success_rate INTEGER DEFAULT 100,     -- Шанс успеха в процентах
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== CHARACTER CRAFTING (История крафта игрока) =====
CREATE TABLE IF NOT EXISTS character_crafting (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    recipe_id INTEGER NOT NULL REFERENCES crafting_recipes(id) ON DELETE CASCADE,
    skill_level INTEGER DEFAULT 1,        -- Уровень навыка крафта
    items_crafted INTEGER DEFAULT 0,      -- Сколько уже создал
    last_crafted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== RESOURCES (Ресурсы для добычи - уголь, руда и т.д.) =====
CREATE TABLE IF NOT EXISTS resources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),            -- ore, wood, plant, hide, etc
    location_id INTEGER REFERENCES locations(id) ON DELETE CASCADE,
    item_id INTEGER REFERENCES items(id) ON DELETE CASCADE,
    quantity INTEGER DEFAULT 10,
    max_quantity INTEGER DEFAULT 10,
    respawn_time_minutes INTEGER DEFAULT 30,
    difficulty_level INTEGER DEFAULT 1,   -- 1-10 сложность добычи
    required_tool VARCHAR(100),           -- pickaxe, axe, etc
    last_harvested_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== FACTIONS (Фракции для социального взаимодействия) =====
CREATE TABLE IF NOT EXISTS factions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    leader_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    members_count INTEGER DEFAULT 1
);

-- ===== CHARACTER FACTION MEMBERSHIP =====
CREATE TABLE IF NOT EXISTS faction_members (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    faction_id INTEGER NOT NULL REFERENCES factions(id) ON DELETE CASCADE,
    rank VARCHAR(50),                     -- member, elder, officer, leader, etc
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(character_id, faction_id)
);

-- ===== CHAT & SOCIAL =====
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    sender_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE SET NULL,
    chat_type VARCHAR(50),                -- global, location, faction, private, etc
    recipient_id INTEGER REFERENCES characters(id) ON DELETE SET NULL,
    location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    faction_id INTEGER REFERENCES factions(id) ON DELETE SET NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== PLAYER STATUS (Текущий статус игрока в игре) =====
CREATE TABLE IF NOT EXISTS player_status (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL UNIQUE REFERENCES characters(id) ON DELETE CASCADE,
    current_location_id INTEGER NOT NULL REFERENCES locations(id) ON DELETE SET NULL,
    status_type VARCHAR(50),              -- idle, in_combat, crafting, gathering, in_quest, etc
    status_data TEXT,                     -- JSON с доп информацией
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== FRIEND SYSTEM =====
CREATE TABLE IF NOT EXISTS friends (
    id SERIAL PRIMARY KEY,
    character_id_1 INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    character_id_2 INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    is_blocked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(character_id_1, character_id_2),
    CHECK (character_id_1 < character_id_2)
);

-- ===== INDEXES для оптимизации =====
CREATE INDEX idx_characters_user_id ON characters(user_id);
CREATE INDEX idx_characters_is_online ON characters(is_online);
CREATE INDEX idx_location_objects_location_id ON location_objects(location_id);
CREATE INDEX idx_npcs_location_id ON npcs(location_id);
CREATE INDEX idx_inventory_character_id ON inventory(character_id);
CREATE INDEX idx_character_quests_character_id ON character_quests(character_id);
CREATE INDEX idx_combat_logs_timestamp ON combat_logs(timestamp);
CREATE INDEX idx_chat_messages_created_at ON chat_messages(created_at);
CREATE INDEX idx_player_status_character_id ON player_status(character_id);
CREATE INDEX idx_faction_members_character_id ON faction_members(character_id);
