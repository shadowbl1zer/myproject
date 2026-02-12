# Telegram-бот для онлайн-магазина (aiogram 3.x)

## Возможности
- Русскоязычный интерфейс с эмодзи и удобным меню.
- FSM-сценарий оформления заказа: фото → вес → цена.
- Расчёт итоговой стоимости в BYN по заданной формуле.
- Хранение заказов и курсов валют в SQLite.
- Админ-команды для управления курсами и заказами.
- Каталог из 30+ категорий товаров с inline-кнопками и средним весом.

## Установка
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Заполните `.env`:
```env
BOT_TOKEN=<токен_бота>
ADMIN_ID=<ваш_telegram_id>
```

## Запуск
```bash
python main.py
```

## Админ-команды
- `/rates` — показать курсы.
- `/setrates USD_BYN CNY_BYN` — изменить курсы.
- `/orders` — список последних заказов.
- `/settrack ORDER_ID TRACKCODE` — задать трек.
- `/setstatus ORDER_ID ТЕКСТ` — изменить статус.
