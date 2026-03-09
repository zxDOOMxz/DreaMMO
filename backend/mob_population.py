from __future__ import annotations

from datetime import datetime, timedelta

from database.connection import execute, fetch_all, fetch_one

BOSS_MARKERS = ("вожак", "главарь", "босс")
FOX_ZONE_MARKER = "лисий лес"

FOX_PROFILES = {
    "молодой лис": ("weak", 20, 60),
    "старый лис": ("normal", 15, 180),
    "матерый лис": ("strong", 10, 600),
    "лисий вожак": ("boss", 1, 1800),
}

DEFAULT_TIER_PROFILE = {
    "weak": (12, 90),
    "normal": (8, 180),
    "strong": (4, 420),
    "boss": (1, 1500),
}


_SCHEMA_READY = False


def ensure_population_schema() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return

    execute(
        """
        CREATE TABLE IF NOT EXISTS mob_zone_population (
            id SERIAL PRIMARY KEY,
            zone_id INTEGER NOT NULL REFERENCES mob_spawn_zones(id) ON DELETE CASCADE,
            mob_id INTEGER NOT NULL REFERENCES mobs(id) ON DELETE CASCADE,
            mob_tier VARCHAR(16) NOT NULL DEFAULT 'normal',
            total_count INTEGER NOT NULL DEFAULT 0,
            alive_count INTEGER NOT NULL DEFAULT 0,
            respawn_seconds INTEGER NOT NULL DEFAULT 60,
            last_update_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(zone_id, mob_id)
        )
        """
    )
    execute("CREATE INDEX IF NOT EXISTS idx_mob_zone_population_zone ON mob_zone_population(zone_id)")
    _SCHEMA_READY = True


def _normalize_name(value: str | None) -> str:
    return str(value or "").strip().lower()


def _is_boss_name(name: str | None) -> bool:
    normalized = _normalize_name(name)
    return any(marker in normalized for marker in BOSS_MARKERS)


def _pick_mob_tier(mob_name: str, mob_level: int, zone_min_level: int, zone_max_level: int) -> str:
    normalized = _normalize_name(mob_name)
    if normalized in FOX_PROFILES:
        return FOX_PROFILES[normalized][0]

    if _is_boss_name(mob_name):
        return "boss"

    zmin = int(zone_min_level or 1)
    zmax = int(zone_max_level or zmin)
    mlevel = int(mob_level or zmin)
    if zmax <= zmin:
        return "normal"

    ratio = (mlevel - zmin) / max(1, (zmax - zmin))
    if ratio <= 0.33:
        return "weak"
    if ratio <= 0.66:
        return "normal"
    return "strong"


def _tier_profile(zone_name: str, mob_name: str, tier: str) -> tuple[int, int]:
    normalized_zone = _normalize_name(zone_name)
    normalized_name = _normalize_name(mob_name)

    if FOX_ZONE_MARKER in normalized_zone and normalized_name in FOX_PROFILES:
        _, total, respawn = FOX_PROFILES[normalized_name]
        return total, respawn

    return DEFAULT_TIER_PROFILE.get(tier, DEFAULT_TIER_PROFILE["normal"])


def sync_zone_population(zone_id: int) -> None:
    ensure_population_schema()

    zone = fetch_one(
        """
        SELECT id, zone_name, COALESCE(min_level, 1), COALESCE(max_level, COALESCE(min_level, 1))
        FROM mob_spawn_zones
        WHERE id = %s
        """,
        zone_id,
    )
    if not zone:
        return

    _, zone_name, zmin, zmax = zone
    spawns = fetch_all(
        """
        SELECT mzs.mob_id, m.name, COALESCE(m.level, 1)
        FROM mob_zone_spawns mzs
        JOIN mobs m ON m.id = mzs.mob_id
        WHERE mzs.spawn_zone_id = %s
        """,
        zone_id,
    )

    active_mob_ids: set[int] = set()
    for mob_id, mob_name, mob_level in spawns:
        active_mob_ids.add(int(mob_id))
        tier = _pick_mob_tier(str(mob_name or ""), int(mob_level or 1), int(zmin or 1), int(zmax or 1))
        total_count, respawn_seconds = _tier_profile(str(zone_name or ""), str(mob_name or ""), tier)

        execute(
            """
            INSERT INTO mob_zone_population (zone_id, mob_id, mob_tier, total_count, alive_count, respawn_seconds, last_update_at)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (zone_id, mob_id)
            DO UPDATE SET
                mob_tier = EXCLUDED.mob_tier,
                total_count = EXCLUDED.total_count,
                respawn_seconds = EXCLUDED.respawn_seconds,
                alive_count = LEAST(
                    GREATEST(mob_zone_population.alive_count, 0),
                    EXCLUDED.total_count
                )
            """,
            zone_id,
            int(mob_id),
            tier,
            int(total_count),
            int(total_count),
            int(respawn_seconds),
        )

    if active_mob_ids:
        execute(
            "DELETE FROM mob_zone_population WHERE zone_id = %s AND mob_id <> ALL(%s)",
            zone_id,
            list(active_mob_ids),
        )
    else:
        execute("DELETE FROM mob_zone_population WHERE zone_id = %s", zone_id)


def apply_zone_respawns(zone_id: int) -> None:
    ensure_population_schema()

    rows = fetch_all(
        """
        SELECT p.id, p.mob_id, p.mob_tier, m.name,
               p.total_count, p.alive_count, p.respawn_seconds, p.last_update_at
        FROM mob_zone_population p
        JOIN mobs m ON m.id = p.mob_id
        WHERE p.zone_id = %s
        """,
        zone_id,
    )

    now = datetime.now()
    for row_id, mob_id, mob_tier, mob_name, total_count, alive_count, respawn_seconds, last_update_at in rows:
        total = int(total_count or 0)
        alive = int(alive_count or 0)
        respawn = int(respawn_seconds or 0)
        last_upd = last_update_at or now

        if total <= 0 or respawn <= 0:
            normalized_name = _normalize_name(str(mob_name or ""))
            if normalized_name in FOX_PROFILES:
                _, recovered_total, recovered_respawn = FOX_PROFILES[normalized_name]
            else:
                fallback_tier = str(mob_tier or "normal").lower()
                recovered_total, recovered_respawn = DEFAULT_TIER_PROFILE.get(
                    fallback_tier,
                    DEFAULT_TIER_PROFILE["normal"],
                )
            total = int(recovered_total)
            respawn = int(recovered_respawn)
            alive = total if alive <= 0 else min(alive, total)
            last_upd = now
            execute(
                """
                UPDATE mob_zone_population
                SET total_count = %s,
                    alive_count = %s,
                    respawn_seconds = %s,
                    last_update_at = CURRENT_TIMESTAMP
                WHERE zone_id = %s AND mob_id = %s
                """,
                total,
                alive,
                respawn,
                zone_id,
                int(mob_id),
            )

        if total <= 0 or respawn <= 0 or alive >= total:
            continue

        elapsed = max(0, int((now - last_upd).total_seconds()))
        restored = min(total - alive, elapsed // respawn)
        if restored <= 0:
            continue

        new_alive = alive + restored
        new_last = last_upd + timedelta(seconds=restored * respawn)
        execute(
            "UPDATE mob_zone_population SET alive_count = %s, last_update_at = %s WHERE id = %s",
            new_alive,
            new_last,
            row_id,
        )


def restore_zone_if_fully_dead(zone_id: int) -> bool:
    """Bootstrap fix: if all tracked mobs in zone are dead, restore full packs once."""
    ensure_population_schema()
    row = fetch_one(
        """
        SELECT COUNT(*), COALESCE(SUM(alive_count), 0)
        FROM mob_zone_population
        WHERE zone_id = %s
        """,
        zone_id,
    )
    if not row:
        return False

    total_rows, alive_sum = int(row[0] or 0), int(row[1] or 0)
    if total_rows <= 0 or alive_sum > 0:
        return False

    execute(
        """
        UPDATE mob_zone_population
        SET alive_count = total_count,
            last_update_at = CURRENT_TIMESTAMP
        WHERE zone_id = %s
        """,
        zone_id,
    )
    return True


def get_zone_mob_entries(zone_id: int, location_id: int | None = None) -> list[dict]:
    sync_zone_population(zone_id)
    apply_zone_respawns(zone_id)
    restore_zone_if_fully_dead(zone_id)

    rows = fetch_all(
        """
        SELECT p.mob_id, m.name, m.level, m.health_points, m.max_health_points,
               m.damage_min, m.damage_max, m.armor_class, m.experience_reward,
               m.gold_reward, m.mob_type, m.aggression_type,
               p.mob_tier, p.total_count, p.alive_count, p.respawn_seconds, p.last_update_at
        FROM mob_zone_population p
        JOIN mobs m ON m.id = p.mob_id
        WHERE p.zone_id = %s
          AND (%s IS NULL OR m.location_id = %s)
        ORDER BY
          CASE p.mob_tier
            WHEN 'weak' THEN 1
            WHEN 'normal' THEN 2
            WHEN 'strong' THEN 3
            WHEN 'boss' THEN 4
            ELSE 5
          END,
          m.level ASC,
          m.name ASC
        """,
        zone_id,
        location_id,
        location_id,
    )

    now = datetime.now()
    entries: list[dict] = []
    for row in rows:
        (
            mob_id,
            name,
            level,
            health_points,
            max_health_points,
            damage_min,
            damage_max,
            armor_class,
            experience_reward,
            gold_reward,
            mob_type,
            aggression_type,
            mob_tier,
            total_count,
            alive_count,
            respawn_seconds,
            last_update_at,
        ) = row

        total = int(total_count or 0)
        alive = int(alive_count or 0)
        respawn = int(respawn_seconds or 0)
        last_upd = last_update_at or now

        if total <= 0 or respawn <= 0:
            normalized_name = _normalize_name(str(name or ""))
            if normalized_name in FOX_PROFILES:
                _, recovered_total, recovered_respawn = FOX_PROFILES[normalized_name]
            else:
                fallback_tier = str(mob_tier or "normal").lower()
                recovered_total, recovered_respawn = DEFAULT_TIER_PROFILE.get(
                    fallback_tier,
                    DEFAULT_TIER_PROFILE["normal"],
                )
            total = int(recovered_total)
            respawn = int(recovered_respawn)
            alive = total if alive <= 0 else min(alive, total)
            execute(
                """
                UPDATE mob_zone_population
                SET total_count = %s,
                    alive_count = %s,
                    respawn_seconds = %s,
                    last_update_at = CURRENT_TIMESTAMP
                WHERE zone_id = %s AND mob_id = %s
                """,
                total,
                alive,
                respawn,
                zone_id,
                int(mob_id),
            )

        next_respawn_in = 0
        if alive < total and respawn > 0:
            elapsed = max(0, int((now - last_upd).total_seconds()))
            remainder = elapsed % respawn
            next_respawn_in = respawn - remainder if remainder else respawn

        entries.append(
            {
                "id": int(mob_id),
                "name": name,
                "level": int(level or 1),
                "health": int(health_points or 1),
                "max_health": int(max_health_points or 1),
                "damage_min": int(damage_min or 0),
                "damage_max": int(damage_max or 0),
                "armor": int(armor_class or 0),
                "exp_reward": int(experience_reward or 0),
                "gold_reward": int(gold_reward or 0),
                "type": mob_type,
                "aggression": aggression_type,
                "mob_tier": mob_tier,
                "is_boss": mob_tier == "boss",
                "party_required": mob_tier == "boss",
                "total_count": total,
                "alive_count": alive,
                "dead_count": max(0, total - alive),
                "respawn_seconds": respawn,
                "next_respawn_in_seconds": next_respawn_in,
            }
        )

    return entries


def consume_mob_unit(zone_id: int, mob_id: int) -> bool:
    sync_zone_population(zone_id)
    apply_zone_respawns(zone_id)

    row = fetch_one(
        "SELECT id, alive_count FROM mob_zone_population WHERE zone_id = %s AND mob_id = %s",
        zone_id,
        mob_id,
    )
    if not row:
        return False

    row_id, alive_count = row
    alive = int(alive_count or 0)
    if alive <= 0:
        return False

    execute(
        "UPDATE mob_zone_population SET alive_count = %s, last_update_at = CURRENT_TIMESTAMP WHERE id = %s",
        alive - 1,
        row_id,
    )
    return True


def fetch_zone_population_row(zone_id: int, mob_id: int) -> dict | None:
    sync_zone_population(zone_id)
    apply_zone_respawns(zone_id)

    row = fetch_one(
        """
        SELECT mob_tier, total_count, alive_count, respawn_seconds
        FROM mob_zone_population
        WHERE zone_id = %s AND mob_id = %s
        """,
        zone_id,
        mob_id,
    )
    if not row:
        return None

    tier, total_count, alive_count, respawn_seconds = row
    return {
        "mob_tier": tier,
        "is_boss": str(tier or "") == "boss",
        "total_count": int(total_count or 0),
        "alive_count": int(alive_count or 0),
        "respawn_seconds": int(respawn_seconds or 0),
    }
