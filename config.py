import os
from dotenv import load_dotenv

# Загружаем переменные из файла .env в окружение
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_NAME = os.getenv("DB_NAME", "dating_profiles.db")

# Переменные окружения всегда считываются как строки (str),
# поэтому ID админа обязательно приводим к числу (int)
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))