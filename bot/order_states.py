from aiogram.fsm.state import StatesGroup, State

class OrderState(StatesGroup):
    drink = State()
    size = State()
    milk = State()