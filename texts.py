"""Все тексты бота «Ченсон» (русский). Для узбекской версии — заменить значения."""
from db.models import (
    CandidateStatus,
    CookSpec,
    Gender,
    Position,
    RejectionReason,
    Role,
    RussianLevel,
    StaffRequestStatus,
    VacancyStatus,
)

# ── Лейблы справочников ──────────────────────────────────────────────
POSITION_LABELS: dict[Position, str] = {
    Position.WAITER: "🍽 Официант",
    Position.BARTENDER: "🍸 Бармен",
    Position.COOK: "👨‍🍳 Повар",
    Position.TECH: "🧹 Техперсонал",
}

COOK_SPEC_LABELS: dict[CookSpec, str] = {
    CookSpec.HOT: "Горячий цех",
    CookSpec.COLD: "Холодный цех",
    CookSpec.SUSHI: "Суши",
    CookSpec.UNIVERSAL: "Универсал",
    CookSpec.OTHER: "Другое",
}

GENDER_LABELS: dict[Gender, str] = {
    Gender.MALE: "Мужской",
    Gender.FEMALE: "Женский",
}

RUSSIAN_LABELS: dict[RussianLevel, str] = {
    RussianLevel.FLUENT: "Свободно",
    RussianLevel.MIDDLE: "Средне",
    RussianLevel.NONE: "Не говорю",
}

STATUS_LABELS: dict[CandidateStatus, str] = {
    CandidateStatus.NEW: "🆕 Новый",
    CandidateStatus.SCREEN_REJECTED: "⛔️ Отказ по критериям",
    CandidateStatus.INVITED: "📅 Приглашён",
    CandidateStatus.CAME: "🤝 Пришёл на собеседование",
    CandidateStatus.NO_SHOW: "👻 Не пришёл",
    CandidateStatus.INTERNSHIP: "📚 Вышел на стажировку",
    CandidateStatus.INTERNSHIP_FAILED: "📕 Не прошёл стажировку",
    CandidateStatus.HIRED: "🎉 Принят",
    CandidateStatus.EMPLOYER_REJECTED: "❌ Отказ работодателя",
    CandidateStatus.NOT_INTERESTED: "🚪 Не заинтересован",
}

REJECTION_LABELS: dict[RejectionReason, str] = {
    RejectionReason.AGE: "Возраст",
    RejectionReason.EXPERIENCE: "Опыт",
    RejectionReason.LANGUAGE: "Язык",
    RejectionReason.MILITARY: "Военный билет",
    RejectionReason.PORK_ALCOHOL: "Свинина/алкоголь",
}

VACANCY_STATUS_LABELS: dict[VacancyStatus, str] = {
    VacancyStatus.OPEN: "🟢 Открыта",
    VacancyStatus.CLOSED: "🔴 Закрыта",
}

STAFF_REQUEST_STATUS_LABELS: dict[StaffRequestStatus, str] = {
    StaffRequestStatus.NEW: "Новая",
    StaffRequestStatus.IN_PROGRESS: "В работе",
    StaffRequestStatus.CONVERTED: "Превращена в вакансию",
    StaffRequestStatus.REJECTED: "Отклонена",
}

ROLE_LABELS: dict[Role, str] = {
    Role.RECRUITER: "Рекрутер",
    Role.BRANCH_MANAGER: "Менеджер филиала",
    Role.CHEF: "Шеф-повар",
    Role.ADMIN: "Администратор",
}

EXPERIENCE_OPTIONS: list[str] = ["Нет", "До 1 года", "1–3 года", "3+ года"]

DISTRICTS: list[str] = [
    "Алмазарский", "Бектемирский", "Мирабадский", "Мирзо-Улугбекский",
    "Сергелийский", "Учтепинский", "Чиланзарский", "Шайхантахурский",
    "Юнусабадский", "Яккасарайский", "Яшнабадский", "Янгихаётский",
]

# ── Кандидат: старт и меню ───────────────────────────────────────────
WELCOME_CANDIDATE = (
    "🇰🇷 Добро пожаловать в <b>«Ченсон»</b> — сеть корейских кафе в Ташкенте!\n\n"
    "Мы набираем команду в 4 филиала. Выберите действие:"
)
BTN_APPLY = "📝 Откликнуться"
BTN_VACANCY_LIST = "📋 Список вакансий"
BTN_CONDITIONS = "ℹ️ Условия работы"

CONDITIONS_TEXT = (
    "<b>Условия работы в «Ченсон»:</b>\n\n"
    "• Официальное трудоустройство\n"
    "• Питание за счёт компании\n"
    "• Дружная команда и обучение\n"
    "• 4 филиала: Куйлюк, Чиланзар, Сайрам, Сеул Мун\n\n"
    "Зарплата и график зависят от вакансии — смотрите «Список вакансий»."
)

NO_OPEN_VACANCIES = (
    "Сейчас открытых вакансий нет. Загляните позже — мы регулярно набираем людей!"
)
CHOOSE_VACANCY = "Выберите вакансию (позиция · филиал):"
ALREADY_APPLIED = (
    "У вас уже есть заявка в работе — мы свяжемся с вами.\n"
    "Новый отклик можно оставить после завершения текущего."
)

# ── Анкета ───────────────────────────────────────────────────────────
ASK_FULL_NAME = "Напишите ваши фамилию и имя:"
ASK_AGE = "Сколько вам лет? Напишите число:"
ASK_GENDER = "Укажите пол:"
ASK_PHONE = (
    "Поделитесь номером телефона — кнопка ниже, или введите вручную "
    "(например, +998901234567):"
)
ASK_DISTRICT = "В каком районе Ташкента вы живёте?"
ASK_EXPERIENCE = "Есть ли у вас опыт работы в общепите?"
ASK_COOK_YEARS = "Сколько лет вы работаете поваром? Напишите число (0 — если нет опыта):"
ASK_COOK_SPEC = "Ваша специализация:"
ASK_RUSSIAN = "Как вы говорите по-русски?"
ASK_PORK_ALCOHOL = (
    "В наших кафе корейская кухня: блюда содержат <b>свинину</b>, "
    "в зале подаётся <b>алкоголь</b>.\n\n"
    "Готовы ли вы работать с такими продуктами?"
)
ASK_MILITARY = "Есть ли у вас приписное свидетельство или военный билет?"

INVALID_NAME = "Пожалуйста, введите имя и фамилию текстом (от 2 до 150 символов)."
INVALID_AGE = "Пожалуйста, введите возраст числом (14–80)."
INVALID_PHONE = (
    "Не получилось распознать номер. Формат: +998901234567, "
    "или нажмите «Поделиться контактом»."
)
INVALID_COOK_YEARS = "Введите стаж числом от 0 до 50."
USE_BUTTONS = "Пожалуйста, выберите вариант кнопкой ниже."

BTN_BACK = "⬅️ Назад"
BTN_SHARE_CONTACT = "📱 Поделиться контактом"
BTN_YES = "Да"
BTN_NO = "Нет"

FORM_CANCELLED = "Анкета отменена. Чтобы начать заново — /start."
FORM_EXPIRED = "Анкета устарела. Пожалуйста, начните заново: /start"

# ── Результат скрининга ──────────────────────────────────────────────
SCREEN_REJECTED = (
    "Спасибо за интерес к «Ченсон»! 🙏\n\n"
    "К сожалению, по требованиям компании мы сейчас не можем предложить вам "
    "эту вакансию. Следите за нашими объявлениями — требования и вакансии "
    "обновляются!"
)
SCREEN_PASSED_TEMPLATE = (
    "🎉 Отлично, вы нам подходите!\n\n"
    "<b>{position} · филиал {branch}</b>\n"
    "💰 Зарплата: {salary}\n"
    "🗓 График: {schedule}\n"
    "{description}\n"
    "📍 <b>Собеседование:</b> {interview_address}\n\n"
    "Подтверждаете, что придёте на собеседование?"
)
COOK_INTERVIEW_NOTE = "филиал Куйлюк (собеседования поваров проводит шеф-повар)"
BTN_CONFIRM_COME = "✅ Да, приду"
BTN_DECLINE_COME = "❌ Нет"

INVITED_OK = (
    "Ждём вас! 🤝 Менеджер филиала может связаться с вами для уточнения времени.\n"
    "Телефон филиала и детали — в сообщении выше."
)
DECLINE_OFFER_OTHER = "Хотите посмотреть другие открытые вакансии?"
BTN_OTHER_VACANCIES = "📋 Другие вакансии"
BTN_NOT_INTERESTED = "🚪 Не интересно"
NOT_INTERESTED_BYE = "Хорошо! Если передумаете — мы всегда рады, просто напишите /start."

# ── Карточка кандидата ───────────────────────────────────────────────
CARD_NEW_CANDIDATE = "🔔 <b>Новый кандидат!</b>\n\n"

# ── Меню сотрудников ─────────────────────────────────────────────────
MANAGER_MENU = "👔 <b>Меню менеджера филиала «{branch}»</b>"
CHEF_MENU = "👨‍🍳 <b>Меню шеф-повара</b> (повара всех филиалов)"
RECRUITER_MENU = (
    "🧑‍💼 <b>Меню рекрутера</b>\n\n"
    "Команды:\n"
    "/vacancies — вакансии\n"
    "/add_vacancy — создать вакансию\n"
    "/close_vacancy — закрыть вакансию\n"
    "/set_quota — изменить квоту\n"
    "/templates — шаблоны для публикации\n"
    "/candidates — кандидаты (фильтры)\n"
    "/candidate <code>id</code> — анкета кандидата\n"
    "/set_status — сменить статус кандидата\n"
    "/report — отчёт за период\n"
)
ADMIN_EXTRA_MENU = (
    "\n<b>Админ:</b>\n"
    "/add_user — добавить сотрудника\n"
    "/users — список сотрудников\n"
    "/bind_chat — привязать этот чат к филиалу/кухне\n"
    "/set_setting — изменить настройку (пороги и пр.)\n"
    "/settings — текущие настройки\n"
)
BTN_STAFF_REQUEST = "➕ Подать заявку на персонал"
BTN_MY_VACANCIES = "📋 Открытые вакансии моего филиала"
BTN_MY_CANDIDATES = "👥 Мои кандидаты"
NOT_AUTHORIZED = "Эта функция доступна только сотрудникам."

# ── Заявка на персонал ───────────────────────────────────────────────
SR_ASK_POSITION = "Кого ищем? Выберите позицию:"
SR_ASK_COUNT = "Сколько человек нужно? Напишите число:"
SR_ASK_COMMENT = "Комментарий по условиям (график, требования) — или «-», если без комментариев:"
SR_INVALID_COUNT = "Введите число от 1 до 50."
SR_CREATED = "✅ Заявка №{id} отправлена рекрутеру."
SR_NEW_FOR_RECRUITER = (
    "📨 <b>Заявка на персонал №{id}</b>\n\n"
    "Филиал: {branch}\nПозиция: {position}\nКоличество: {count}\n"
    "Комментарий: {comment}\nОт: {manager}"
)
SR_BTN_CREATE_VACANCY = "✅ Создать вакансию"
SR_BTN_CLARIFY = "❓ Уточнить"
SR_BTN_REJECT = "❌ Отклонить"
SR_REJECTED_FOR_MANAGER = "Ваша заявка №{id} отклонена рекрутером."
SR_CLARIFY_ASK = "Напишите вопрос менеджеру (или /cancel):"
SR_CLARIFY_SENT = "Вопрос отправлен менеджеру."
SR_CLARIFY_FOR_MANAGER = "❓ <b>Вопрос рекрутера по заявке №{id}:</b>\n\n{text}"
SR_ALREADY_PROCESSED = "Эта заявка уже обработана."

# ── Вакансии ─────────────────────────────────────────────────────────
VAC_LIST_TITLE = "📋 <b>Вакансии</b>"
VAC_LINE = "#{id} {position} · {branch} · {status} · закрыто {hired}/{quota}"
VAC_EMPTY = "Вакансий пока нет. Создать: /add_vacancy"
VAC_ASK_BRANCH = "Филиал вакансии:"
VAC_ASK_POSITION = "Позиция:"
VAC_ASK_SALARY = "Зарплата (текстом, например «4–6 млн сум»):"
VAC_ASK_SCHEDULE = "График (например «6/1, 10:00–22:00»):"
VAC_ASK_DESCRIPTION = "Описание вакансии (требования, обязанности) — или «-»:"
VAC_ASK_QUOTA = "Квота — сколько человек нужно нанять? Число:"
VAC_INVALID_QUOTA = "Введите число от 1 до 100."
VAC_CREATED = "✅ Вакансия #{id} создана и открыта: {position} · {branch}"
VAC_CHOOSE_TO_CLOSE = "Какую вакансию закрыть?"
VAC_CLOSED = "🔴 Вакансия #{id} закрыта."
VAC_CHOOSE_FOR_QUOTA = "Для какой вакансии изменить квоту?"
VAC_ASK_NEW_QUOTA = "Новая квота для вакансии #{id} (число):"
VAC_QUOTA_SET = "✅ Квота вакансии #{id}: {quota}"
MY_BRANCH_VACANCIES_TITLE = "📋 <b>Открытые вакансии филиала «{branch}»</b>"
MY_BRANCH_NO_VACANCIES = "В вашем филиале нет открытых вакансий."

TEMPLATES_TITLE = "📝 <b>Шаблоны вакансий для публикации</b>\n(копируйте текст ниже)"
TEMPLATE_VACANCY = (
    "🇰🇷 «Ченсон» ищет: <b>{position}</b>\n"
    "📍 Филиал: {branch}, {address}\n"
    "💰 {salary}\n🗓 {schedule}\n{description}\n"
    "👉 Откликнуться: напишите нашему боту @{bot_username}"
)
TEMPLATES_DRIVE = "\n📁 Медиа для публикаций: {link}"
TEMPLATES_NO_DRIVE = "\n(ссылка на Google Drive не настроена — /set_setting drive_link &lt;url&gt;)"

# ── Кандидаты (управление) ───────────────────────────────────────────
CAND_LIST_TITLE = "👥 <b>Кандидаты</b> (стр. {page}/{pages}, всего {total})"
CAND_EMPTY = "Кандидатов по фильтрам нет."
FILTER_BRANCH = "Фильтр по филиалу:"
FILTER_POSITION = "Фильтр по позиции:"
FILTER_STATUS = "Фильтр по статусу:"
FILTER_ALL = "Все"
MY_CANDIDATES_EMPTY = "Пока нет кандидатов по вашему филиалу."
CHOOSE_STATUS = "Новый статус для кандидата #{id}:"
STATUS_SET = "✅ Кандидат #{id}: статус «{status}»"
ASK_STATUS_REASON = "Укажите причину (обязательно):"
STATUS_CHANGE_FOR_RECRUITER = (
    "ℹ️ {who} изменил статус кандидата #{id} {name}: {old} → {new}{reason}"
)
CANDIDATE_NOT_FOUND = "Кандидат не найден."
CAND_USAGE = "Использование: /candidate &lt;id&gt;"
MANAGER_STATUS_BUTTONS_HINT = "Доступные действия:"

# ── Отчёты ───────────────────────────────────────────────────────────
REPORT_ASK_FROM = "Период отчёта. Дата начала (ДД.ММ.ГГГГ):"
REPORT_ASK_TO = "Дата конца (ДД.ММ.ГГГГ):"
REPORT_INVALID_DATE = "Формат даты: ДД.ММ.ГГГГ (например 01.06.2026)."
REPORT_ASK_BRANCH = "Филиал (или «Все»):"
REPORT_ASK_POSITION = "Позиция (или «Все»):"
REPORT_TEMPLATE = (
    "📊 <b>Отчёт {date_from} — {date_to}</b>\n"
    "Филиал: {branch} · Позиция: {position}\n\n"
    "<b>Воронка:</b>\n"
    "• Откликнулось: {applied}\n"
    "• Прошли скрининг: {screened} ({screened_pct}%)\n"
    "• Пришли на собеседование: {came} ({came_pct}%)\n"
    "• Вышли на стажировку: {internship} ({internship_pct}%)\n"
    "• Приняты: {hired} ({hired_pct}%)\n\n"
    "<b>Отказы по критериям ({rejected_total}):</b>\n{rejections}\n"
    "<b>Источники:</b>\n{sources}"
)
BTN_DOWNLOAD_EXCEL = "📥 Скачать Excel"
EXPORT_CAPTION = "📥 Анкеты за период ({count} шт.)"
EXPORT_EMPTY = "За выбранный период анкет нет."

# ── Админ ────────────────────────────────────────────────────────────
ADD_USER_USAGE = (
    "Использование: /add_user <code>tg_id</code> <code>роль</code> [филиал]\n"
    "Роли: recruiter, branch_manager, chef, admin\n"
    "Пример: /add_user 123456789 branch_manager Чиланзар"
)
USER_ADDED = "✅ Сотрудник добавлен: {tg_id}, роль {role}{branch}"
USER_EXISTS = "Этот tg_id уже в списке сотрудников."
UNKNOWN_ROLE = "Неизвестная роль. Доступны: recruiter, branch_manager, chef, admin"
UNKNOWN_BRANCH = "Филиал не найден. Доступны: {branches}"
MANAGER_NEEDS_BRANCH = "Для роли branch_manager укажите филиал."
USERS_TITLE = "👥 <b>Сотрудники:</b>"
BIND_CHAT_USAGE = (
    "Запустите команду В нужном чате:\n"
    "/bind_chat <code>филиал</code> — привязать чат к филиалу\n"
    "/bind_chat kitchen — чат «Кухня» (повара)"
)
BIND_CHAT_PRIVATE = (
    "⚠️ Эту команду нужно выполнять <b>внутри группового чата</b> филиала "
    "или кухни, а не в личке с ботом.\n\n"
    "Добавьте бота в рабочий чат и напишите команду там."
)
CHAT_BOUND_BRANCH = "✅ Этот чат привязан к филиалу «{branch}». Сюда будут приходить карточки кандидатов."
CHAT_BOUND_KITCHEN = "✅ Этот чат привязан как «Кухня» — сюда будут приходить карточки поваров."
SET_SETTING_USAGE = (
    "Использование: /set_setting <code>ключ</code> <code>значение</code>\n"
    "Ключи: {keys}"
)
SETTING_SET = "✅ {key} = {value}"
SETTING_NOT_NUMBER = "⚠️ Для «{key}» нужно число (например 30). Значение не сохранено."
UNKNOWN_SETTING = "Неизвестный ключ настройки."
SETTINGS_TITLE = "⚙️ <b>Настройки:</b>"

# ── Еженедельная сверка ──────────────────────────────────────────────
WEEKLY_CHECKIN_TITLE = "📋 <b>День сверки — чеклист рекрутера</b>\n\n"
WEEKLY_VACANCIES = "<b>Открытые вакансии (проверьте актуальность):</b>\n{lines}\n"
WEEKLY_NO_VACANCIES = "Открытых вакансий нет.\n"
WEEKLY_HIRED = "<b>Вышли на работу за неделю:</b>\n{lines}\n"
WEEKLY_NO_HIRED = "За неделю никто не принят.\n"
WEEKLY_INTERNSHIP_FAILED = "<b>Не прошли стажировку за неделю:</b>\n{lines}\n"
WEEKLY_REJECTIONS = "<b>Отказы по критериям за неделю:</b>\n{lines}"

ACTION_CANCELLED = "Действие отменено."
