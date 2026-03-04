#!/bin/bash

# Quick start script for DreaMMO on macOS/Linux

echo ""
echo "🎮 DreaMMO - Local Development Server"
echo "======================================"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
  echo "⚠️  .env file not found!"
  echo "Creating .env from .env.example..."
  cp .env.example .env
  echo "✅ .env created. Please update it with your database credentials."
  read -p "Press enter to continue..."
fi

# Kill existing processes
echo ""
echo "🔄 Checking for existing processes..."
lsof -i :8000 | grep LISTEN | awk '{print $2}' | xargs kill -9 2>/dev/null || true
lsof -i :5173 | grep LISTEN | awk '{print $2}' | xargs kill -9 2>/dev/null || true

# Start Backend
echo ""
echo "🚀 Starting Backend Server..."
cd backend
python3 -m venv venv 2>/dev/null || echo "Virtual environment already exists"
source venv/bin/activate
pip install -q -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# Start Frontend
echo ""
echo "🚀 Starting Frontend Server..."
cd frontend
npm install -q >/dev/null 2>&1
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Servers started!"
echo ""
echo "📊 Backend API: http://localhost:8000"
echo "📋 API Docs:   http://localhost:8000/api/docs"
echo ""
echo "🎨 Frontend:   http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop all servers"
echo ""

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait
