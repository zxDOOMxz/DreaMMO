@echo off
REM Quick start script for DreaMMO on Windows

echo.
echo 🎮 DreaMMO - Local Development Server
echo ======================================
echo.

REM Check if .env exists
if not exist ".env" (
  echo ⚠️  .env file not found!
  echo Creating .env from .env.example...
  copy .env.example .env
  echo ✅ .env created. Please update it with your database credentials.
  pause
)

REM Kill existing processes on ports
echo.
echo 🔄 Checking for existing processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
  echo Stopping process on port 8000...
  taskkill /PID %%a /F 2>nul || true
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173') do (
  echo Stopping process on port 5173...
  taskkill /PID %%a /F 2>nul || true
)

REM Start Backend
echo.
echo 🚀 Starting Backend Server...
cd backend
python -m venv venv 2>nul || echo Virtual environment already exists
call venv\Scripts\activate.bat
pip install -q -r requirements.txt
start "" cmd /k "uvicorn main:app --reload --host 0.0.0.0 --port 8000"
cd ..

REM Start Frontend
echo.
echo 🚀 Starting Frontend Server...
cd frontend
npm install -q
start "" cmd /k "npm run dev"
cd ..

echo.
echo ✅ Servers starting...
echo.
echo 📊 Backend API: http://localhost:8000
echo 📋 API Docs:   http://localhost:8000/api/docs
echo.
echo 🎨 Frontend:   http://localhost:5173
echo.
echo Press Ctrl+C in each terminal to stop servers.
echo.

pause
