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

-- ===== CHARACTER CLASSES =====
CREATE TABLE IF NOT EXISTS character_classes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    base_health INTEGER DEFAULT 100,
    base_mana INTEGER DEFAULT 50,
    base_strength INTEGER DEFAULT 10,
    base_dexterity INTEGER DEFAULT 10,
    base_constitution INTEGER DEFAULT 10,
    base_intelligence INTEGER DEFAULT 10,
    base_wisdom INTEGER DEFAULT 10,
    base_luck INTEGER DEFAULT 10,
    health_per_level INTEGER DEFAULT 10,
    mana_per_level INTEGER DEFAULT 5,
    primary_stat VARCHAR(20),             -- strength, intelligence, dexterity
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== ABILITIES (умения и заклинания) =====
CREATE TABLE IF NOT EXISTS abilities (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    ability_type VARCHAR(20),             -- spell, skill, passive
    class_id INTEGER REFERENCES character_classes(id) ON DELETE CASCADE,
    level_requirement INTEGER DEFAULT 1,
    mana_cost INTEGER DEFAULT 0,
    cooldown INTEGER DEFAULT 0,           -- в секундах
    damage_min INTEGER DEFAULT 0,
    damage_max INTEGER DEFAULT 0,
    healing INTEGER DEFAULT 0,
    effect_type VARCHAR(50),              -- damage, heal, buff, debuff
    effect_duration INTEGER DEFAULT 0,    -- в секундах
    range_m INTEGER DEFAULT 1,            -- дальность действия
    is_aoe BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== RACES (Расы) =====
CREATE TABLE IF NOT EXISTS races (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    strength_bonus INTEGER DEFAULT 0,
    dexterity_bonus INTEGER DEFAULT 0,
    constitution_bonus INTEGER DEFAULT 0,
    intelligence_bonus INTEGER DEFAULT 0,
    wisdom_bonus INTEGER DEFAULT 0,
    luck_bonus INTEGER DEFAULT 0,
    health_bonus INTEGER DEFAULT 0,
    mana_bonus INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== RACE PASSIVE ABILITIES (Пассивные навыки рас) =====
CREATE TABLE IF NOT EXISTS race_passive_abilities (
    id SERIAL PRIMARY KEY,
    race_id INTEGER NOT NULL REFERENCES races(id) ON DELETE CASCADE,
    ability_id INTEGER NOT NULL REFERENCES abilities(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(race_id, ability_id)
);

-- ===== CHARACTERS =====
CREATE TABLE IF NOT EXISTS characters (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(50) UNIQUE NOT NULL,
    race_id INTEGER REFERENCES races(id) ON DELETE SET NULL,
    class_id INTEGER REFERENCES character_classes(id) ON DELETE SET NULL,
    level INTEGER DEFAULT 1,
    experience INTEGER DEFAULT 0,
    health_points INTEGER DEFAULT 100,
    max_health_points INTEGER DEFAULT 100,
    mana_points INTEGER DEFAULT 50,
    max_mana_points INTEGER DEFAULT 50,
    gold INTEGER DEFAULT 0,
    silver INTEGER DEFAULT 0,
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
    available_stat_points INTEGER DEFAULT 0,
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
    location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
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

-- ===== CHARACTER ABILITIES =====
CREATE TABLE IF NOT EXISTS character_abilities (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    ability_id INTEGER NOT NULL REFERENCES abilities(id) ON DELETE CASCADE,
    level INTEGER DEFAULT 1,
    cooldown_remaining INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(character_id, ability_id)
);

-- ===== MOBS (монстры) =====
CREATE TABLE IF NOT EXISTS mobs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    level INTEGER DEFAULT 1,
    health_points INTEGER DEFAULT 50,
    max_health_points INTEGER DEFAULT 50,
    damage_min INTEGER DEFAULT 5,
    damage_max INTEGER DEFAULT 10,
    armor_class INTEGER DEFAULT 0,
    experience_reward INTEGER DEFAULT 10,
    gold_reward INTEGER DEFAULT 5,
    location_id INTEGER REFERENCES locations(id) ON DELETE CASCADE,
    mob_type VARCHAR(50),                 -- animal, undead, demon, etc
    aggression_type VARCHAR(20),          -- passive, aggressive, defensive
    respawn_time INTEGER DEFAULT 300,     -- в секундах
    loot_table_id INTEGER,                -- ссылка на таблицу лута
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== COMBAT LOG =====
CREATE TABLE IF NOT EXISTS combat_log (
    id SERIAL PRIMARY KEY,
    character_id INTEGER REFERENCES characters(id) ON DELETE CASCADE,
    mob_id INTEGER REFERENCES mobs(id) ON DELETE CASCADE,
    action_type VARCHAR(50),              -- attack, spell, skill, defend
    ability_id INTEGER REFERENCES abilities(id) ON DELETE SET NULL,
    damage_dealt INTEGER DEFAULT 0,
    damage_taken INTEGER DEFAULT 0,
    healing_done INTEGER DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mob_aggro_targets (
    mob_id INTEGER PRIMARY KEY REFERENCES mobs(id) ON DELETE CASCADE,
    target_character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    aggro_mode VARCHAR(20) NOT NULL DEFAULT 'first_hit',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
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
    current_location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
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

-- ===== LOOT TABLES (Таблицы лутов для мобов) =====
CREATE TABLE IF NOT EXISTS loot_tables (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== LOOT ITEMS (Предметы в таблице лутов) =====
CREATE TABLE IF NOT EXISTS loot_items (
    id SERIAL PRIMARY KEY,
    loot_table_id INTEGER NOT NULL REFERENCES loot_tables(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    drop_chance DECIMAL(5,2) DEFAULT 50.00,  -- Шанс выпадения в процентах
    min_quantity INTEGER DEFAULT 1,
    max_quantity INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== MOB LOOT (Добытые предметы из мобов) =====
CREATE TABLE IF NOT EXISTS mob_loot (
    id SERIAL PRIMARY KEY,
    character_id INTEGER REFERENCES characters(id) ON DELETE CASCADE,
    mob_id INTEGER REFERENCES mobs(id) ON DELETE SET NULL,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    quantity INTEGER DEFAULT 1,
    obtained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_butchered BOOLEAN DEFAULT FALSE    -- Был ли разработан этот лут
);

-- ===== BUTCHERING SKILL (Навык разделки) =====
CREATE TABLE IF NOT EXISTS butchering_skill (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL UNIQUE REFERENCES characters(id) ON DELETE CASCADE,
    skill_level INTEGER DEFAULT 1,
    experience INTEGER DEFAULT 0,         -- Опыт для прокачки разделки
    experience_next_level INTEGER DEFAULT 100,  -- Опыта нужно до следующего уровня
    items_butchered INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== SKILL COINS (Валюта для покупки умений) =====
CREATE TABLE IF NOT EXISTS skill_coins (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL UNIQUE REFERENCES characters(id) ON DELETE CASCADE,
    balance INTEGER DEFAULT 0,            -- Текущий баланс коинов
    total_earned INTEGER DEFAULT 0,       -- Всего заработано
    total_spent INTEGER DEFAULT 0,        -- Всего потрачено
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== ABILITY SKILL COIN COSTS (Стоимость умений в коинах) =====
CREATE TABLE IF NOT EXISTS ability_skill_coin_costs (
    id SERIAL PRIMARY KEY,
    ability_id INTEGER NOT NULL UNIQUE REFERENCES abilities(id) ON DELETE CASCADE,
    skill_coin_cost INTEGER DEFAULT 0,    -- 0 = не продается за коины
    class_id INTEGER REFERENCES character_classes(id) ON DELETE CASCADE,
    unlocked_at_level INTEGER DEFAULT 1,  -- На каком уровне доступна для покупки
    required_completed_quests INTEGER DEFAULT 0, -- Сколько квестов нужно завершить
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== CHARACTER LEARNED ABILITIES (Обученные умения через коины) =====
CREATE TABLE IF NOT EXISTS character_learned_abilities (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    ability_id INTEGER NOT NULL REFERENCES abilities(id) ON DELETE CASCADE,
    learned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(character_id, ability_id)
);

-- ===== SKILL COIN TRANSACTIONS (История транзакций коинов) =====
CREATE TABLE IF NOT EXISTS skill_coin_transactions (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    transaction_type VARCHAR(50),         -- earned, spent, quest_reward
    amount INTEGER NOT NULL,
    source TEXT,                          -- quest_id, ability_id, etc
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== QUEST KILL TARGETS (Целевые мобы для квестов убйства) =====
CREATE TABLE IF NOT EXISTS quest_kill_targets (
    id SERIAL PRIMARY KEY,
    quest_id INTEGER NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
    mob_id INTEGER NOT NULL REFERENCES mobs(id) ON DELETE CASCADE,
    required_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== CHARACTER QUEST KILLS (Отслеживание убитых мобов для квестов) =====
CREATE TABLE IF NOT EXISTS character_quest_kills (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    quest_id INTEGER NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
    mob_id INTEGER NOT NULL REFERENCES mobs(id) ON DELETE CASCADE,
    kill_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(character_id, quest_id, mob_id)
);

-- ===== INDEXES для оптимизации =====
CREATE INDEX IF NOT EXISTS idx_characters_user_id ON characters(user_id);
-- Дополнительные ограничения уникальности/проверки могут быть добавлены миграциями в будущем
CREATE INDEX IF NOT EXISTS idx_characters_is_online ON characters(is_online);
CREATE INDEX IF NOT EXISTS idx_location_objects_location_id ON location_objects(location_id);
CREATE INDEX IF NOT EXISTS idx_npcs_location_id ON npcs(location_id);
CREATE INDEX IF NOT EXISTS idx_inventory_character_id ON inventory(character_id);
CREATE INDEX IF NOT EXISTS idx_character_quests_character_id ON character_quests(character_id);
CREATE INDEX IF NOT EXISTS idx_combat_logs_timestamp ON combat_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_player_status_character_id ON player_status(character_id);
CREATE INDEX IF NOT EXISTS idx_faction_members_character_id ON faction_members(character_id);
CREATE INDEX IF NOT EXISTS idx_loot_items_loot_table_id ON loot_items(loot_table_id);
CREATE INDEX IF NOT EXISTS idx_mob_loot_character_id ON mob_loot(character_id);
CREATE INDEX IF NOT EXISTS idx_skill_coin_transactions_character_id ON skill_coin_transactions(character_id);
CREATE INDEX IF NOT EXISTS idx_quest_kill_targets_quest_id ON quest_kill_targets(quest_id);
CREATE INDEX IF NOT EXISTS idx_character_quest_kills_character_id ON character_quest_kills(character_id);
