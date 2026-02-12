"""Клавиатуры бота: reply и inline."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


CATEGORIES: list[tuple[str, int]] = [
    ("👕 Одежда", 550),
    ("👟 Обувь", 900),
    ("⌚ Часы", 250),
    ("📱 Смартфоны", 420),
    ("🎧 Наушники", 300),
    ("💻 Ноутбуки", 2100),
    ("🖥️ Комплектующие ПК", 700),
    ("🎮 Игровые аксессуары", 450),
    ("🏠 Товары для дома", 800),
    ("🍳 Кухонная утварь", 650),
    ("💄 Косметика", 180),
    ("🧴 Уход за телом", 220),
    ("👶 Детские товары", 750),
    ("🧸 Игрушки", 500),
    ("🚗 Автотовары", 1100),
    ("🚲 Велотовары", 1700),
    ("🏋️ Спорт и фитнес", 1200),
    ("🏕️ Туризм", 1300),
    ("🐶 Товары для питомцев", 600),
    ("📚 Книги", 350),
    ("🖊️ Канцтовары", 300),
    ("💡 Освещение", 750),
    ("🔌 Электрика", 680),
    ("🛋️ Мебель и декор", 2500),
    ("🧹 Уборка", 620),
    ("🌱 Сад и огород", 1400),
    ("🧰 Инструменты", 1600),
    ("📷 Камеры", 980),
    ("🔊 Аудиотехника", 1250),
    ("⌨️ Периферия", 400),
    ("💍 Украшения", 120),
    ("🕶️ Аксессуары", 200),
    ("🧳 Сумки и чемоданы", 1000),
    ("🛁 Ванная", 550),
]


def main_menu_kb() -> ReplyKeyboardMarkup:
    """Главное меню пользователя."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧮 Рассчитать стоимость"), KeyboardButton(text="📦 Каталог товаров")],
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="ℹ️ Как работает")],
        ],
        resize_keyboard=True,
    )


def catalog_kb() -> InlineKeyboardMarkup:
    """Inline-кнопки категорий товаров (30+)."""
    builder = InlineKeyboardBuilder()
    for title, weight in CATEGORIES:
        builder.add(InlineKeyboardButton(text=title, callback_data=f"cat:{weight}:{title}"))
    builder.adjust(2)
    return builder.as_markup()


def choose_weight_kb() -> InlineKeyboardMarkup:
    """Подсказка выбора веса через каталог."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📦 Выбрать средний вес из каталога", callback_data="open_catalog")]
        ]
    )
