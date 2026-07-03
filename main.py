import asyncio
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

from config import BOT_TOKEN
from database import init_db
from handlers import router as main_router
from middlewares import MaintenanceMiddleware

async def main():
    # 🌟 1. СНАЧАЛА ИНИЦИАЛИЗИРУЕМ БАЗУ ДАННЫХ И МИГРАЦИИ
    # Это гарантирует, что все таблицы и новые колонки создадутся до первого сообщения
    await init_db()
    
    # 🌐 2. НАСТРАИВАЕМ СЕТЕВУЮ СЕССИЮ С УВЕЛИЧЕННЫМИ ТАЙМ-АУТАМИ
    # Защищает от сетевых сбоев TelegramNetworkError на хостинге
    session = AiohttpSession(timeout=aiohttp.ClientTimeout(total=40, connect=15))
    bot = Bot(token=BOT_TOKEN, session=session)
    
    dp = Dispatcher()
    
    # 🛡️ 3. РЕГИСТРИРУЕМ ВЫШИБАЛУ (MIDDLEWARE)
    # Важно зарегистрировать его как outer, чтобы он проверял входящие запросы первее всех
    dp.message.outer_middleware(MaintenanceMiddleware())
    
    # 📥 4. ПОДКЛЮЧАЕМ ОБРАБОТЧИКИ КОМАНД И КНОПОК
    dp.include_router(main_router)
    
    print("Бот успешно запущен и готов к работе!")
    
    # Стираем накопившиеся на сервере Telegram сообщения, пока бот лежал в ошибке,
    # чтобы он не начал спамить ответами на старые запросы
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запуск бесконечного цикла чтения обновлений
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен.")