# HorecaKadrBot — бот массового подбора персонала для сети кафе

Telegram-бот: кандидаты заполняют анкету по вакансиям (официант, бармен, повар,
техперсонал), HR управляет воронкой найма прямо в боте — статусы, собеседования
с напоминаниями, аналитика и выгрузка в Excel.

## Стек

- Python 3.11+ · aiogram 3.x · SQLAlchemy 2.0 (async) + aiosqlite
- APScheduler (напоминания о собеседованиях за 3 часа)
- openpyxl (выгрузка .xlsx)

## Возможности

**Кандидат** (`/start`, deep-link `t.me/<bot>?start=<source>` для меток трафика):
выбор вакансии → анкета из 7 шагов с валидацией и кнопкой «Назад» →
авто-скрининг (возраст ≥ 18 и готовность к графику) → уведомление всем админам.
Повторная анкета — только после завершения предыдущей заявки.

**HR/Админ** (`/admin`, доступ по `ADMIN_IDS`):
- 📋 Кандидаты: фильтры по вакансии/статусу, пагинация, карточка кандидата
- Смена статуса воронки, сообщение кандидату через бота, назначение собеседования
- 📊 Аналитика: заявки за сегодня/7/30 дней/всё время, разбивка по вакансиям,
  конверсия по этапам воронки, источники трафика
- 📥 Выгрузка всех кандидатов в Excel

## Установка (локально)

```bash
git clone <repo-url> && cd HorecaKadrBot
python3 --version            # требуется 3.11+
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить BOT_TOKEN и ADMIN_IDS
python main.py
```

`.env`:

| Переменная     | Описание                                                  |
|----------------|-----------------------------------------------------------|
| `BOT_TOKEN`    | Токен от @BotFather                                        |
| `ADMIN_IDS`    | Telegram user_id админов через запятую                     |
| `DATABASE_URL` | По умолчанию SQLite; для Postgres — `postgresql+asyncpg://…` (нужен пакет `asyncpg`) |
| `TIMEZONE`     | Часовой пояс, по умолчанию `Asia/Tashkent`                 |

База создаётся автоматически при первом запуске.

## Деплой на VPS (systemd)

```bash
# 1. Код и окружение
sudo useradd -r -m -d /opt/horecakadr-bot botuser
sudo git clone <repo-url> /opt/horecakadr-bot
cd /opt/horecakadr-bot
sudo python3 -m venv .venv   # python3 ≥ 3.11 (на Ubuntu: apt install python3.11-venv)
sudo .venv/bin/pip install -r requirements.txt
sudo cp .env.example .env && sudo nano .env      # заполнить
sudo chown -R botuser:botuser /opt/horecakadr-bot

# 2. Сервис
sudo cp deploy/horecakadr-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now horecakadr-bot

# 3. Проверка
systemctl status horecakadr-bot
journalctl -u horecakadr-bot -f
```

Готовый unit-файл: [`deploy/horecakadr-bot.service`](deploy/horecakadr-bot.service).

## Миграция на Postgres

1. `pip install asyncpg`
2. В `.env`: `DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/horecakadr`
3. Перезапустить бота — таблицы создадутся автоматически.

## Структура проекта

```
main.py              # точка входа, сборка диспетчера, graceful shutdown
config.py            # конфиг из .env
texts.py             # все тексты (RU) — для перевода менять только здесь
handlers/            # candidate.py (анкета), admin.py (админ-панель)
keyboards/           # inline/reply клавиатуры
db/                  # models.py, repository.py, base.py
services/            # notifications, scheduler, analytics, excel
middlewares/         # antiflood (0.5 c), logging, db-session
utils/               # валидаторы, форматирование карточек
deploy/              # systemd unit
```
