from database.connection import fetch_val, fetch_all

# Check quest NPCs
quest_npcs = fetch_val("SELECT COUNT(*) FROM npcs WHERE has_quest = TRUE")
print(f"Quest NPCs: {quest_npcs}")

# Check all quests
quests = fetch_val("SELECT COUNT(*) FROM quests")
print(f"Total Quests: {quests}")

# List all quest NPCs
npcs = fetch_all("SELECT id, name, type, has_quest FROM npcs WHERE has_quest = TRUE")
print(f"\nNPCs with quests:")
for npc in npcs:
    print(f"  ID: {npc[0]}, Name: {npc[1]}, Type: {npc[2]}, Has Quest: {npc[3]}")

# List quests by NPC
if npcs:
    npc_name = npcs[0][1]
    npc_id = npcs[0][0]
    quests = fetch_all(f"SELECT id, title FROM quests WHERE npc_id = {npc_id}")
    print(f"\nQuests for {npc_name}:")
    for q in quests:
        print(f"  ID: {q[0]}, Title: {q[1]}")
