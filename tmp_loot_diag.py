from pathlib import Path
import psycopg2

url = [
    line.split('=', 1)[1].strip()
    for line in Path('backend/.env').read_text(encoding='utf-8').splitlines()
    if line.startswith('DATABASE_URL=')
][0]

conn = psycopg2.connect(url, connect_timeout=10)
cur = conn.cursor()

cur.execute("SELECT id, name FROM loot_tables ORDER BY id LIMIT 40")
print('loot_tables', cur.fetchall())

cur.execute("SELECT loot_table_id, COUNT(*) FROM loot_items GROUP BY loot_table_id ORDER BY loot_table_id LIMIT 40")
print('loot_items_counts', cur.fetchall())

cur.execute("SELECT id, name, loot_table_id, location_id FROM mobs WHERE location_id IN (1,2) ORDER BY id LIMIT 40")
print('mobs_sample', cur.fetchall())

cur.close()
conn.close()
