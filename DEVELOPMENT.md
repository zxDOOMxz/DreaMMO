# 👨‍💻 DreaMMO Development Guide

## Project Overview

DreaMMO is a text-based MMORPG that combines game mechanics from:
- **EVE Online**: Location-based interactions, spatial mechanics
- **Mortal Online**: Combat depth, crafting, resource gathering
- **Classic MMORPGs**: Quest systems, NPCs, social features

## Architecture

### Backend (Python/FastAPI)
```
backend/
├── main.py              - FastAPI application & websockets
├── config.py            - Configuration management
├── routes.py            - Game API endpoints
├── database/
│   ├── connection.py    - Database pool & utilities
│   └── schema.sql       - Database schema
└── .devcontainer/       - Docker development environment
```

### Frontend (React/Vite)
```
frontend/
├── src/
│   ├── App.jsx          - Main application component
│   ├── main.jsx         - React entry point
│   └── index.css        - Global styles
├── index.html           - HTML template
├── vite.config.js       - Vite configuration
└── package.json         - Dependencies
```

### Database (PostgreSQL)
- **Location-based**: Locations with objects (NPCs, buildings, resources)
- **Character progression**: Stats, levels, experience, inventory
- **Combat system**: Combat logs with hit tracking
- **Crafting**: Recipes, skill progression, materials
- **Social**: Friends, factions, chat
- **Quests**: Quest chains with objectives and rewards

## Development Workflow

### 1. Setting Up Development Environment

```bash
# Clone repository
git clone https://github.com/zxDOOMxz/DreaMMO.git
cd DreaMMO

# Windows: run_local.bat
./run_local.bat

# macOS/Linux: run_local.sh
chmod +x run_local.sh
./run_local.sh
```

### 2. Creating New Features

#### Backend (API Endpoint)

**Example: Add "Move Character" endpoint**

1. Add function to `backend/routes.py`:
```python
@router.post("/character/{character_id}/move", response_model=dict)
async def move_character(character_id: int, location_id: int):
    """Move character to new location"""
    try:
        # Update player status
        execute("""
            UPDATE player_status 
            SET current_location_id = %s, updated_at = CURRENT_TIMESTAMP
            WHERE character_id = %s
        """, location_id, character_id)
        
        return {
            "status": "moved",
            "character_id": character_id,
            "location_id": location_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

2. Test endpoint:
   - Go to http://localhost:8000/api/docs
   - Use Swagger UI to test

#### Frontend (React Component)

**Example: Location View Component**

1. Create `frontend/src/components/LocationView.jsx`:
```jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';

function LocationView({ location_id }) {
  const [location, setLocation] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLocation();
  }, [location_id]);

  const fetchLocation = async () => {
    try {
      const response = await axios.get(
        `http://localhost:8000/api/locations/${location_id}`
      );
      setLocation(response.data);
    } catch (error) {
      console.error('Failed to load location:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      <h2>{location.name}</h2>
      <p>{location.description}</p>
      
      <h3>Objects in this location:</h3>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Distance</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {location.objects.map((obj) => (
            <tr key={obj.id}>
              <td>{obj.name}</td>
              <td>{obj.type}</td>
              <td>{obj.distance_km} km</td>
              <td>
                <button onClick={() => interact(obj.id)}>
                  {obj.interaction}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default LocationView;
```

2. Use in `App.jsx`:
```jsx
import LocationView from './components/LocationView';

function App() {
  return <LocationView location_id={1} />;
}
```

### 3. Database Schema Modifications

1. Edit `backend/database/schema.sql` to add/modify tables
2. Backup current data (for production)
3. Run initialization:
```python
from backend.database.connection import execute_sql_file
execute_sql_file('backend/database/schema.sql')
```

### 4. Git Workflow

```bash
# Create feature branch
git checkout -b feature/character-movement

# Make changes
git add .
git commit -m "feat: add character movement mechanics"

# Push to GitHub
git push origin feature/character-movement

# Create Pull Request on GitHub
```

## Game Mechanics Implementation Checklist

### Combat System
- [ ] Calculate hit chance (weapon skill + dexterity)
- [ ] Calculate damage (strength + weapon damage - armor)
- [ ] Implement hit locations (head, chest, legs, arms)
- [ ] Add block/parry mechanics (dexterity based)
- [ ] Implement escape mechanics (dexterity vs strength)
- [ ] Create combat log system
- [ ] Add combat animations/descriptions

### Crafting System
- [ ] Define recipe structure
- [ ] Implement material gathering
- [ ] Add crafting skill progression
- [ ] Implement success/failure rates
- [ ] Add crafting time calculations
- [ ] Create item quality modifiers
- [ ] Implement tool requirements (pickaxe, etc)

### Quest System
- [ ] Design quest types (kill, collect, explore, delivery)
- [ ] Implement quest progress tracking
- [ ] Add NPC dialogue/quest-giver
- [ ] Create quest rewards (experience, items, gold)
- [ ] Add quest chains/prerequisites
- [ ] Implement quest markers on map

### Social System
- [ ] Create friend system
- [ ] Implement faction system
- [ ] Add chat channels (global, location, faction, private)
- [ ] Create player profiles
- [ ] Add trading system
- [ ] Implement leaderboards

### Content
- [ ] Create locations/zones
- [ ] Design NPCs and dialogues
- [ ] Define items and weapons
- [ ] Balance game economy
- [ ] Create starter experience
- [ ] Design end-game content

## Testing

### Backend Tests
```bash
cd backend
pytest
```

### Frontend Tests
```bash
cd frontend
npm test
```

### Manual Testing
1. Browser DevTools (F12)
2. Check API responses in Network tab
3. Test WebSocket in Console:
```javascript
const ws = new WebSocket("ws://localhost:8000/ws/player1");
ws.onmessage = (e) => console.log(e.data);
ws.send(JSON.stringify({type: "test"}));
```

## Performance Optimization

### Backend
- Use database indexes effectively
- Implement caching for frequently accessed data
- Use connection pooling (already configured)
- Implement rate limiting
- Add query pagination for large result sets

### Frontend
- Lazy load components
- Optimize bundle size
- Use React.memo for expensive components
- Implement virtual scrolling for long lists
- Cache API responses

## Deployment

### Backend (Vercel/Render/Railway)
1. Push to GitHub
2. Connect repository to deployment platform
3. Set environment variables
4. Deploy

### Frontend (Vercel/Netlify)
1. Push to GitHub
2. Connect repository
3. Trigger automatic build/deploy

### Database (Neon.tech)
- Already connected via DATABASE_URL environment variable
- Migrations handled via `schema.sql`

## Useful Resources

- **FastAPI**: https://fastapi.tiangolo.com/
- **React**: https://react.dev/
- **PostgreSQL**: https://www.postgresql.org/docs/
- **WebSocket**: https://developer.mozilla.org/en-US/docs/Web/API/WebSocket
- **Vite**: https://vitejs.dev/

## Common Issues

### Database Connection Failed
```
Solution: Check DATABASE_URL in .env and ensure PostgreSQL is running
```

### Port Already in Use
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# macOS/Linux
lsof -i :8000
kill -9 <PID>
```

### Module Not Found
```bash
pip install -r requirements.txt
npm install
```

### CORS Issues
- Update CORS_ORIGINS in backend/config.py
- Development frontend URL is already added

## Contributing

1. Create a feature branch from `develop`
2. Make your changes
3. Test thoroughly
4. Submit a Pull Request
5. Wait for code review

Please follow the existing code style and add tests for new features.

## Questions?

- Check [README.md](README.md) for project overview
- Check [SETUP.md](SETUP.md) for setup instructions
- Open an issue on GitHub for bugs/features

---

**Happy Coding! 🎮**
