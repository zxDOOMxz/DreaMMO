import asyncio
import json
from database.connection import init_db_pool, close_db_pool, fetch_all

async def main():
    await init_db_pool()
    try:
        groups = fetch_all("""
            SELECT location_id, lower(name) AS mob_name, ARRAY_AGG(id ORDER BY id) AS ids, COUNT(*)
            FROM mobs
            GROUP BY location_id, lower(name)
            HAVING COUNT(*) > 1
            ORDER BY location_id, mob_name
        """)
        out = []
        for location_id, mob_name, ids, cnt in groups:
            refs = []
            for mob_id in ids:
                refs.append({
                    'mob_id': int(mob_id),
                    'zone_spawns': int(fetch_all('SELECT COUNT(*) FROM mob_zone_spawns WHERE mob_id = %s', mob_id)[0][0]),
                    'quest_targets': int(fetch_all('SELECT COUNT(*) FROM quest_kill_targets WHERE mob_id = %s', mob_id)[0][0]),
                    'quest_kills': int(fetch_all('SELECT COUNT(*) FROM character_quest_kills WHERE mob_id = %s', mob_id)[0][0]),
                    'combat_log': int(fetch_all('SELECT COUNT(*) FROM combat_log WHERE mob_id = %s', mob_id)[0][0]),
                    'mob_loot': int(fetch_all('SELECT COUNT(*) FROM mob_loot WHERE mob_id = %s', mob_id)[0][0]),
                })
            out.append({'location_id': int(location_id), 'mob_name': mob_name, 'ids': [int(x) for x in ids], 'refs': refs})
        print(json.dumps(out, ensure_ascii=False))
    finally:
        await close_db_pool()

asyncio.run(main())
