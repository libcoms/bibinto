from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_ID

def get_main_menu(user_id: int) -> ReplyKeyboardMarkup:
    """Главное меню. Если зашел админ, ему показывается кнопка админки"""
    buttons = [
        [KeyboardButton(text="🔍 Искать анкеты")],
        [KeyboardButton(text="📝 Моя анкета")]
    ]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="👑 Панель Админа")])
        
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_skip_description_keyboard() -> ReplyKeyboardMarkup:
    """Кнопка для пропуска ввода описания"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Пропустить ➡️")]],
        resize_keyboard=True
    )

def get_rating_keyboard(target_tg_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i in range(1, 11):
        builder.button(text=str(i), callback_data=f"rate:{i}:{target_tg_id}")
    builder.adjust(5, 5)
    return builder.as_markup()

def get_edit_profile_keyboard(is_active: int) -> InlineKeyboardMarkup:
    """Управление своей анкетой: редактирование и скрытие/показ"""
    builder = InlineKeyboardBuilder()
    builder.button(text="⚙️ Изменить анкету", callback_data="edit_profile")
    
    # Текст кнопки зависит от текущего статуса анкеты
    visibility_text = "👁 Скрыть анкету" if is_active == 1 else "👁 Показать анкету"
    builder.button(text=visibility_text, callback_data="toggle_visibility")
    
    builder.adjust(1)
    return builder.as_markup()

def get_admin_menu() -> ReplyKeyboardMarkup:
    """Клавиатура внутри админ-панели"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статистика и метрики")],
            [KeyboardButton(text="📄 Экспорт всех анкет в PDF")],
            [KeyboardButton(text="📥 Выгрузка таблицы (CSV)")],
            [KeyboardButton(text="🔙 Главное меню")]
        ],
        resize_keyboard=True
    )