# 🎮 DreaMMO Setup Guide

## 📋 Prerequisites

- Python 3.12+
- Node.js 18+
- PostgreSQL 15+ (or Neon.tech cloud database)
- pip & npm

## 🚀 Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/zxDOOMxz/DreaMMO.git
cd DreaMMO
```

### 2. Backend Setup

#### 2.1 Create Python Environment
```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

#### 2.2 Install Dependencies
```bash
pip install -r requirements.txt
```

#### 2.3 Configure Database
1. Copy `.env.example` to `.env`:
```bash
copy .env.example .env  # Windows
# or
cp .env.example .env    # macOS/Linux
```

2. Update `.env` with your database credentials:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/dreammo
JWT_SECRET=your_secret_key_min_32_chars
DEBUG=True
```

3. Initialize database schema:
```bash
# Using psql
psql -U postgres -d dreammo -f backend/database/schema.sql

# Or with Python (recommended for cloud databases)
python -c "
from backend.database.connection import execute_file
execute_file('backend/database/schema.sql')
"
```

#### 2.4 Run Backend Server
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at: `http://localhost:8000`
- API Docs: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`

### 3. Frontend Setup

#### 3.1 Install Dependencies
```bash
cd frontend
npm install
```

#### 3.2 Run Development Server
```bash
npm run dev
```

Frontend will be available at: `http://localhost:5173`

#### 3.3 Build for Production
```bash
npm run build
npm run preview
```

---

## 🗄️ Database Setup (Neon.tech)

If using Neon.tech cloud database:

1. Create project at https://console.neon.tech
2. Copy connection string to `.env`:
```env
DATABASE_URL=postgresql://user:password@ep-xyz-123.neon.tech/neondb
```

3. Run schema initialization (using your connection string)

---

## 🐳 Docker Setup (Optional)

### Using DevContainer in VS Code
1. Open the project in VS Code
2. Install "Dev Containers" extension
3. Press `Ctrl+Shift+P` → "Dev Containers: Reopen in Container"
4. Container will build and set everything up

### Manual Docker
```bash
# Build
docker build -t dreammo-backend -f backend/.devcontainer/Dockerfile .

# Run
docker run -p 8000:8000 --env-file .env dreammo-backend
```

---

## 📝 API Endpoints (MVP)

### Health Check
```
GET /api/health
```

### Test Database
```
GET /api/test-db
```

### WebSocket (Real-time)
```
WebSocket /ws/{user_id}
```

---

## 📚 Project Structure

```
DreaMMO/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration & settings
│   ├── requirements.txt      # Python dependencies
│   ├── database/
│   │   ├── connection.py     # Database connection pool
│   │   └── schema.sql        # Database schema
│   ├── .devcontainer/        # Docker dev environment
│   └── __init__.py
├── frontend/
│   ├── package.json          # Node.js dependencies
│   ├── src/                  # React components
│   └── index.html
├── .env.example              # Environment template
├── .gitignore
├── README.md
├── LICENSE
└── SETUP.md                  # This file
```

---

## 🔧 Development Workflow

### Adding New Features

1. **Backend Route**:
   - Add endpoint in `backend/main.py`
   - Test with `/api/docs`

2. **Database Schema**:
   - Update `backend/database/schema.sql`
   - Run migrations

3. **Frontend Component**:
   - Create React component in `frontend/src/`
   - Call API with axios

### Git Workflow
```bash
# Create feature branch
git checkout -b feature/my-feature

# Make changes
git add .
git commit -m "feat: add my feature"

# Push to GitHub
git push origin feature/my-feature

# Create Pull Request on GitHub
```

---

## 🧪 Testing

### Test Backend API
```bash
# Using curl
curl http://localhost:8000/api/health

# Using Python
python -m pytest backend/tests/
```

### Test WebSocket
```javascript
// In browser console
const ws = new WebSocket("ws://localhost:8000/ws/player1");
ws.onmessage = (event) => console.log(event.data);
ws.send(JSON.stringify({type: "move", x: 10, y: 20}));
```

---

## 🆘 Troubleshooting

### Database Connection Failed
- Check `.env` DATABASE_URL is correct
- Ensure PostgreSQL is running: `psql --version`
- Test connection: `psql <your-database-url>`

### Port Already in Use
```bash
# Kill process on port 8000
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# macOS/Linux
lsof -i :8000
kill -9 <PID>
```

### Module Not Found
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
npm install
```

---

## 📖 Resources

- **FastAPI**: https://fastapi.tiangolo.com/
- **React 18**: https://react.dev/
- **PostgreSQL**: https://www.postgresql.org/docs/
- **Neon.tech**: https://neon.tech/docs/

---

## 📄 License

MIT License - see LICENSE file

---

## 👨‍💻 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

---

## 🎮 Game Development Roadmap

### MVP Phase (v0.1)
- [x] API structure
- [x] Database schema
- [ ] Character creation
- [ ] Location system
- [ ] Basic combat mechanics
- [ ] Quest system
- [ ] Crafting system

### Phase 2 (v0.2)
- [ ] NPC interactions
- [ ] Faction system
- [ ] Player-vs-Player combat
- [ ] Trading system
- [ ] Advanced crafting
- [ ] Sound effects

### Phase 3 (v0.3+)
- [ ] Dungeons & raids
- [ ] Advanced economy
- [ ] Mobile app optimization
- [ ] Rankings & leaderboards
- [ ] Streaming features

---

**Last Updated**: March 4, 2026
**Project Status**: Early Development (MVP)
