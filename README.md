# HR-бот «Ченсон» — массовый подбор персонала

Telegram-бот для сети корейских кафе «Ченсон» (Ташкент, 4 филиала: Куйлюк,
Чиланзар, Сайрам, Сеул Мун). Кандидаты проходят анкету с автоскринингом,
менеджеры филиалов и шеф-повар ведут своих кандидатов, рекрутер управляет
вакансиями и отчётами.

## Стек

Python 3.11+ · aiogram 3.x · SQLAlchemy 2.0 async + aiosqlite (Postgres через
`DATABASE_URL`) · APScheduler · openpyxl

## Роли (whitelist в БД, таблица Users)

| Роль | Возможности |
|------|-------------|
| Кандидат (любой) | анкета, список вакансий, условия работы |
| `branch_manager` | заявки на персонал, вакансии и кандидаты своего филиала, смена их статусов |
| `chef` | то же, но видит поваров всех филиалов |
| `recruiter` | вакансии, кандидаты, статусы, шаблоны, отчёты |
| `admin` | всё + управление whitelist, привязка чатов, настройки |

Админы из `ADMIN_IDS` (.env) попадают в whitelist автоматически при старте.
Действия сотрудников пишутся в AuditLog.

## Ключевые механики

- **Анкета** (FSM, кнопка «Назад»): ФИО, возраст, пол, телефон, район, опыт
  (повара — стаж в годах + специализация), русский, свинина/алкоголь,
  военный билет (мужчины). Выбор вакансии — только из открытых.
- **Автоскрининг** — все пороги в таблице Settings (меняются командой
  `/set_setting` без правки кода): возрастные вилки по позициям (у поваров
  отдельный потолок для женщин), мин. стаж поваров, язык, военный билет,
  свинина/алкоголь. Причина отказа сохраняется для аналитики.
- **Повара**: собеседование всегда на Куйлюке у шеф-повара, карточки уходят
  в чат «Кухня» и шефу.
- **Карточки**: при подтверждении собеседования карточка идёт в чат филиала
  (привязка: `/bind_chat <филиал>` в нужном чате) и рекрутерам.
- **Заявки на персонал**: менеджер подаёт заявку → рекрутер «Создать
  вакансию» (с префиллом) / «Уточнить» / «Отклонить».
- **Отчёты** `/report`: период, фильтры, конверсия воронки, причины отказов,
  источники (deep-link `t.me/<bot>?start=hh`), выгрузка Excel со всеми
  анкетами. Экспорт в `services/export.py` — фаза 2 добавит Google Sheets
  без переделки кода.
- **День сверки**: каждый понедельник 10:00 (Asia/Tashkent) рекрутеру
  приходит чеклист: открытые вакансии, кто вышел, кто не прошёл стажировку,
  причины отказов.

## Установка

```bash
git clone <repo-url> && cd HorecaKadrBot
python3 --version            # требуется 3.11+
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env         # заполнить BOT_TOKEN и ADMIN_IDS
python main.py
```

База и справочники (филиалы, настройки) создаются автоматически.

### Первые шаги после запуска

1. `/start` от имени админа → меню с командами.
2. `/add_user <tg_id> recruiter` — добавить рекрутера;
   `/add_user <tg_id> branch_manager Чиланзар` — менеджера;
   `/add_user <tg_id> chef` — шеф-повара.
3. Добавить бота в чаты филиалов и кухни, в каждом выполнить
   `/bind_chat <филиал>` или `/bind_chat kitchen`.
4. `/add_vacancy` — создать первые вакансии.
5. При необходимости поправить пороги: `/settings`, `/set_setting cook_min_exp_years 2`.

## Деплой на VPS (systemd)

```bash
sudo useradd -r -m -d /opt/horecakadr-bot botuser
sudo git clone <repo-url> /opt/horecakadr-bot
cd /opt/horecakadr-bot
sudo python3 -m venv .venv   # python3 ≥ 3.11 (Ubuntu: apt install python3.11-venv)
sudo .venv/bin/pip install -r requirements.txt
sudo cp .env.example .env && sudo nano .env
sudo chown -R botuser:botuser /opt/horecakadr-bot

sudo cp deploy/horecakadr-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now horecakadr-bot
journalctl -u horecakadr-bot -f
```

Либо через pm2: `pm2 start main.py --name chenson-bot --interpreter ./.venv/bin/python && pm2 save`.

## Миграция на Postgres

`pip install asyncpg`, в `.env`:
`DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/chenson` — таблицы
создадутся при старте.

## Структура

```
main.py                  # сборка, polling, graceful shutdown
config.py                # .env + DEFAULT_SETTINGS (пороги скрининга)
texts.py                 # все тексты (RU)
db/                      # models, repository, seed (филиалы/настройки/админы)
handlers/
  common.py              # /start: роль → меню
  candidate.py           # анкета, скрининг, подтверждение собеседования
  manager.py             # менеджер/шеф: заявки, свои кандидаты, статусы
  recruiter_vacancies.py # вакансии, шаблоны, обработка заявок
  recruiter_candidates.py# /candidates, /candidate, /set_status
  reports.py             # /report + Excel
  admin_users.py         # whitelist, /bind_chat, /set_setting
services/                # screening, cards, notify, export, scheduler
middlewares/             # antiflood 0.5с, logging (без PII), db-session
utils/                   # validators, roles (RoleFilter), timeutil
deploy/                  # systemd unit
```
