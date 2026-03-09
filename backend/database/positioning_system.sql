-- ===== POSITIONING AND MOVEMENT SYSTEM =====
-- Add positioning fields to characters table
ALTER TABLE characters ADD COLUMN IF NOT EXISTS current_location_id INTEGER REFERENCES locations(id);
ALTER TABLE characters ADD COLUMN IF NOT EXISTS position_x FLOAT DEFAULT 0;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS position_y FLOAT DEFAULT 0;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS position_z FLOAT DEFAULT 0;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS target_object_id INTEGER;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS target_object_type VARCHAR(50);
ALTER TABLE characters ADD COLUMN IF NOT EXISTS distance_to_target FLOAT DEFAULT 0;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS is_moving BOOLEAN DEFAULT FALSE;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS movement_speed FLOAT DEFAULT 5.0; -- meters per second
ALTER TABLE characters ADD COLUMN IF NOT EXISTS last_position_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- ===== MOB SPAWN ZONES =====
-- Zones where mobs spawn with specific distance from location center
CREATE TABLE IF NOT EXISTS mob_spawn_zones (
    id SERIAL PRIMARY KEY,
    location_id INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    zone_name VARCHAR(100) NOT NULL,
    zone_type VARCHAR(50), -- city, hunting, resource
    distance_from_center FLOAT NOT NULL, -- distance in meters
    position_x FLOAT DEFAULT 0,
    position_y FLOAT DEFAULT 0,
    position_z FLOAT DEFAULT 0,
    radius FLOAT DEFAULT 20, -- spawn radius in meters
    min_level INTEGER DEFAULT 1,
    max_level INTEGER DEFAULT 10,
    is_aggressive_zone BOOLEAN DEFAULT FALSE,
    respawn_timer INTEGER DEFAULT 300, -- seconds
    max_mobs INTEGER DEFAULT 10,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Link mobs to spawn zones
CREATE TABLE IF NOT EXISTS mob_zone_spawns (
    id SERIAL PRIMARY KEY,
    spawn_zone_id INTEGER NOT NULL REFERENCES mob_spawn_zones(id) ON DELETE CASCADE,
    mob_id INTEGER NOT NULL REFERENCES mobs(id) ON DELETE CASCADE,
    spawn_chance FLOAT DEFAULT 1.0, -- 0.0 to 1.0
    min_count INTEGER DEFAULT 1,
    max_count INTEGER DEFAULT 3,
    is_champion_spawn BOOLEAN DEFAULT FALSE, -- Can spawn champion versions (*)
    champion_chance FLOAT DEFAULT 0.05, -- 5% chance for champion
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add position to mobs
ALTER TABLE mobs ADD COLUMN IF NOT EXISTS position_x FLOAT DEFAULT 0;
ALTER TABLE mobs ADD COLUMN IF NOT EXISTS position_y FLOAT DEFAULT 0;
ALTER TABLE mobs ADD COLUMN IF NOT EXISTS position_z FLOAT DEFAULT 0;
ALTER TABLE mobs ADD COLUMN IF NOT EXISTS spawn_zone_id INTEGER REFERENCES mob_spawn_zones(id);
ALTER TABLE mobs ADD COLUMN IF NOT EXISTS is_champion BOOLEAN DEFAULT FALSE;
ALTER TABLE mobs ADD COLUMN IF NOT EXISTS champion_stars INTEGER DEFAULT 0; -- 0, 1, 2, 3 stars

-- ===== PARTY SYSTEM =====
CREATE TABLE IF NOT EXISTS parties (
    id SERIAL PRIMARY KEY,
    party_name VARCHAR(100),
    leader_character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    max_members INTEGER DEFAULT 6,
    is_public BOOLEAN DEFAULT FALSE,
    experience_share_type VARCHAR(20) DEFAULT 'equal', -- equal, level_based
    loot_distribution VARCHAR(20) DEFAULT 'free_for_all', -- free_for_all, round_robin, master_looter
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS party_members (
    id SERIAL PRIMARY KEY,
    party_id INTEGER NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    role VARCHAR(20) DEFAULT 'member', -- leader, member
    UNIQUE(party_id, character_id)
);

-- Add party_id to characters
ALTER TABLE characters ADD COLUMN IF NOT EXISTS party_id INTEGER REFERENCES parties(id);

-- ===== ENHANCED COMBAT SYSTEM =====
-- Update combat log with more details
ALTER TABLE combat_log ADD COLUMN IF NOT EXISTS is_critical BOOLEAN DEFAULT FALSE;
ALTER TABLE combat_log ADD COLUMN IF NOT EXISTS is_miss BOOLEAN DEFAULT FALSE;
ALTER TABLE combat_log ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE;
ALTER TABLE combat_log ADD COLUMN IF NOT EXISTS combat_message TEXT;
ALTER TABLE combat_log ADD COLUMN IF NOT EXISTS distance FLOAT DEFAULT 0;

-- Combat instances (ongoing battles)
CREATE TABLE IF NOT EXISTS combat_instances (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    target_id INTEGER NOT NULL,
    target_type VARCHAR(20) NOT NULL, -- mob, player
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    winner VARCHAR(20), -- character, target, fled
    total_damage_dealt INTEGER DEFAULT 0,
    total_damage_taken INTEGER DEFAULT 0,
    experience_gained INTEGER DEFAULT 0,
    gold_gained INTEGER DEFAULT 0
);

-- ===== ABILITIES AND SKILLS SYSTEM =====
-- Add more fields to abilities for class-based skills
ALTER TABLE abilities ADD COLUMN IF NOT EXISTS race_id INTEGER REFERENCES races(id);
ALTER TABLE abilities ADD COLUMN IF NOT EXISTS is_ultimate BOOLEAN DEFAULT FALSE;
ALTER TABLE abilities ADD COLUMN IF NOT EXISTS tier INTEGER DEFAULT 1; -- 1-5 for active skills
ALTER TABLE abilities ADD COLUMN IF NOT EXISTS stat_requirement VARCHAR(50); -- e.g., "strength:20"
ALTER TABLE abilities ADD COLUMN IF NOT EXISTS crit_chance_bonus FLOAT DEFAULT 0;
ALTER TABLE abilities ADD COLUMN IF NOT EXISTS attack_speed_bonus FLOAT DEFAULT 0;

-- Character active ability slots (5 + 1 ultimate)
CREATE TABLE IF NOT EXISTS character_ability_slots (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    slot_number INTEGER NOT NULL, -- 1-5 for active, 6 for ultimate
    ability_id INTEGER REFERENCES abilities(id) ON DELETE SET NULL,
    UNIQUE(character_id, slot_number)
);

-- Ability cooldowns tracking
CREATE TABLE IF NOT EXISTS character_ability_cooldowns (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    ability_id INTEGER NOT NULL REFERENCES abilities(id) ON DELETE CASCADE,
    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cooldown_ends_at TIMESTAMP NOT NULL,
    UNIQUE(character_id, ability_id)
);

-- ===== EXPERIENCE AND LEVEL SYSTEM (Lineage 2 style) =====
-- XP penalty table based on level difference
CREATE TABLE IF NOT EXISTS exp_penalty_rules (
    id SERIAL PRIMARY KEY,
    level_difference_min INTEGER NOT NULL, -- e.g., -10
    level_difference_max INTEGER NOT NULL, -- e.g., -5
    exp_multiplier FLOAT NOT NULL, -- e.g., 0.5 for 50% penalty
    gold_multiplier FLOAT DEFAULT 1.0,
    description TEXT
);

-- Insert default Lineage 2 style rules
INSERT INTO exp_penalty_rules (level_difference_min, level_difference_max, exp_multiplier, gold_multiplier, description) VALUES
    (-2, 100, 1.0, 1.0, 'Full XP: mob is same level or higher'),
    (-5, -3, 0.75, 0.9, '-25% XP: mob is 3-5 levels lower'),
    (-10, -6, 0.5, 0.75, '-50% XP: mob is 6-10 levels lower'),
    (-999, -11, 0.0, 0.5, 'No XP: mob is 11+ levels lower, only loot')
ON CONFLICT DO NOTHING;

-- ===== INTERACTABLE OBJECTS =====
-- Update location_objects with position and distance
ALTER TABLE location_objects DROP COLUMN IF EXISTS distance_km;
ALTER TABLE location_objects ADD COLUMN IF NOT EXISTS distance_meters FLOAT DEFAULT 0;
ALTER TABLE location_objects ADD COLUMN IF NOT EXISTS position_x FLOAT DEFAULT 0;
ALTER TABLE location_objects ADD COLUMN IF NOT EXISTS position_y FLOAT DEFAULT 0;
ALTER TABLE location_objects ADD COLUMN IF NOT EXISTS interaction_range FLOAT DEFAULT 10; -- meters

-- NPC positions
ALTER TABLE npcs ADD COLUMN IF NOT EXISTS position_x FLOAT DEFAULT 0;
ALTER TABLE npcs ADD COLUMN IF NOT EXISTS position_y FLOAT DEFAULT 0;
ALTER TABLE npcs ADD COLUMN IF NOT EXISTS position_z FLOAT DEFAULT 0;
ALTER TABLE npcs ADD COLUMN IF NOT EXISTS distance_from_center FLOAT DEFAULT 0;

-- ===== INDEXES FOR PERFORMANCE =====
CREATE INDEX IF NOT EXISTS idx_characters_location ON characters(current_location_id);
CREATE INDEX IF NOT EXISTS idx_characters_party ON characters(party_id);
CREATE INDEX IF NOT EXISTS idx_mob_spawn_zones_location ON mob_spawn_zones(location_id);
CREATE INDEX IF NOT EXISTS idx_mob_zone_spawns_zone ON mob_zone_spawns(spawn_zone_id);
CREATE INDEX IF NOT EXISTS idx_party_members_party ON party_members(party_id);
CREATE INDEX IF NOT EXISTS idx_party_members_character ON party_members(character_id);
CREATE INDEX IF NOT EXISTS idx_combat_instances_character ON combat_instances(character_id);
CREATE INDEX IF NOT EXISTS idx_combat_instances_active ON combat_instances(is_active);
CREATE INDEX IF NOT EXISTS idx_ability_slots_character ON character_ability_slots(character_id);
CREATE INDEX IF NOT EXISTS idx_ability_cooldowns_character ON character_ability_cooldowns(character_id);
