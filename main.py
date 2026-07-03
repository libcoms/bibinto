import asyncio
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from database import init_db
from handlers import router as main_router
from middlewares import MaintenanceMiddleware

async def main():
    # 1. Сначала инициализируем базу данных и миграции
    await init_db()
    
    # 2. Инициализируем бота стандартным, безопасным способом
    bot = Bot(token=BOT_TOKEN)
    
    dp = Dispatcher()
    
    # 3. Регистрируем middleware для режима тех. работ
    dp.message.outer_middleware(MaintenanceMiddleware())
    
    # 4. Подключаем обработчики команд и кнопок
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