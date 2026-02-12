"""Telegram-бот для расчёта заказов с китайских маркетплейсов (aiogram 3.x)."""

from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from dotenv import load_dotenv

from db import (
    create_order,
    get_rates,
    init_db,
    list_orders,
    set_rates,
    update_status,
    update_track,
    user_orders_count,
)
from keyboards import catalog_kb, choose_weight_kb, main_menu_kb
from states import OrderStates


router = Router()


def calculate_total(weight_g: float, price_cny: float, usd_to_byn: float, cny_to_byn: float) -> int:
    """Рассчитать итоговую стоимость в BYN по заданной формуле."""
    delivery_usd = (weight_g / 1000) * 19
    delivery_byn = delivery_usd * usd_to_byn
    goods_byn = price_cny * cny_to_byn
    subtotal = delivery_byn + goods_byn + 10
    total = subtotal * 1.2  # 20% маржа
    return int(round(total))


def is_admin(user_id: int, admin_id: int) -> bool:
    """Проверка, является ли пользователь администратором."""
    return user_id == admin_id


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Старт бота и показ главного меню."""
    await state.clear()
    await message.answer(
        "👋 <b>Добро пожаловать!</b>\n\n"
        "Я помогу рассчитать стоимость заказа товаров с китайских маркетплейсов.\n"
        "Выберите действие в меню ниже 👇",
        reply_markup=main_menu_kb(),
    )


@router.message(F.text == "ℹ️ Как работает")
async def how_it_works(message: Message) -> None:
    """Инструкция по работе с ботом."""
    await message.answer(
        "ℹ️ <b>Как работает расчёт:</b>\n\n"
        "1) Вы отправляете фото товара 📸\n"
        "2) Указываете вес в граммах ⚖️\n"
        "3) Указываете цену в юанях 💴\n"
        "4) Бот считает итог в BYN с доставкой, комиссией и маржой ✅\n\n"
        "После расчёта заказ автоматически сохраняется и отправляется админу.",
    )


@router.message(F.text == "👤 Профиль")
async def profile(message: Message) -> None:
    """Показ профиля пользователя."""
    count = await user_orders_count(message.from_user.id)
    username = message.from_user.username or "без username"
    await message.answer(
        f"👤 <b>Ваш профиль</b>\n\n"
        f"ID: <code>{message.from_user.id}</code>\n"
        f"Username: @{username}\n"
        f"📦 Всего заказов: <b>{count}</b>",
    )


@router.message(F.text == "📦 Каталог товаров")
async def show_catalog(message: Message) -> None:
    """Показ каталога категорий."""
    await message.answer(
        "📦 <b>Каталог товаров</b>\n"
        "Выберите категорию, чтобы посмотреть средний вес для расчёта:",
        reply_markup=catalog_kb(),
    )


@router.callback_query(F.data == "open_catalog")
async def callback_open_catalog(callback: CallbackQuery) -> None:
    """Открыть каталог из шага выбора веса."""
    await callback.message.answer("📦 Выберите категорию:", reply_markup=catalog_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("cat:"))
async def callback_category(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор категории и подстановка среднего веса."""
    try:
        _, weight_str, title = callback.data.split(":", maxsplit=2)
        weight = float(weight_str)
    except (ValueError, AttributeError):
        await callback.answer("Ошибка данных категории", show_alert=True)
        return

    current_state = await state.get_state()
    text = (
        f"📦 <b>{title}</b>\n"
        f"Средний вес: <b>{int(weight)} г</b>\n\n"
        "Чтобы использовать этот вес в текущем расчёте, нажмите кнопку ниже."
    )
    await callback.message.answer(
        text,
        reply_markup=None,
    )

    if current_state == OrderStates.waiting_weight.state:
        await state.update_data(weight_g=weight)
        await state.set_state(OrderStates.waiting_price)
        await callback.message.answer(
            f"✅ Вес <b>{int(weight)} г</b> сохранён.\nТеперь введите цену товара в юанях (например, <code>299.5</code>):"
        )
    else:
        await callback.message.answer(
            "ℹ️ Для автоматической подстановки веса начните расчёт через кнопку "
            "<b>🧮 Рассчитать стоимость</b>."
        )

    await callback.answer()


@router.message(F.text == "🧮 Рассчитать стоимость")
async def start_calculation(message: Message, state: FSMContext) -> None:
    """Запуск FSM-сценария оформления заказа."""
    await state.clear()
    await state.set_state(OrderStates.waiting_photo)
    await message.answer("📸 Отправьте фото товара для расчёта стоимости.")


@router.message(OrderStates.waiting_photo)
async def get_photo(message: Message, state: FSMContext) -> None:
    """Получить фото товара."""
    if not message.photo:
        await message.answer("❗ Пожалуйста, отправьте именно фото товара.")
        return

    file_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=file_id)
    await state.set_state(OrderStates.waiting_weight)
    await message.answer(
        "⚖️ Введите вес товара в граммах (только число, например <code>850</code>).",
        reply_markup=choose_weight_kb(),
    )


@router.message(OrderStates.waiting_weight)
async def get_weight(message: Message, state: FSMContext) -> None:
    """Получить и валидировать вес."""
    if not message.text:
        await message.answer("❗ Введите вес текстом (число в граммах).")
        return

    value = message.text.replace(",", ".").strip()
    try:
        weight_g = float(value)
        if weight_g <= 0 or weight_g > 100_000:
            raise ValueError
    except ValueError:
        await message.answer("❗ Некорректный вес. Введите число от 1 до 100000 грамм.")
        return

    await state.update_data(weight_g=weight_g)
    await state.set_state(OrderStates.waiting_price)
    await message.answer("💴 Введите цену товара в юанях (например, <code>199.99</code>).")


@router.message(OrderStates.waiting_price)
async def get_price(message: Message, state: FSMContext, bot: Bot) -> None:
    """Получить цену, рассчитать итог и создать заказ."""
    if not message.text:
        await message.answer("❗ Введите цену текстом (число в юанях).")
        return

    value = message.text.replace(",", ".").strip()
    try:
        price_cny = float(value)
        if price_cny <= 0 or price_cny > 1_000_000:
            raise ValueError
    except ValueError:
        await message.answer("❗ Некорректная цена. Введите число от 0.01 до 1000000.")
        return

    data = await state.get_data()
    rates = await get_rates()
    total_byn = calculate_total(
        weight_g=float(data["weight_g"]),
        price_cny=price_cny,
        usd_to_byn=rates.usd_to_byn,
        cny_to_byn=rates.cny_to_byn,
    )

    order_id = await create_order(
        {
            "user_id": message.from_user.id,
            "username": message.from_user.username,
            "photo_file_id": data["photo_file_id"],
            "weight_g": float(data["weight_g"]),
            "price_cny": price_cny,
            "usd_rate": rates.usd_to_byn,
            "cny_rate": rates.cny_to_byn,
            "total_byn": total_byn,
            "status": "Новый",
        }
    )

    admin_id = int(os.getenv("ADMIN_ID", "0"))
    admin_caption = (
        f"🆕 <b>Новый заказ #{order_id}</b>\n"
        f"👤 Пользователь: <code>{message.from_user.id}</code> (@{message.from_user.username or 'no_username'})\n"
        f"⚖️ Вес: <b>{float(data['weight_g']):.2f} г</b>\n"
        f"💴 Цена: <b>{price_cny:.2f} CNY</b>\n"
        f"💵 USD→BYN: <b>{rates.usd_to_byn}</b>\n"
        f"💹 CNY→BYN: <b>{rates.cny_to_byn}</b>\n"
        f"💰 Итого: <b>{total_byn} BYN</b>"
    )

    if admin_id > 0:
        try:
            await bot.send_photo(chat_id=admin_id, photo=data["photo_file_id"], caption=admin_caption)
        except TelegramBadRequest:
            logging.exception("Не удалось отправить заказ админу")

    await message.answer(
        f"✅ <b>Расчёт готов!</b>\n\n"
        f"Номер заказа: <b>#{order_id}</b>\n"
        f"Итоговая стоимость: <b>{total_byn} BYN</b>\n\n"
        "Менеджер свяжется с вами после проверки заказа.",
        reply_markup=main_menu_kb(),
    )
    await state.clear()


@router.message(Command("rates"))
async def admin_rates(message: Message) -> None:
    """Показать курсы (админ)."""
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if not is_admin(message.from_user.id, admin_id):
        return

    rates = await get_rates()
    await message.answer(
        "💱 <b>Текущие курсы:</b>\n"
        f"USD → BYN: <b>{rates.usd_to_byn}</b>\n"
        f"CNY → BYN: <b>{rates.cny_to_byn}</b>"
    )


@router.message(Command("setrates"))
async def admin_set_rates(message: Message) -> None:
    """Изменить курсы (админ). Формат: /setrates 3.2 0.45"""
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if not is_admin(message.from_user.id, admin_id):
        return

    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Формат: <code>/setrates USD_BYN CNY_BYN</code>\nПример: <code>/setrates 3.25 0.46</code>")
        return

    try:
        usd_rate = float(parts[1].replace(",", "."))
        cny_rate = float(parts[2].replace(",", "."))
        if usd_rate <= 0 or cny_rate <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❗ Курсы должны быть положительными числами.")
        return

    await set_rates(usd_rate, cny_rate)
    await message.answer(f"✅ Курсы обновлены: USD→BYN={usd_rate}, CNY→BYN={cny_rate}")


@router.message(Command("orders"))
async def admin_orders(message: Message) -> None:
    """Список последних заказов (админ)."""
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if not is_admin(message.from_user.id, admin_id):
        return

    orders = await list_orders(limit=20)
    if not orders:
        await message.answer("📭 Заказов пока нет.")
        return

    lines = ["📋 <b>Последние заказы:</b>"]
    for item in orders:
        oid, user_id, username, weight_g, price_cny, total_byn, status, track, created = item
        lines.append(
            f"\n<b>#{oid}</b> | 👤 {user_id} (@{username or 'no_username'})"
            f"\n⚖️ {weight_g:.0f}г | 💴 {price_cny:.2f} | 💰 {total_byn} BYN"
            f"\n📌 Статус: {status}"
            f"\n🚚 Трек: {track or 'не задан'}"
            f"\n🕒 {created}"
        )

    await message.answer("\n".join(lines))


@router.message(Command("settrack"))
async def admin_set_track(message: Message) -> None:
    """Обновить трек заказа. Формат: /settrack ORDER_ID TRACKCODE"""
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if not is_admin(message.from_user.id, admin_id):
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Формат: <code>/settrack ORDER_ID TRACKCODE</code>")
        return

    try:
        order_id = int(parts[1])
    except ValueError:
        await message.answer("❗ ORDER_ID должен быть числом.")
        return

    ok = await update_track(order_id, parts[2].strip())
    if ok:
        await message.answer(f"✅ Трек-код для заказа #{order_id} обновлён.")
    else:
        await message.answer("❗ Заказ не найден.")


@router.message(Command("setstatus"))
async def admin_set_status(message: Message) -> None:
    """Обновить статус заказа. Формат: /setstatus ORDER_ID текст"""
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if not is_admin(message.from_user.id, admin_id):
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Формат: <code>/setstatus ORDER_ID ТЕКСТ_СТАТУСА</code>")
        return

    try:
        order_id = int(parts[1])
    except ValueError:
        await message.answer("❗ ORDER_ID должен быть числом.")
        return

    status_text = parts[2].strip()
    ok = await update_status(order_id, status_text)
    if ok:
        await message.answer(f"✅ Статус заказа #{order_id} обновлён: {status_text}")
    else:
        await message.answer("❗ Заказ не найден.")


@router.message()
async def fallback(message: Message) -> None:
    """Общий fallback-обработчик."""
    await message.answer(
        "🤖 Не понял команду. Используйте кнопки меню или /start.",
        reply_markup=main_menu_kb(),
    )


async def main() -> None:
    """Точка входа: инициализация и запуск polling."""
    load_dotenv()

    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN не найден в .env")

    await init_db()

    bot = Bot(token=token, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    dp.include_router(router)

    # Удаляем webhook перед запуском polling согласно требованиям.
    await bot.delete_webhook(drop_pending_updates=True)

    logging.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
    except Exception:
        logging.exception("Критическая ошибка при запуске бота")
