from aiogram.fsm.state import State, StatesGroup

class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()  # <-- Новый шаг
    waiting_for_photo = State()
    waiting_for_age = State()