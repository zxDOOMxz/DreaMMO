#!/usr/bin/env python3
"""Simple test to check if NPCs are being initialized correctly"""

import asyncio
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from database.connection import init_db_pool, close_db_pool, fetch_val, fetch_all, execute

async def main():
    print("=" * 50)
    print("Database Initialization Test")
    print("=" * 50)
    
    # Initialize database connection
    try:
        await init_db_pool()
        print("✓ Database connection initialized")
    except Exception as e:
        print(f"✗ Failed to initialize database: {e}")
        return
    
    try:
        # Check NPCs
        print("\n[Testing NPCs]")
        quest_npcs = fetch_val("SELECT COUNT(*) FROM npcs WHERE has_quest = TRUE")
        print(f"  Quest NPCs (has_quest=TRUE): {quest_npcs}")
        
        all_npcs = fetch_val("SELECT COUNT(*) FROM npcs")
        print(f"  All NPCs: {all_npcs}")
        
        # List all NPCs
        npcs = fetch_all("SELECT id, name, type, has_quest FROM npcs ORDER BY id")
        print(f"  NPC List:")
        for npc in npcs:
            print(f"    - ID: {npc[0]}, Name: {npc[1]}, Type: {npc[2]}, HasQuest: {npc[3]}")
        
        # Check quests
        print("\n[Testing Quests]")
        total_quests = fetch_val("SELECT COUNT(*) FROM quests")
        print(f"  Total Quests: {total_quests}")
        
        quests = fetch_all("SELECT id, npc_id, title FROM quests ORDER BY npc_id, id")
        print(f"  Quest List:")
        for quest in quests:
            print(f"    - ID: {quest[0]}, NPC_ID: {quest[1]}, Title: {quest[2]}")
        
        # Check quest targets
        print("\n[Testing Quest Targets]")
        kill_targets = fetch_val("SELECT COUNT(*) FROM quest_kill_targets")
        print(f"  Kill Targets: {kill_targets}")
        
        targets = fetch_all("SELECT quest_id, mob_id, required_count FROM quest_kill_targets ORDER BY quest_id")
        print(f"  Target List:")
        for target in targets:
            print(f"    - Quest_ID: {target[0]}, Mob_ID: {target[1]}, Required: {target[2]}")
        
    except Exception as e:
        import traceback
        print(f"✗ Error during testing: {e}")
        traceback.print_exc()
    finally:
        await close_db_pool()
        print("\n✓ Database connection closed")

if __name__ == "__main__":
    asyncio.run(main())
