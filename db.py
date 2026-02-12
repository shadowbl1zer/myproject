"""Слой работы с SQLite (aiosqlite)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiosqlite


DB_PATH = "shop_bot.db"


@dataclass(slots=True)
class Rates:
    """Курсы валют для расчёта."""

    usd_to_byn: float
    cny_to_byn: float


async def init_db() -> None:
    """Создать таблицы и базовые настройки, если их ещё нет."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                photo_file_id TEXT NOT NULL,
                weight_g REAL NOT NULL,
                price_cny REAL NOT NULL,
                usd_rate REAL NOT NULL,
                cny_rate REAL NOT NULL,
                total_byn INTEGER NOT NULL,
                status TEXT DEFAULT 'Новый',
                track_code TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

        await db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('usd_to_byn', '3.2')"
        )
        await db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('cny_to_byn', '0.45')"
        )
        await db.commit()


async def get_rates() -> Rates:
    """Получить текущие курсы валют из настроек."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT key, value FROM settings WHERE key IN ('usd_to_byn', 'cny_to_byn')"
        )
        rows = await cursor.fetchall()

    values = {key: float(value) for key, value in rows}
    return Rates(
        usd_to_byn=values.get("usd_to_byn", 3.2),
        cny_to_byn=values.get("cny_to_byn", 0.45),
    )


async def set_rates(usd_to_byn: float, cny_to_byn: float) -> None:
    """Обновить курсы валют."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('usd_to_byn', ?)",
            (str(usd_to_byn),),
        )
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('cny_to_byn', ?)",
            (str(cny_to_byn),),
        )
        await db.commit()


async def create_order(data: dict[str, Any]) -> int:
    """Создать заказ и вернуть его ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO orders (
                user_id, username, photo_file_id, weight_g, price_cny,
                usd_rate, cny_rate, total_byn, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["user_id"],
                data.get("username"),
                data["photo_file_id"],
                data["weight_g"],
                data["price_cny"],
                data["usd_rate"],
                data["cny_rate"],
                data["total_byn"],
                data.get("status", "Новый"),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        await db.commit()
        return cursor.lastrowid


async def list_orders(limit: int = 20) -> list[tuple]:
    """Вернуть последние заказы."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT id, user_id, username, weight_g, price_cny, total_byn, status, track_code, created_at
            FROM orders
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return await cursor.fetchall()


async def update_track(order_id: int, track_code: str) -> bool:
    """Обновить трек-код заказа."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE orders SET track_code = ? WHERE id = ?",
            (track_code, order_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def update_status(order_id: int, status: str) -> bool:
    """Обновить статус заказа."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (status, order_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def user_orders_count(user_id: int) -> int:
    """Количество заказов пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0
