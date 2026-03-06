import psycopg2
from psycopg2 import pool
from typing import Optional
from config import settings

# Глобальный пул соединений
_db_pool: Optional[pool.SimpleConnectionPool] = None


def _dsn_from_url(url: str) -> Optional[str]:
    if not url:
        return None
    # psycopg2 ожидает postgres://
    return url.replace("postgresql://", "postgres://")


async def init_db_pool():
    """
    Инициализация пула соединений с базой данных.
    Вызывается при запуске приложения.
    """
    global _db_pool
    
    if _db_pool is None:
        dsn = _dsn_from_url(settings.DATABASE_URL)
        if not dsn:
            print("[WARNING] DATABASE_URL не задан. Приложение запущено без подключения к БД.")
            return
        print("[INFO] Подключение к базе данных...")
        
        # psycopg2 не async, поэтому используем простой пул
        # Для MVP этого достаточно
        _db_pool = pool.SimpleConnectionPool(
            minconn=2,
            maxconn=10,
            dsn=dsn
        )
        
        print("[OK] База данных подключена!")


async def close_db_pool():
    """
    Закрытие пула соединений.
    """
    global _db_pool
    
    if _db_pool is not None:
        _db_pool.closeall()
        print("🔌 База данных отключена")
        _db_pool = None


def get_db_connection():
    """
    Получение соединения из пула.
    Возвращает контекстный менеджер.
    
    Пример:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users")
    """
    if _db_pool is None:
        raise RuntimeError("База данных не инициализирована!")
    
    return _db_pool.getconn()


def release_db_connection(conn):
    """
    Возврат соединения в пул.
    """
    if _db_pool is not None and conn is not None:
        _db_pool.putconn(conn)


# === Утилиты для быстрых запросов ===
# Примечание: psycopg2 синхронный, поэтому функции не async

def fetch_one(query: str, *args):
    """Получить одну строку результата"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, args)
            return cur.fetchone()
    finally:
        release_db_connection(conn)


def fetch_all(query: str, *args):
    """Получить все строки результата"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, args)
            return cur.fetchall()
    finally:
        release_db_connection(conn)


def fetch_val(query: str, *args):
    """Получить одно значение"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, args)
            result = cur.fetchone()
            return result[0] if result else None
    finally:
        release_db_connection(conn)


def execute(query: str, *args):
    """Выполнить запрос без возврата результата"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if args:
                cur.execute(query, args)
            else:
                cur.execute(query)
            conn.commit()
            return cur.rowcount
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        release_db_connection(conn)


def execute_sql_file(file_path: str):
    """
    Выполнить SQL файл (для инициализации схемы БД).
    
    Пример:
        execute_sql_file('backend/database/schema.sql')
    """
    conn = get_db_connection()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        with conn.cursor() as cur:
            # Выполнить скрипт целиком
            cur.execute(sql_script)
            conn.commit()
        
        print(f"✅ SQL файл {file_path} успешно выполнен")
        return True
    except FileNotFoundError:
        print(f"❌ Файл {file_path} не найден")
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Ошибка при выполнении SQL файла: {e}")
        raise e
    finally:
        release_db_connection(conn)