from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database.connection import init_db_pool, close_db_pool, fetch_one, execute, fetch_val
from .routes import router as game_router

# === Жизненный цикл приложения ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Инициализация при старте и очистка при остановке.
    """
    # STARTUP: Подключение к БД
    await init_db_pool()
    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} запущен!")
    yield
    # SHUTDOWN: Отключение от БД
    await close_db_pool()
    print("🛑 Приложение остановлено")


# === Создание приложения ===
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Text-based MMORPG API with mobile-first UI",
    lifespan=lifespan,
    docs_url="/api/docs",  # Swagger UI
    redoc_url="/api/redoc"  # ReDoc
)

# === CORS Middleware (разрешаем frontend доступ) ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Include game routes ===
app.include_router(game_router)


# === Простой health check ===
@app.get("/api/health")
async def health_check():
    """Проверка работоспособности API"""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": "connected" if True else "disconnected"  # TODO: реальная проверка
    }


# === Тест подключения к БД ===
@app.get("/api/test-db")
def test_database():
    """Тестовый запрос к базе данных"""
    try:
        # psycopg2 функции синхронные - без await
        count = fetch_val("SELECT COUNT(*) FROM users")
        return {
            "status": "ok",
            "users_count": count,
            "message": "Database connection successful"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


# === WebSocket менеджер (заглушка для MVP) ===
class ConnectionManager:
    """Управление WebSocket подключениями игроков"""
    
    def __init__(self):
        # {user_id: WebSocket}
        self.active_connections: dict = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """Подключение игрока"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        print(f"🔗 Player {user_id} connected via WebSocket")
    
    def disconnect(self, user_id: str):
        """Отключение игрока"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            print(f"🔌 Player {user_id} disconnected")
    
    async def send_personal_message(self, message: dict, user_id: str):
        """Отправка сообщения конкретному игроку"""
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json(message)
    
    async def broadcast_location(self, message: dict, location_id: int):
        """Рассылка сообщения всем игрокам в локации (заглушка)"""
        # TODO: реализовать фильтрацию по location_id
        for connection in self.active_connections.values():
            await connection.send_json(message)

# Глобальный экземпляр менеджера
manager = ConnectionManager()


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """
    WebSocket эндпоинт для real-time связи с клиентом.
    """
    # TODO: Добавить проверку JWT токена здесь
    await manager.connect(websocket, user_id)
    try:
        while True:
            # Получение сообщения от клиента
            data = await websocket.receive_json()
            
            # Эхо-ответ для тестирования (удалить в продакшене)
            await manager.send_personal_message(
                {"type": "echo", "received": data}, 
                user_id
            )
            
            # TODO: Здесь будет обработка команд:
            # - move: перемещение
            # - attack: атака
            # - chat: сообщение в чат
            # - interact: взаимодействие с объектом
            
    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception as e:
        print(f"❌ WebSocket error for {user_id}: {e}")
        manager.disconnect(user_id)


# === Корневой эндпоинт ===
@app.get("/")
async def root():
    """Информация об API"""
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "docs": "/api/docs",
        "health": "/api/health",
        "websocket": "/ws/{user_id}"
    }