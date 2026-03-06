# 🎮 DreaMMO - Text-Based MMORPG

**A free, open-source text-based MMORPG combining the best mechanics from EVE Online, Mortal Online, and classic MUDs.**

## Features

✨ **Game Mechanics Inspired By:**
- **EVE Online**: Location-based object system with distance mechanics, spatial awareness
- **Mortal Online**: Complex combat system with block/parry mechanics, crafting, resource gathering, escape mechanics based on stats
- **Classic MUDs**: Rich text interactions, quests, NPCs, social systems

🎯 **Core Features**
- 📍 **Locations System**: Text-based world with objects, NPCs, buildings, resources
- ⚔️ **Combat System**: Hit/miss/block/parry with damage calculations based on stats (strength, dexterity, constitution)
- 🔨 **Crafting & Resources**: Mine ores, craft weapons/armor, create items with skill progression
- 📜 **Quest System**: Quest chains, objectives, rewards, reputation
- 🗣️ **NPC Interactions**: Dialogue trees, merchants, quest givers, guards
- 👥 **Social System**: Factions, friend lists, chat channels (global/location/faction/private)
- 🎮 **Mobile-First UI**: Responsive design optimized for phones and desktops
- 🔗 **WebSocket Real-time**: Live location updates, combat messages, social notifications
- 🎵 **Audio Support**: Text-to-speech narration and game ambiance

## Tech Stack

**Backend:**
- FastAPI (Python) - High-performance async web framework
- PostgreSQL (Neon.tech) - Cloud database
- WebSocket - Real-time communication
- pg8000 - Pure Python PostgreSQL driver

**Frontend:**
- React 18 - UI framework
- Vite - Build tool
- i18next - Multi-language support
- Axios - HTTP client

**Deployment:**
- Docker & Dev Containers
- GitHub Actions (CI/CD ready)
- Neon.tech PostgreSQL
- Vercel/Netlify ready frontend

## Quick Start

### 📚 Full Setup Guide
See [SETUP.md](SETUP.md) for detailed installation instructions.

### ⚡ Quick Setup (5 minutes)

> Примечание: в backend появились простые маршруты для регистрации и логина, используйте их для создания пользователей.

```bash
# Clone
git clone https://github.com/zxDOOMxz/DreaMMO.git
cd DreaMMO

# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Update with your DB credentials
uvicorn main:app --reload

# Frontend (new terminal)
cd frontend
npm install && npm run dev
```

**Access:**
- Backend API: http://localhost:8000
- Swagger Docs: http://localhost:8000/api/docs
- Frontend: http://localhost:5173

## 🗄️ Database Schema

MVP includes tables for:
- **Users & Characters**: Account management, character stats
- **World**: Locations, objects (NPCs, buildings, resources)
- **Combat**: Combat log, hit locations, damage calculations
- **Quests**: Quest chains, progress tracking
- **Crafting**: Recipes, player skill levels
- **Social**: Friends, factions, chat
- **Resources**: Gatherable materials with respawn mechanics

[View Full Schema](backend/database/schema.sql)

## 🎮 Game Design

### Character Progression
- **Stats**: Strength, Dexterity, Constitution, Intelligence, Wisdom, Luck (affects combat, crafting, gathering)
- **Leveling**: Experience from combat, quests, crafting
- **Skills**: Combat, Crafting (and variants), Gathering, Magic
- **Equipment**: Weapons, armor with different damage/protection values

### Combat System
- Turn-based or real-time with stamina
- Hit locations (head, chest, legs)
- Block/parry based on dexterity
- Escape chance based on dexterity vs opponent's strength
- Damage calculation: Attacker strength/weapon vs Defender armor/dexterity

### World Interaction (EVE Online style)
- Locations contain objects displayed as a table:
  ```
  Name              Type        Distance    Filters
  ─────────────────────────────────────────────────
  Joe's Shop        Building    0.5 km      [merchant]
  Iron Ore Deposit  Resource    2.3 km      [ore]
  Guard Captain     NPC         0.1 km      [enemy]
  ```
- Click/interact with objects based on proximity and type

### Crafting (Mortal Online style)
- Gather materials from resource nodes
- Learn recipes from NPCs or books
- Craft improvements affect weapon damage/armor quality
- Success rate based on skill level and intelligence
- Resource consumption tracked per recipe

## 📡 API Structure

```
GET  /api/health              - Server status
GET  /api/test-db             - Database connectivity
WS   /ws/{user_id}            - WebSocket real-time channel
```

Future endpoints structure planned for:
- `/api/auth/` - Authentication
- `/api/characters/` - Character management
- `/api/world/` - Location & objects
- `/api/combat/` - Battle system
- `/api/crafting/` - Crafting system
- `/api/quests/` - Quest management
- `/api/social/` - Friends, factions, chat

## 🎯 MVP Roadmap

**Phase 1 (v0.1) - Core Infrastructure** ✅
- [x] FastAPI backend setup
- [x] PostgreSQL schema design
- [x] WebSocket infrastructure
- [ ] Database initialization script
- [ ] Character creation API
- [ ] Location/object system

**Phase 2 (v0.2) - Game Mechanics**
- [ ] Character stats & progression
- [ ] Combat system (hit/miss/block)
- [ ] Quest system & NPC dialogues
- [ ] Crafting & resource gathering
- [ ] Safe zone & PvP mechanics

**Phase 3 (v0.3) - Social & Polish**
- [ ] Faction system
- [ ] Trade/market system
- [ ] Sound effects & audio narration
- [ ] Mobile UI optimization
- [ ] Performance optimization

## 🤝 Contributing

We welcome contributions! Check out [Issues](https://github.com/zxDOOMxz/DreaMMO/issues) for tasks.

**Development Setup:**
1. Fork the repo
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit: `git commit -m 'feat: add amazing feature'`
4. Push: `git push origin feature/amazing-feature`
5. Open Pull Request

## 📜 License

MIT License - See [LICENSE](LICENSE) for details

**Copyright (c) 2026 zxDOOMxz**

## 🙏 Credits

Inspired by:
- EVE Online (spatial mechanics, location-based interactions)
- Mortal Online (combat depth, crafting, resource gathering)
- Ultima Online & Asheron's Call (classic MMORPG design)
- MUD games (text-based interaction patterns)

## 📞 Support

- 📖 [Full Documentation](SETUP.md)
- 💬 [GitHub Discussions](https://github.com/zxDOOMxz/DreaMMO/discussions)
- 🐛 [Report Bugs](https://github.com/zxDOOMxz/DreaMMO/issues)

---

**Status**: Early Development (MVP)  
**Last Updated**: March 4, 2026  
**Made with ❤️ for MMORPG lovers**
