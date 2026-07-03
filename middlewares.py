# middlewares.py
from aiogram import BaseMiddleware
from aiogram.types import Message
from config import ADMIN_ID
import database as db

class MaintenanceMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data):
        # Проверяем только текстовые сообщения / команды от пользователей
        if isinstance(event, Message):
            # Если пишет Админ — пропускаем без ограничений всегда
            if event.from_user.id == ADMIN_ID:
                return await handler(event, data)
            
            # Если пишет обычный пользователь — проверяем статус бота
            bot_enabled = await db.is_bot_enabled()
            if not bot_enabled:
                await event.answer(
                    "⚠️ **Бот временно недоступен**\n\n"
                    "Сейчас проводятся технические работы. Мы скоро вернемся! 🔧"
                )
                return # Прерываем выполнение, обработчики (handlers) не вызовутся
        
        return await handler(event, data)