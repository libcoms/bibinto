import os
import csv
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, FSInputFile
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from fpdf import FPDF

from states import Registration
from config import ADMIN_ID
import database as db
import keyboards as kb

router = Router()

# Вспомогательный класс для PDF с поддержкой русского языка
class CyrillicPDF(FPDF):
    def header(self):
        # Проверяем стандартный путь к шрифту Arial в Windows
        font_path = r"C:\Windows\Fonts\arial.ttf"
        if os.path.exists(font_path):
            self.add_font("Arial", "", font_path)
            self.set_font("Arial", size=16)
        else:
            self.set_font("Helvetica", size=16)
        self.cell(0, 10, "Отчет: База данных анкет бота", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(10)

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    if not message.from_user.username:
        await message.answer("⚠️ У тебя не установлен @username в настройках Telegram! Измени это для работы бота.")
        return

    user = await db.get_user(message.from_user.id)
    if user:
        await message.answer("Добро пожаловать обратно!", reply_markup=kb.get_main_menu(message.from_user.id))
    else:
        await message.answer("Привет! Давай создадим твою анкету. Как тебя зовут?")
        await state.set_state(Registration.waiting_for_name)

# --- ЦЕПОЧКА РЕГИСТРАЦИИ С ОПИСАНИЕМ ---

@router.message(Registration.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(
        f"Приятно познакомиться, {message.text}! Расскажи немного о себе (это будет описанием анкеты):",
        reply_markup=kb.get_skip_description_keyboard()
    )
    await state.set_state(Registration.waiting_for_description)

@router.message(Registration.waiting_for_description)
async def process_description(message: Message, state: FSMContext):
    desc = "" if message.text == "Пропустить ➡️" else message.text
    await state.update_data(description=desc)
    
    # Удаляем текстовую клавиатуру, запрашивая фото
    await message.answer("Отлично! Теперь отправь своё фото:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Registration.waiting_for_photo)

@router.message(Registration.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await message.answer("И последний шаг — введи свой возраст цифрами:")
    await state.set_state(Registration.waiting_for_age)

@router.message(Registration.waiting_for_age)
async def process_age(message: Message, state: FSMContext):
    if not message.text.isdigit() or not (16 <= int(message.text) <= 100):
        await message.answer("Пожалуйста, введи реальный возраст цифрами:")
        return
    
    age = int(message.text)
    data = await state.get_data()
    
    await db.add_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        name=data['name'],
        description=data['description'],
        photo_id=data['photo_id'],
        age=age
    )
    
    await state.clear()
    await message.answer("Ура! Твоя анкета создана!", reply_markup=kb.get_main_menu(message.from_user.id))

# --- УПРАВЛЕНИЕ СВОИМ ПРОФИЛЕМ ---

@router.message(F.text == "📝 Моя анкета")
async def my_profile(message: Message):
    user = await db.get_user(message.from_user.id)
    if user:
        # Учитываем смещение индексов: 0:id, 1:username, 2:name, 3:desc, 4:photo, 5:age, 6:active
        status_text = "🟢 Видна в поиске" if user[6] == 1 else "🔴 Скрыта из поиска"
        caption = f"Твоя анкетa ({status_text}):\n\n👤 Имя: {user[2]}\n🔥 Возраст: {user[5]}\nНик: @{user[1]}"
        if user[3]:
            caption += f"\n📝 Описание: {user[3]}"
            
        await message.answer_photo(
            photo=user[4],
            caption=caption,
            reply_markup=kb.get_edit_profile_keyboard(user[6])
        )

@router.callback_query(F.data == "toggle_visibility")
async def handle_toggle_visibility(callback: CallbackQuery):
    await callback.answer()
    new_status = await db.toggle_visibility(callback.from_user.id)
    
    status_str = "теперь видна всем!" if new_status == 1 else "скрыта. Тебя больше никто не увидит, пока ты сам не включишь её."
    await callback.message.answer(f"Твоя анкета {status_str}")
    
    # Удаляем старое сообщение профиля, чтобы обновить кнопки
    try: await callback.message.delete()
    except Exception: pass

@router.callback_query(F.data == "edit_profile")
async def edit_profile_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Давай перепишем анкету. Как тебя зовут?")
    await state.set_state(Registration.waiting_for_name)

# --- ЛОГИКА ПОИСКА ---

async def send_next_profile(message: Message, bot: Bot, tg_id: int):
    profile = await db.get_random_profile(tg_id)
    if not profile:
        await bot.send_message(tg_id, "Пока что новых анкет нет. Загляни позже! 😉")
        return
    
    # 0:id, 1:username, 2:name, 3:desc, 4:photo, 5:age
    caption = f"🔥 {profile[2]}, {profile[5]}"
    if profile[3]:
        caption += f"\n\n📝 {profile[3]}"
        
    await bot.send_photo(
        chat_id=tg_id,
        photo=profile[4],
        caption=caption,
        reply_markup=kb.get_rating_keyboard(profile[0])
    )

@router.message(F.text == "🔍 Искать анкеты")
async def start_searching(message: Message, bot: Bot):
    # Проверим, не скрыл ли пользователь себя. Позволим искать, только если сам активен
    user = await db.get_user(message.from_user.id)
    if user and user[6] == 0:
        await message.answer("⚠️ Твоя анкета сейчас скрыта. Включи её в меню '📝 Моя анкета', чтобы начать поиск!")
        return
    await send_next_profile(message, bot, message.from_user.id)

@router.callback_query(F.data.startswith("rate:"))
async def handle_rating(callback: CallbackQuery, bot: Bot):
    _, score_str, target_id_str = callback.data.split(":")
    score, target_id, from_id = int(score_str), int(target_id_str), callback.from_user.id
    
    await db.save_rating(from_id, target_id, score)
    await callback.answer(f"Оценка {score} отправлена!")
    
    try: await callback.message.delete()
    except Exception: pass
    
    if score > 5:
        sender = await db.get_user(from_id)
        sender_name = sender[2] if sender else "Кто-то"
        try:
            await bot.send_message(
                chat_id=target_id,
                text=f"🔥 Твоя анкета понравилась пользователю {sender_name}! Оценка: {score}/10\n"
                     f"Ссылка для связи: @{callback.from_user.username}"
            )
        except Exception: pass
            
    await send_next_profile(callback.message, bot, from_id)

# --- ПАНЕЛЬ АДМИНИСТРАТОРА (СТРОГАЯ ПРОВЕРКА ПО ID) ---

@router.message(F.text == "👑 Панель Админа")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("Режим администратора активирован.", reply_markup=kb.get_admin_menu())

@router.message(F.text == "🔙 Главное меню")
async def back_to_main(message: Message):
    await message.answer("Возвращаемся в меню.", reply_markup=kb.get_main_menu(message.from_user.id))

@router.message(F.text == "📊 Статистика и метрики")
async def admin_metrics(message: Message):
    if message.from_user.id != ADMIN_ID: return
    total, active, ratings = await db.get_admin_stats()
    
    await message.answer(
        f"📊 **Метрики бота на текущий момент:**\n\n"
        f"👥 Всего анкет в системе: {total}\n"
        f"🟢 Из них активны (видны): {active}\n"
        f"💤 Из них скрыты: {total - active}\n"
        f"⭐ Всего выставлено оценок: {ratings}"
    )

@router.message(F.text == "📥 Выгрузка таблицы (CSV)")
async def admin_export_csv(message: Message):
    if message.from_user.id != ADMIN_ID: return
    
    users = await db.get_all_users()
    filename = "users_export.csv"
    
    # Генерируем CSV таблицу стандартными средствами Python (Excel откроет без проблем)
    with open(filename, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Telegram ID", "Username", "Имя", "Описание", "Возраст", "Активен (1/0)"])
        for u in users:
            writer.writerow(u)
            
    await message.answer_document(document=FSInputFile(filename), caption="📊 Таблица всех пользователей выгружена!")
    os.remove(filename)

@router.message(F.text == "📄 Экспорт всех анкет в PDF")
async def admin_export_pdf(message: Message):
    if message.from_user.id != ADMIN_ID: return
    
    await message.answer("Генерирую PDF-отчет, это может занять пару секунд...")
    users = await db.get_all_users()
    
    pdf = CyrillicPDF()
    pdf.add_page()
    
    # Подгружаем шрифт для отображения кириллицы
    font_path = r"C:\Windows\Fonts\arial.ttf"
    if os.path.exists(font_path):
        pdf.add_font("Arial", "", font_path)
        pdf.set_font("Arial", size=11)
    else:
        pdf.set_font("Helvetica", size=11)

    for u in users:
        tg_id, username, name, desc, age, active = u
        act_str = "Активен" if active == 1 else "Скрыт"
        
        # Рендерим блок данных для каждого юзера
        text_block = f"ID: {tg_id} | @{username} | {name}, {age} л. ({act_str})\n"
        if desc:
            text_block += f"Описание: {desc}\n"
        text_block += "-" * 50 + "\n"
        
        # multi_cell отлично переносит длинные строки
        pdf.multi_cell(0, 7, text_block)
        pdf.ln(2)
        
    filename = "profiles_report.pdf"
    pdf.output(filename)
    
    await message.answer_document(document=FSInputFile(filename), caption="📄 PDF-отчет со всеми анкетами готов!")
    os.remove(filename)