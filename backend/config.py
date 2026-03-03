import os
from pathlib import Path
from dotenv import load_dotenv

# Загрузка переменных из .env файла
load_dotenv(Path(__file__).parent / ".env")

class Settings:
    # === DATABASE ===
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL не найден в .env файле!")
    
    # === JWT (авторизация) ===
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change_this_in_production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    
    # === SECURITY / RATE LIMITING ===
    RATE_LIMIT_ACTIONS_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_ACTIONS_PER_MINUTE", "60"))
    RATE_LIMIT_BURST: int = int(os.getenv("RATE_LIMIT_BURST", "10"))
    
    # === DEBUG ===
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")
    
    # === APP ===
    APP_NAME: str = "DreaMMO API"
    APP_VERSION: str = "0.1.0"
    
    # === CORS (для frontend) ===
    CORS_ORIGINS: list = [
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",
        # В продакшене добавить домен фронтенда
    ]

# Глобальный экземпляр настроек
settings = Settings()