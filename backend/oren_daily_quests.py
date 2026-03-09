from __future__ import annotations

import json
from datetime import date

from database.connection import execute, fetch_all, fetch_one, fetch_val

BOSS_MARKERS = ("вожак", "главарь", "босс")
OREN_NAME = "Смотритель Равнин Орен"


def _today_key() -> str:
    return date.today().isoformat()


def _pick_reward_item(category: str) -> int | None:
    category = (category or "").lower()
    if category == "animal":
        item_id = fetch_val(
            """
            SELECT id FROM items
            WHERE LOWER(name) LIKE ANY(%s)
            ORDER BY RANDOM()
            LIMIT 1
            """,
            ["%шкура%", "%кость%", "%мясо%", "%клык%"],
        )
        return int(item_id) if item_id else None

    if category == "humanoid":
        item_id = fetch_val(
            """
            SELECT id FROM items
            WHERE LOWER(name) LIKE ANY(%s)
            ORDER BY RANDOM()
            LIMIT 1
            """,
            ["%кинжал%", "%меч%", "%кольцо%", "%роба%", "%доспех%"],
        )
        return int(item_id) if item_id else None

    if category == "resource":
        item_id = fetch_val(
            """
            SELECT id FROM items
            WHERE LOWER(item_type) IN ('material', 'resource', 'crafting')
               OR LOWER(name) LIKE ANY(%s)
            ORDER BY RANDOM()
            LIMIT 1
            """,
            ["%руда%", "%камень%", "%дерево%", "%трава%"],
        )
        return int(item_id) if item_id else None

    item_id = fetch_val("SELECT id FROM items WHERE name = 'Малое зелье лечения' LIMIT 1")
    return int(item_id) if item_id else None


def _insert_kill_daily_quest(
    npc_id: int,
    title: str,
    description: str,
    mob_id: int,
    required_count: int,
    level_requirement: int,
    base_exp: int,
    base_gold: int,
    reward_item_id: int | None,
) -> None:
    reward_exp = max(200, int(base_exp or 20) * int(required_count or 1) * 10)
    reward_gold = max(20, int(base_gold or 2) * int(required_count or 1) * 10)
    completion_condition = json.dumps(
        {
            "daily_key": _today_key(),
            "kind": "kill",
            "required_count": int(required_count),
            "mob_id": int(mob_id),
            "reward_item_quantity": 10,
        },
        ensure_ascii=False,
    )

    quest_id = fetch_val(
        """
        INSERT INTO quests (
            npc_id, title, description, quest_type, level_requirement,
            reward_experience, reward_gold, reward_item_id,
            completion_condition, is_repeatable, is_available
        )
        VALUES (%s, %s, %s, 'kill', %s, %s, %s, %s, %s, TRUE, TRUE)
        RETURNING id
        """,
        npc_id,
        title,
        description,
        int(level_requirement or 1),
        reward_exp,
        reward_gold,
        reward_item_id,
        completion_condition,
    )
    if not quest_id:
        return

    execute(
        "INSERT INTO quest_kill_targets (quest_id, mob_id, required_count) VALUES (%s, %s, %s)",
        int(quest_id),
        int(mob_id),
        int(required_count),
    )


def _insert_collect_daily_quest(
    npc_id: int,
    title: str,
    description: str,
    item_id: int,
    required_count: int,
    level_requirement: int,
    reward_item_id: int | None,
) -> None:
    reward_exp = max(300, int(level_requirement or 1) * int(required_count or 1) * 120)
    reward_gold = max(30, int(level_requirement or 1) * int(required_count or 1) * 15)
    completion_condition = json.dumps(
        {
            "daily_key": _today_key(),
            "kind": "collect",
            "required_item_id": int(item_id),
            "required_count": int(required_count),
            "reward_item_quantity": 10,
        },
        ensure_ascii=False,
    )

    fetch_val(
        """
        INSERT INTO quests (
            npc_id, title, description, quest_type, level_requirement,
            reward_experience, reward_gold, reward_item_id,
            completion_condition, is_repeatable, is_available
        )
        VALUES (%s, %s, %s, 'collect', %s, %s, %s, %s, %s, TRUE, TRUE)
        RETURNING id
        """,
        npc_id,
        title,
        description,
        int(level_requirement or 1),
        reward_exp,
        reward_gold,
        reward_item_id,
        completion_condition,
    )


def ensure_oren_daily_quests_for_npc(npc_id: int) -> None:
    npc = fetch_one("SELECT id, name, location_id FROM npcs WHERE id = %s", npc_id)
    if not npc:
        return

    resolved_npc_id, npc_name, location_id = int(npc[0]), str(npc[1] or ""), int(npc[2] or 0)
    if npc_name.strip().lower() != OREN_NAME.lower():
        return

    day_key = _today_key()
    existing = fetch_val(
        """
        SELECT COUNT(*)
        FROM quests
        WHERE npc_id = %s
          AND completion_condition::text LIKE %s
        """,
        resolved_npc_id,
        f"%{day_key}%",
    ) or 0
    if int(existing) > 0:
        return

    # Boss daily quests for this territory.
    bosses = fetch_all(
        """
        SELECT id, name, level, experience_reward, gold_reward
        FROM mobs
        WHERE location_id = %s
          AND (
              LOWER(name) LIKE ANY(%s)
              OR LOWER(mob_type) = 'boss'
          )
        ORDER BY level DESC, id ASC
        """,
        location_id,
        [f"%{marker}%" for marker in BOSS_MARKERS],
    )
    for mob_id, mob_name, level, exp_reward, gold_reward in bosses:
        reward_item_id = _pick_reward_item("boss")
        _insert_kill_daily_quest(
            resolved_npc_id,
            f"Ежедневный рейд: {mob_name} [{day_key}]",
            f"Победите босса {mob_name}. Рекомендуется группа.",
            int(mob_id),
            1,
            max(1, int(level or 1)),
            int(exp_reward or 0),
            int(gold_reward or 0),
            reward_item_id,
        )

    # One random animal and one random humanoid daily quest.
    animal = fetch_one(
        """
        SELECT id, name, level, experience_reward, gold_reward
        FROM mobs
        WHERE location_id = %s
          AND LOWER(mob_type) = 'animal'
        ORDER BY RANDOM()
        LIMIT 1
        """,
        location_id,
    )
    if animal:
        mob_id, mob_name, level, exp_reward, gold_reward = animal
        _insert_kill_daily_quest(
            resolved_npc_id,
            f"Ежедневная охота: {mob_name} [{day_key}]",
            f"Убейте 5 существ типа животные: {mob_name}.",
            int(mob_id),
            5,
            max(1, int(level or 1)),
            int(exp_reward or 0),
            int(gold_reward or 0),
            _pick_reward_item("animal"),
        )

    humanoid = fetch_one(
        """
        SELECT id, name, level, experience_reward, gold_reward
        FROM mobs
        WHERE location_id = %s
          AND LOWER(mob_type) = 'humanoid'
        ORDER BY RANDOM()
        LIMIT 1
        """,
        location_id,
    )
    if humanoid:
        mob_id, mob_name, level, exp_reward, gold_reward = humanoid
        _insert_kill_daily_quest(
            resolved_npc_id,
            f"Ежедневная зачистка: {mob_name} [{day_key}]",
            f"Убейте 5 существ типа гуманоиды: {mob_name}.",
            int(mob_id),
            5,
            max(1, int(level or 1)),
            int(exp_reward or 0),
            int(gold_reward or 0),
            _pick_reward_item("humanoid"),
        )

    # One random collect/resource daily quest.
    resource_item = fetch_one(
        """
        SELECT id, name
        FROM items
        WHERE LOWER(item_type) IN ('material', 'resource', 'crafting')
           OR LOWER(name) LIKE ANY(%s)
        ORDER BY RANDOM()
        LIMIT 1
        """,
        ["%руда%", "%камень%", "%дерево%", "%трава%", "%шкура%", "%кость%"],
    )
    if resource_item:
        item_id, item_name = int(resource_item[0]), resource_item[1]
        _insert_collect_daily_quest(
            resolved_npc_id,
            f"Ежедневный сбор: {item_name} [{day_key}]",
            f"Соберите 10 шт. ресурса: {item_name}.",
            item_id,
            10,
            1,
            _pick_reward_item("resource"),
        )
