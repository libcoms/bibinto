import os
import csv
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.exceptions import TelegramBadRequest  # 🛡️ Импортируем защиту от ошибок Telegram
from fpdf import FPDF

from config import ADMIN_ID
import database as db

router = Router()

# ==========================================
# 📋 СОСТОЯНИЯ ДЛЯ РЕГИСТРАЦИИ (FSM)
# ==========================================
class RegistrationStates(StatesGroup):
    name = State()
    age = State()
    description = State()
    photo = State()

# ==========================================
# 🛠️ ВСПОМОГАТЕЛЬНЫЕ КЛАССЫ И ФУНКЦИИ
# ==========================================
class CyrillicPDF(FPDF):
    """Кастомный класс для корректной работы PDF с кириллицей"""
    def header(self):
        pass
    def footer(self):
        pass

def generate_rating_bar(score: float) -> str:
    """Генерирует визуальную шкалу звезд для рейтинга"""
    filled_stars = int(round(score))
    return "⭐" * filled_stars + "⚫" * (5 - filled_stars)

def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """Генерирует главное меню в зависимости от роли пользователя"""
    buttons = [
        [KeyboardButton(text="🔍 Смотреть анкеты")],
        [KeyboardButton(text="👤 Моя анкета"), KeyboardButton(text="👁️ Скрыть/Показать анкету")]
    ]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="🔧 Панель управления")])
        
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# ==========================================
# 🚀 БАЗОВЫЕ КОМАНДЫ И РЕГИСТРАЦИЯ
# ==========================================
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if user:
        await message.answer(f"Привет, {user[2]}! Рад видеть тебя снова.", reply_markup=get_main_keyboard(message.from_user.id))
    else:
        await message.answer("Привет! Добро пожаловать в бот знакомств. Давай создадим твою анкету.\n\nКак тебя зовут?")
        await state.set_state(RegistrationStates.name)

@router.message(RegistrationStates.name)
async def reg_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Сколько тебе лет?")
    await state.set_state(RegistrationStates.age)

@router.message(RegistrationStates.age)
async def reg_age(message: Message, state: FSMContext):
    if not message.text.isdigit() or not (16 <= int(message.text) <= 99):
        await message.answer("Пожалуйста, введи корректный возраст цифрами (от 16 до 99):")
        return
    await state.update_data(age=int(message.text))
    await message.answer("Расскажи немного о себе (твои хобби, интересы):")
    await state.set_state(RegistrationStates.description)

@router.message(RegistrationStates.description)
async def reg_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Пришли своё лучшее фото для анкеты:")
    await state.set_state(RegistrationStates.photo)

@router.message(RegistrationStates.photo, F.photo)
async def reg_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    user_data = await state.get_data()
    
    await db.add_user(
        tg_id=message.from_user.id,
        username=message.from_user.username or "сокрыт",
        name=user_data['name'],
        description=user_data['description'],
        photo_id=photo_id,
        age=user_data['age']
    )
    
    await state.clear()
    await message.answer("✨ Твоя анкета успешно создана и сохранена!", reply_markup=get_main_keyboard(message.from_user.id))

# ==========================================
# 🔍 ПРОСМОТР АНКЕТ И ОЦЕНКА
# ==========================================
async def send_next_profile(message: Message, user_id: int):
    profile = await db.get_random_profile(user_id)
    if not profile:
        await message.answer("Ты посмотрел все доступные анкеты на сегодня! Загляни позже. 😉")
        return

    p_id, p_username, p_name, p_desc, p_photo, p_age = profile
    caption = f"🔥 {p_name}, {p_age}\n\n{p_desc}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1️⃣", callback_data=f"rate_{p_id}_1"),
            InlineKeyboardButton(text="2️⃣", callback_data=f"rate_{p_id}_2"),
            InlineKeyboardButton(text="3️⃣", callback_data=f"rate_{p_id}_3"),
            InlineKeyboardButton(text="4️⃣", callback_data=f"rate_{p_id}_4"),
            InlineKeyboardButton(text="5️⃣", callback_data=f"rate_{p_id}_5")
        ],
        [InlineKeyboardButton(text="➡️ Пропустить", callback_data=f"rate_{p_id}_0")]
    ])
    
    await message.answer_photo(photo=p_photo, caption=caption, reply_markup=keyboard)

@router.message(F.text == "🔍 Смотреть анкеты")
async def start_viewing(message: Message):
    await send_next_profile(message, message.from_user.id)

@router.callback_query(F.data.startswith("rate_"))
async def handle_rating(callback: CallbackQuery):
    _, to_id, score = callback.data.split("_")
    to_id, score = int(to_id), int(score)
    
    if score > 0:
        await db.save_rating(callback.from_user.id, to_id, score)
        
    await callback.answer("Оценка учтена!")
    
    # 🛡️ Безопасное удаление старой анкеты с защитой от двойного клика
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        # Если сообщение уже удалено предыдущим кликом — просто игнорируем ошибку
        pass
        
    await send_next_profile(callback.message, callback.from_user.id)

# ==========================================
# 👤 УПРАВЛЕНИЕ ЛИЧНЫМ ПРОФИЛЕМ
# ==========================================
@router.message(F.text == "👤 Моя анкета")
async def show_my_profile(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Твоя анкета не найдена. Напиши /start для регистрации.")
        return
        
    status = "🟢 Видима для всех" if user[6] == 1 else "🔴 Скрыта от остальных"
    caption = f"👤 **Твой профиль:**\n\nИмя: {user[2]}, {user[5]}\nО себе: {user[3]}\nСтатус: {status}"
    
    await message.answer_photo(photo=user[4], caption=caption, parse_mode="Markdown")

@router.message(F.text == "👁️ Скрыть/Показать анкету")
async def toggle_profile_visibility(message: Message):
    new_status = await db.toggle_visibility(message.from_user.id)
    if new_status == 1:
        await message.answer("🟢 Твоя анкета снова активна и участвует в поиске!")
    else:
        await message.answer("🔴 Твоя анкета успешно скрыта. Тебя больше никто не увидит.")

@router.message(F.text == "⬅️ Назад в меню")
async def back_to_menu(message: Message):
    await message.answer("Возвращаемся в главное меню.", reply_markup=get_main_keyboard(message.from_user.id))

# ==========================================
# 👑 АДМИНИСТРАТИВНАЯ ПАНЕЛЬ
# ==========================================
@router.message(F.text == "🔧 Панель управления")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID: return
    
    is_enabled = await db.is_bot_enabled()
    status_text = "🟢 Бот запущен" if is_enabled else "🔴 Бот выключен (Тех. работы)"
    toggle_btn_text = "🛑 Выключить бота" if is_enabled else "✅ Включить бота"
    
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏆 ТОП-5 Анкет"), KeyboardButton(text="📊 Общая статистика")],
            [KeyboardButton(text="📥 Выгрузка таблицы (CSV)"), KeyboardButton(text="📄 Экспорт всех анкет в PDF")],
            [KeyboardButton(text=toggle_btn_text)],
            [KeyboardButton(text="⬅️ Назад в меню")]
        ],
        resize_keyboard=True
    )
    await message.answer(f"Добро пожаловать в админку!\nТекущий статус: **{status_text}**", reply_markup=kb)

@router.message(F.text.in_({"🛑 Выключить бота", "✅ Включить бота"}))
async def handle_toggle_bot(message: Message):
    if message.from_user.id != ADMIN_ID: return
    
    new_status = await db.toggle_bot_status()
    if new_status:
        await message.answer("✅ Бот успешно **включен** для всех пользователей!")
    else:
        await message.answer("🛑 Бот **выключен** для всех (включен режим тех. работ).")
        
    await admin_panel(message)

@router.message(F.text == "📊 Общая статистика")
async def show_admin_stats(message: Message):
    if message.from_user.id != ADMIN_ID: return
    
    total, active, ratings = await db.get_admin_stats()
    text = (
        "📊 **АНАЛИТИКА СИСТЕМЫ**\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"👥 Всего анкет в базе: `{total}`\n"
        f"🟢 Активных (видимых): `{active}`\n"
        f"💤 Скрытых профилей: `{total - active}`\n"
        f"⭐ Всего выставлено оценок: `{ratings}`\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(F.text == "🏆 ТОП-5 Анкет")
async def show_top_ratings(message: Message):
    if message.from_user.id != ADMIN_ID: return
    
    top_profiles = await db.get_top_rated_profiles(limit=5)
    if not top_profiles:
        await message.answer("Пока никто не оценил ни одну анкету. Рейтинг пуст! 🤷‍♂️")
        return
        
    response = "🏆 **РЕЙТИНГ ЛУЧШИХ АНКЕТ БОТА** 🏆\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    
    for idx, profile in enumerate(top_profiles):
        name, age, username, avg_score, votes = profile
        username_link = f"@{username}" if username and username != "сокрыт" else "нет юзернейма"
        bar = generate_rating_bar(avg_score)
        
        response += f"{medals[idx]} **{name}, {age}** ({username_link})\n"
        response += f"┣ Средний балл: `{avg_score:.2f}` из 5\n"
        response += f"┣ Визуально: {bar}\n"
        response += f"┗ Всего голосов: `{votes}`\n\n"
        
    response += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n*Рейтинг обновляется автоматически.*"
    await message.answer(response, parse_mode="Markdown")

# ==========================================
# 📥 ЭКСПОРТ ДАННЫХ
# ==========================================
@router.message(F.text == "📥 Выгрузка таблицы (CSV)")
async def admin_export_csv(message: Message):
    if message.from_user.id != ADMIN_ID: return
    
    users = await db.get_all_users()
    filename = "/data/users_export.csv"
    
    with open(filename, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Telegram ID", "Username", "Имя", "Описание", "Возраст", "Активен (1/0)"])
        for u in users:
            writer.writerow(u)
            
    await message.answer_document(document=FSInputFile(filename), caption="📊 Таблица всех пользователей выгружена!")
    if os.path.exists(filename): os.remove(filename)

@router.message(F.text == "📄 Экспорт всех анкет в PDF")
async def admin_export_pdf(message: Message):
    if message.from_user.id != ADMIN_ID: return
    
    await message.answer("Генерирую PDF-отчет...")
    users = await db.get_all_users()
    
    pdf = CyrillicPDF()
    pdf.add_page()
    
    font_path = "arial.ttf"
    if os.path.exists(font_path):
        pdf.add_font("Arial", "", font_path, uni=True)
        pdf.set_font("Arial", size=11)
    else:
        pdf.set_font("Helvetica", size=11)

    for u in users:
        tg_id, username, name, desc, age, active = u
        act_str = "Активен" if active == 1 else "Скрыт"
        text_block = f"ID: {tg_id} | @{username} | {name}, {age} y.o. ({act_str})\n"
        if desc: text_block += f"Bio: {desc}\n"
        text_block += "-" * 50 + "\n"
        pdf.multi_cell(0, 7, text_block)
        pdf.ln(2)
        
    filename = "/data/profiles_report.pdf"
    pdf.output(filename)
    
    await message.answer_document(document=FSInputFile(filename), caption="📄 PDF-отчет со всеми анкетами готов!")
    if os.path.exists(filename): os.remove(filename)