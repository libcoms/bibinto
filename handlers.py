import os
import csv
import html  # 🛡️ Импортируем модуль для безопасного экранирования текста пользователей
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder
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
    def header(self):
        pass
    def footer(self):
        pass

def generate_rating_bar(score: float) -> str:
    # Ограничиваем максимум 10 звездами
    filled_stars = int(round(score))
    return "⭐" * filled_stars + "⚫" * (10 - filled_stars)

def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="🔍 Смотреть анкеты"), KeyboardButton(text="🏆 ТОП анкет")],
        [KeyboardButton(text="👤 Моя анкета")]
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
        await message.answer(f"Привет, {html.escape(user[2])}! Рад видеть тебя снова.", reply_markup=get_main_keyboard(message.from_user.id))
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
    await message.answer("✨ Твоя анкета успешно сохранена!", reply_markup=get_main_keyboard(message.from_user.id))

# ==========================================
# 🔍 ПРОСМОТР АНКЕТ И ОЦЕНКА (10 БАЛЛОВ)
# ==========================================
async def send_next_profile(message: Message, user_id: int):
    profile = await db.get_random_profile(user_id)
    if not profile:
        await message.answer("Ты посмотрел все доступные анкеты на сегодня! Загляни позже. 😉")
        return

    p_id, p_username, p_name, p_desc, p_photo, p_age = profile
    
    safe_name = html.escape(str(p_name))
    safe_desc = html.escape(str(p_desc))
    
    if p_id == ADMIN_ID:
        caption = f"👑 <b>PREMIUM PROFILE</b> 👑\n🔥 {safe_name}, {p_age} [Разработчик]\n\n{safe_desc}"
    else:
        caption = f"🔥 {safe_name}, {p_age}\n\n{safe_desc}"
    
    # Строим 10-балльную клавиатуру (2 ряда по 5 кнопок) + кнопка пропуска
    builder = InlineKeyboardBuilder()
    for i in range(1, 11):
        builder.button(text=str(i), callback_data=f"rate_{p_id}_{i}")
    builder.adjust(5, 5)
    
    # Добавляем кнопку "Пропустить" отдельной строкой
    inline_kb = builder.as_markup()
    inline_kb.inline_keyboard.append([InlineKeyboardButton(text="➡️ Пропустить", callback_data=f"rate_{p_id}_0")])
    
    await message.answer_photo(photo=p_photo, caption=caption, reply_markup=inline_kb, parse_mode="HTML")

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
    
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
        
    await send_next_profile(callback.message, callback.from_user.id)

# ==========================================
# 👤 УПРАВЛЕНИЕ ЛИЧНЫМ ПРОФИЛЕМ (РЕДАКТИРОВАНИЕ)
# ==========================================
@router.message(F.text == "👤 Моя анкета")
async def show_my_profile(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Твоя анкета не найдена. Напиши /start для регистрации.")
        return
        
    status = "🟢 Видима для всех" if user[6] == 1 else "🔴 Скрыта от остальных"
    safe_name = html.escape(str(user[2]))
    safe_desc = html.escape(str(user[3]))
    
    if user[0] == ADMIN_ID:
        caption = f"👑 <b>Твой профиль (PREMIUM DEVELOPER):</b>\n\nИмя: {safe_name}, {user[5]}\nО себе: {safe_desc}\nСтатус: {status}"
    else:
        caption = f"👤 <b>Твой профиль:</b>\n\nИмя: {safe_name}, {user[5]}\nО себе: {safe_desc}\nСтатус: {status}"
    
    # Создаем инлайн-кнопки под анкетой
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Изменить анкету", callback_data="profile_edit")],
        [InlineKeyboardButton(text="👁️ Скрыть/Показать анкету", callback_data="profile_toggle")]
    ])
    
    await message.answer_photo(photo=user[4], caption=caption, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "profile_edit")
async def edit_profile_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer("Давай обновим твою анкету! Как тебя зовут?")
    await state.set_state(RegistrationStates.name)
    await callback.answer()

@router.callback_query(F.data == "profile_toggle")
async def toggle_profile_callback(callback: CallbackQuery):
    new_status = await db.toggle_visibility(callback.from_user.id)
    status_text = "🟢 Твоя анкета снова активна!" if new_status == 1 else "🔴 Твоя анкета успешно скрыта."
    
    await callback.answer(status_text, show_alert=True)
    
    # Обновляем профиль на экране, чтобы статус визуально поменялся
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    # Перевызываем функцию отображения
    # Имитируем объект Message для переиспользования функции
    callback.message.from_user = callback.from_user 
    await show_my_profile(callback.message)

@router.message(F.text == "⬅️ Назад в меню")
async def back_to_menu(message: Message):
    await message.answer("Возвращаемся в главное меню.", reply_markup=get_main_keyboard(message.from_user.id))

# ==========================================
# 🏆 ПРОСМОТР РЕЙТИНГА АНКЕТ (ОБЩИЙ ДОСТУП)
# ==========================================
@router.message(F.text.in_({"🏆 ТОП анкет", "🏆 ТОП-5 Анкет"}))
async def show_top_ratings(message: Message):
    top_profiles = await db.get_top_rated_profiles(limit=5)
    if not top_profiles:
        await message.answer("Пока никто не оценил ни одну анкету. Рейтинг пуст! 🤷‍♂️")
        return
        
    response = "🏆 <b>РЕЙТИНГ ЛУЧШИХ АНКЕТ БОТА</b> 🏆\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    
    for idx, profile in enumerate(top_profiles):
        tg_id, name, age, username, avg_score, votes = profile
        username_link = f"@{username}" if username and username != "сокрыт" else "нет юзернейма"
        
        safe_name = html.escape(str(name))
        safe_username = html.escape(str(username_link))
        bar = generate_rating_bar(avg_score)
        
        if tg_id == ADMIN_ID:
            premium_tag = " ✨ [⚡ PREMIUM]"
            response += f"{medals[idx]} <b>{safe_name}, {age}</b>{premium_tag} ({safe_username})\n"
        else:
            response += f"{medals[idx]} <b>{safe_name}, {age}</b> ({safe_username})\n"
            
        response += f"┣ Средний балл: <code>{avg_score:.2f}</code> из 10\n"
        response += f"┣ Визуально: {bar}\n"
        response += f"┗ Всего голосов: <code>{votes}</code>\n\n"
        
    response += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n*<i>Рейтинг использует умную систему взвешивания оценок.</i>"
    await message.answer(response, parse_mode="HTML")

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
    await message.answer(f"Добро пожаловать в админку!\nТекущий статус: <b>{status_text}</b>", reply_markup=kb, parse_mode="HTML")

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
        "📊 <b>АНАЛИТИКА СИСТЕМЫ</b>\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"👥 Всего анкет в базе: <code>{total}</code>\n"
        f"🟢 Активных (видимых): <code>{active}</code>\n"
        f"💤 Скрытых профилей: <code>{total - active}</code>\n"
        f"⭐ Всего выставлено оценок: <code>{ratings}</code>\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"
    )
    await message.answer(text, parse_mode="HTML")

# ==========================================
# 📥 ЭКСПОРТ ДАННЫХ
# ==========================================
@router.message(F.text == "📥 Выгрузка таблицы (CSV)")
async def admin_export_csv(message: Message):
    if message.from_user.id != ADMIN_ID: return
    
    users = await db.get_all_users()
    filename = "users_export.csv"
    
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
        
    filename = "profiles_report.pdf"
    pdf.output(filename)
    
    await message.answer_document(document=FSInputFile(filename), caption="📄 PDF-отчет со всеми анкетами готов!")
    if os.path.exists(filename): os.remove(filename)