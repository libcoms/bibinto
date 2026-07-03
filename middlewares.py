from aiogram import BaseMiddleware
from aiogram.types import Message
from config import ADMIN_ID

class MaintenanceMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data):
        if isinstance(event, Message):
            # Админа пускаем беспрепятственно при любом статусе рубильника
            if event.from_user.id == ADMIN_ID:
                return await handler(event, data)
            
            # Для остальных пользователей проверяем, включен ли бот
            import database as db
            bot_enabled = await db.is_bot_enabled()
            
            if not bot_enabled:
                await event.answer(
                    "⚠️ **Бот временно недоступен**\n\n"
                    "В данный момент проводятся технические работы или обновление системы. "
                    "Мы скоро вернемся, пожалуйста, попробуйте позже! 🔧"
                )
                return  # Обрываем выполнение, хэндлеры не сработают
                
        return await handler(event, data)