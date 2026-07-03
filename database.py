import aiosqlite
from config import DB_NAME

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                name TEXT,
                description TEXT,    -- <-- Новое поле
                photo_id TEXT,
                age INTEGER,
                is_active INTEGER DEFAULT 1
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER,
                to_user_id INTEGER,
                score INTEGER,
                UNIQUE(from_user_id, to_user_id)
            )
        ''')
        await db.commit()

async def add_user(tg_id: int, username: str, name: str, description: str, photo_id: str, age: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT OR REPLACE INTO users (telegram_id, username, name, description, photo_id, age, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        ''', (tg_id, username, name, description, photo_id, age))
        await db.commit()

async def toggle_visibility(tg_id: int) -> int:
    """Переключает статус видимости анкеты (0 или 1). Возвращает новый статус."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT is_active FROM users WHERE telegram_id = ?', (tg_id,)) as cursor:
            res = await cursor.fetchone()
            if not res: return 1
            new_status = 0 if res[0] == 1 else 1
            
        await db.execute('UPDATE users SET is_active = ? WHERE telegram_id = ?', (new_status, tg_id))
        await db.commit()
        return new_status

async def get_user(tg_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT * FROM users WHERE telegram_id = ?', (tg_id,)) as cursor:
            return await cursor.fetchone()

async def get_random_profile(current_tg_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        query = '''
            SELECT telegram_id, username, name, description, photo_id, age FROM users
            WHERE is_active = 1 AND telegram_id != ?
            AND telegram_id NOT IN (
                SELECT to_user_id FROM ratings WHERE from_user_id = ?
            )
            ORDER BY RANDOM() LIMIT 1
        '''
        async with db.execute(query, (current_tg_id, current_tg_id)) as cursor:
            return await cursor.fetchone()

async def save_rating(from_id: int, to_id: int, score: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT OR IGNORE INTO ratings (from_user_id, to_user_id, score)
            VALUES (?, ?, ?)
        ''', (from_id, to_id, score))
        await db.commit()

# --- АДМИН-МЕТОДЫ ---

async def get_admin_stats():
    """Возвращает общие метрики системы"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT COUNT(*) FROM users') as c:
            total_users = (await c.fetchone())[0]
        async with db.execute('SELECT COUNT(*) FROM users WHERE is_active = 1') as c:
            active_users = (await c.fetchone())[0]
        async with db.execute('SELECT COUNT(*) FROM ratings') as c:
            total_ratings = (await c.fetchone())[0]
        return total_users, active_users, total_ratings

async def get_all_users():
    """Получает абсолютно всех пользователей для генерации отчетов"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT telegram_id, username, name, description, age, is_active FROM users') as cursor:
            return await cursor.fetchall()