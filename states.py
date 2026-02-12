"""FSM-состояния для сценариев пользователя."""

from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    """Состояния оформления заказа."""

    waiting_photo = State()
    waiting_weight = State()
    waiting_price = State()
