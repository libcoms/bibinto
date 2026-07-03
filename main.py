import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from middlewares import MaintenanceMiddleware
from handlers import router
from database import init_db

async def main():
    await init_db()
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    # 🔥 Регистрируем ограничение на все сообщения
    dp.message.outer_middleware(MaintenanceMiddleware())
    
    # dp.include_router(...)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")