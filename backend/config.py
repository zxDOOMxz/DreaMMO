import os
from pathlib import Path
from dotenv import load_dotenv

# if .env missing, create from example so config can load
dotenv_path = Path(__file__).parent / ".env"
example_path = Path(__file__).parent / ".env.example"
if not dotenv_path.exists() and example_path.exists():
    with open(example_path, 'r', encoding='utf-8') as src, open(dotenv_path, 'w', encoding='utf-8') as dst:
        dst.write(src.read())
    print("⚠️  .env файл не найден, создан из .env.example. Пожалуйста, отредактируйте его и добавьте DATABASE_URL.")

# Загрузка переменных из .env файла
# если файл не существует, load_dotenv тихо ничего не делает
load_dotenv(dotenv_path)

class Settings:
    # === DATABASE ===
    # сначала читаем из окружения, потом из .env
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    DATABASE_AVAILABLE: bool = bool(DATABASE_URL)
    
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
    APP_NAME: str = "CodeX of Honor API"
    APP_VERSION: str = "0.1.0"
    
    # === CORS (для frontend) ===
    CORS_ORIGINS: list = [
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",
        # В продакшене добавить домен фронтенда
    ]

# Глобальный экземпляр настроек
settings = Settings()