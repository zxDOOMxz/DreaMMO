"""Character progression helpers: XP gain, level cap, and derived stat growth."""

from database.connection import execute, fetch_one

MAX_LEVEL = 10


def exp_required_for_next_level(level: int) -> int:
    """Return total XP required to advance from current level to next."""
    safe_level = max(1, int(level or 1))
    return safe_level * 100


def apply_experience_and_level_up(character_id: int, exp_gain: int, gold_gain: int = 0) -> dict:
    """
    Apply experience/gold and process level-ups up to MAX_LEVEL.

    Returns summary dict with current level/experience and level-up details.
    """
    exp_gain = max(0, int(exp_gain or 0))
    gold_gain = max(0, int(gold_gain or 0))

    row = fetch_one(
        """
        SELECT c.level, c.experience, c.max_health_points, c.max_mana_points,
               c.health_points, c.mana_points,
               COALESCE(cc.health_per_level, 10), COALESCE(cc.mana_per_level, 5)
        FROM characters c
        LEFT JOIN character_classes cc ON cc.id = c.class_id
        WHERE c.id = %s
        """,
        character_id,
    )
    if not row:
        raise ValueError("Character not found")

    level = int(row[0] or 1)
    experience = int(row[1] or 0)
    max_hp = int(row[2] or 100)
    max_mp = int(row[3] or 50)
    hp = int(row[4] or max_hp)
    mp = int(row[5] or max_mp)
    hp_per_level = int(row[6] or 10)
    mp_per_level = int(row[7] or 5)

    experience += exp_gain
    leveled_up = False
    levels_gained = 0

    while level < MAX_LEVEL:
        required = exp_required_for_next_level(level)
        if experience < required:
            break
        experience -= required
        level += 1
        levels_gained += 1
        leveled_up = True
        max_hp += hp_per_level
        max_mp += mp_per_level

    if level >= MAX_LEVEL:
        level = MAX_LEVEL
        # At level cap keep XP bounded to progress bar requirement.
        experience = min(experience, exp_required_for_next_level(MAX_LEVEL) - 1)

    stat_points_gained = levels_gained * 5

    # Restore a part of HP/MP on level-up to make progression feel visible.
    if leveled_up:
        hp = min(max_hp, hp + 20 * levels_gained)
        mp = min(max_mp, mp + 15 * levels_gained)

    execute(
        """
        UPDATE characters
        SET level = %s,
            experience = %s,
            max_health_points = %s,
            max_mana_points = %s,
            health_points = %s,
            mana_points = %s,
            gold = COALESCE(gold, 0) + %s
        WHERE id = %s
        """,
        level,
        experience,
        max_hp,
        max_mp,
        hp,
        mp,
        gold_gain,
        character_id,
    )

    execute(
        """
        INSERT INTO character_stats (character_id)
        VALUES (%s)
        ON CONFLICT (character_id) DO NOTHING
        """,
        character_id,
    )

    if stat_points_gained > 0:
        execute(
            """
            UPDATE character_stats
            SET available_stat_points = COALESCE(available_stat_points, 0) + %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE character_id = %s
            """,
            stat_points_gained,
            character_id,
        )

    available_stat_points = fetch_one(
        "SELECT COALESCE(available_stat_points, 0) FROM character_stats WHERE character_id = %s",
        character_id,
    )

    return {
        "level": level,
        "experience": experience,
        "leveled_up": leveled_up,
        "levels_gained": levels_gained,
        "stat_points_gained": stat_points_gained,
        "available_stat_points": int(available_stat_points[0]) if available_stat_points else 0,
        "max_level": MAX_LEVEL,
    }
