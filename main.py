import asyncio
import csv
import html
import os
import re
from datetime import datetime, date

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BotCommand, MenuButtonCommands,
    BotCommandScopeDefault, BotCommandScopeAllPrivateChats, BotCommandScopeChat,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
)

# ================= НАСТРОЙКИ =================
BOT_TOKEN = os.getenv("BOT_TOKEN", "9142696714:AAFMi5254_4ROAGumEPC7mI1ArrqdECbxzU")
ADMIN_ID = 1682544256
CSV_FILE = "участники_выезд.csv"  # новый файл: структура отличается от старой версии бота
# =============================================

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ---------- Тексты, которые нужно отредактировать под себя ----------
WELCOME_TEXT = (
    "👋 <b>Привет!</b>\n\n"
    "Это бот для регистрации на выезд. Здесь ты можешь:\n"
    "• зарегистрироваться и заполнить анкету;\n"
    "• посмотреть и изменить свою анкету;\n"
    "• узнать подробности о выезде;\n"
    "• связаться с организаторами, если возникли вопросы.\n\n"
    "Выбери нужное действие с помощью кнопок ниже 👇"
)

HELP_TEXT = (
    "🆘 <b>Помощь и поддержка</b>\n\n"
    "Если у тебя возникли проблемы с регистрацией или вопросы по выезду — "
    "напиши организаторам:\n\n"
    "👤 Контакт: @ваш_ник_поддержки\n"
    "📞 Телефон: 8XXXXXXXXXX\n\n"
    "Мы отвечаем в течение дня. Если ты ошибся при заполнении анкеты, "
    "нажми «Изменить свою анкету» — и исправь нужные данные."
)

TRIP_INFO_TEXT = (
    "🏕 <b>О выезде</b>\n\n"
    "📅 <b>Дата:</b> XX–XX месяца 20XX\n"
    "📍 <b>Место:</b> название базы / адрес\n"
    "🚌 <b>Сбор и отправление:</b> время и место сбора\n"
    "💰 <b>Стоимость:</b> XXXX ₽\n\n"
    "🎒 <b>Что взять с собой:</b> документы, удобная одежда и обувь, "
    "личные медикаменты, хорошее настроение.\n\n"
    "Подробности будут приходить в этом боте — не блокируй его 😉"
)

# ---------- Названия кнопок ----------
BTN_REGISTER = "Регистрация"
BTN_HELP = "Помощь"
BTN_TRIP = "О выезде"
BTN_VIEW = "Посмотреть свою анкету"
BTN_EDIT = "Изменить свою анкету"
BTN_YES = "Да"
BTN_NO = "Нет"
BTN_BACK = "⬅️ Назад"


# ---------- Состояния ----------
class RegForm(StatesGroup):
    full_name = State()
    birth_date = State()
    group = State()
    tg_nick = State()
    phone = State()
    meat = State()
    health_choice = State()
    health_details = State()


# Порядок шагов регистрации
ORDER = ["full_name", "birth_date", "group", "tg_nick", "phone", "meat", "health"]

# Какой шаг какому состоянию соответствует
STEP_STATE = {
    "full_name": RegForm.full_name,
    "birth_date": RegForm.birth_date,
    "group": RegForm.group,
    "tg_nick": RegForm.tg_nick,
    "phone": RegForm.phone,
    "meat": RegForm.meat,
    "health": RegForm.health_choice,
    "health_details": RegForm.health_details,
}
STATE_TO_STEP = {st.state: step for step, st in STEP_STATE.items()}

# Названия полей (для вывода анкеты и меню редактирования)
FIELD_TITLES = {
    "full_name": "ФИО",
    "birth_date": "Дата рождения",
    "group": "Учебная группа",
    "tg_nick": "Ник в Telegram",
    "phone": "Номер телефона",
    "meat": "Ест мясо",
    "health": "Здоровье / аллергии / питание",
}

# Колонки CSV
CSV_COLUMNS = [
    ("id", "ID"),
    ("username", "Username"),
    ("full_name", "ФИО"),
    ("birth_date", "Дата рождения"),
    ("group", "Группа"),
    ("tg_nick", "Ник в ТГ"),
    ("phone", "Телефон"),
    ("meat", "Ест мясо"),
    ("health", "Здоровье"),
]


# ================= Работа с таблицей =================
def load_all() -> dict[int, dict]:
    """Читает всех участников: {user_id: анкета}."""
    if not os.path.isfile(CSV_FILE):
        return {}
    result = {}
    with open(CSV_FILE, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            record = {key: row.get(title, "") for key, title in CSV_COLUMNS}
            try:
                result[int(record["id"])] = record
            except (ValueError, TypeError):
                continue
    return result


def save_all(participants: dict[int, dict]) -> None:
    with open(CSV_FILE, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([title for _, title in CSV_COLUMNS])
        for record in participants.values():
            writer.writerow([record.get(key, "") for key, _ in CSV_COLUMNS])


def get_participant(user_id: int) -> dict | None:
    return load_all().get(user_id)


def upsert_participant(user_id: int, record: dict) -> None:
    """Создаёт анкету или обновляет существующую."""
    participants = load_all()
    record["id"] = user_id
    participants[user_id] = record
    save_all(participants)


def get_all_user_ids() -> list[int]:
    return list(load_all().keys())


# ================= Клавиатуры =================
def main_menu(registered: bool) -> ReplyKeyboardMarkup:
    if registered:
        rows = [
            [KeyboardButton(text=BTN_VIEW), KeyboardButton(text=BTN_EDIT)],
            [KeyboardButton(text=BTN_HELP), KeyboardButton(text=BTN_TRIP)],
        ]
    else:
        rows = [
            [KeyboardButton(text=BTN_REGISTER)],
            [KeyboardButton(text=BTN_HELP), KeyboardButton(text=BTN_TRIP)],
        ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def yes_no_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_YES), KeyboardButton(text=BTN_NO)]],
        resize_keyboard=True,
    )


def back_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_BACK)]],
        resize_keyboard=True,
    )


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить мой номер", request_contact=True)]],
        resize_keyboard=True,
    )


def edit_fields_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=title, callback_data=f"edit:{field}")]
        for field, title in FIELD_TITLES.items()
    ]
    rows.append([InlineKeyboardButton(text="↩️ Отмена", callback_data="edit:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ================= Тексты вопросов =================
PROMPTS = {
    "full_name": (
        "📝 <b>Шаг 1 из 7. ФИО</b>\n\n"
        "Введи свои <b>фамилию, имя и отчество</b> полностью, через пробел.\n"
        "Пример: <i>Иванов Иван Иванович</i>"
    ),
    "birth_date": (
        "🎂 <b>Шаг 2 из 7. Дата рождения</b>\n\n"
        "Введи дату рождения в формате <b>ДД.ММ.ГГГГ</b>.\n"
        "Пример: <i>25.03.2005</i>"
    ),
    "group": (
        "🎓 <b>Шаг 3 из 7. Учебная группа</b>\n\n"
        "Введи название своей группы так, как оно написано в расписании.\n"
        "Пример: <i>РК6-31Б</i>"
    ),
    "tg_nick": (
        "💬 <b>Шаг 4 из 7. Ник в Telegram</b>\n\n"
        "Введи свой ник, он должен начинаться с символа <b>@</b>.\n"
        "Пример: <i>@ivan_ivanov</i>"
    ),
    "phone": (
        "📞 <b>Шаг 5 из 7. Номер телефона</b>\n\n"
        "Введи номер в формате <b>8XXXXXXXXXX</b> (11 цифр, без пробелов, скобок и тире).\n"
        "Пример: <i>89001234567</i>\n\n"
        "Или просто нажми кнопку ниже, чтобы отправить номер автоматически 👇"
    ),
    "meat": (
        "🍖 <b>Шаг 6 из 7. Питание</b>\n\n"
        "Ты ешь мясо?\n"
        "Выбери ответ кнопкой: <b>Да</b> или <b>Нет</b>."
    ),
    "health": (
        "🩺 <b>Шаг 7 из 7. Здоровье</b>\n\n"
        "Есть ли у тебя какие-либо заболевания, аллергии, особенности здоровья или питания?\n"
        "Выбери ответ кнопкой: <b>Да</b> или <b>Нет</b>."
    ),
    "health_details": (
        "🩺 <b>Уточни, пожалуйста</b>\n\n"
        "Опиши одним сообщением свои заболевания, аллергии и особенности здоровья или питания. "
        "Эта информация поможет организаторам учесть всё необходимое.\n"
        "Пример: <i>Аллергия на орехи и цитрусовые, непереносимость лактозы</i>\n\n"
        "Если нажал «Да» по ошибке или передумал — нажми кнопку <b>«⬅️ Назад»</b> "
        "и сможешь ответить «Нет»."
    ),
}

ERRORS = {
    "full_name": "❌ Нужно ввести <b>три слова</b> — фамилию, имя и отчество, только буквами.\nПример: <i>Иванов Иван Иванович</i>",
    "birth_date": "❌ Не получилось распознать дату. Введи её в формате <b>ДД.ММ.ГГГГ</b>.\nПример: <i>25.03.2005</i>",
    "group": "❌ Неверный формат группы. Пример: <i>РК6-31Б</i>",
    "tg_nick": "❌ Ник должен начинаться с <b>@</b> и содержать от 5 до 32 символов (латинские буквы, цифры, «_»).\nПример: <i>@ivan_ivanov</i>",
    "phone": "❌ Номер должен быть в формате <b>8XXXXXXXXXX</b> (ровно 11 цифр).\nПример: <i>89001234567</i>",
    "meat": "❌ Пожалуйста, выбери ответ кнопкой: <b>Да</b> или <b>Нет</b>.",
    "health": "❌ Пожалуйста, выбери ответ кнопкой: <b>Да</b> или <b>Нет</b>.",
    "health_details": "❌ Опиши, пожалуйста, текстом (хотя бы пару слов).",
}


def keyboard_for(step: str):
    if step == "phone":
        return phone_kb()
    if step in ("meat", "health"):
        return yes_no_kb()
    if step == "health_details":
        return back_kb()
    return ReplyKeyboardRemove()


async def ask(message: types.Message, state: FSMContext, step: str):
    """Задаёт вопрос и переключает состояние на нужный шаг."""
    await state.set_state(STEP_STATE[step])
    await message.answer(PROMPTS[step], reply_markup=keyboard_for(step))


# ================= Валидаторы (возвращают значение или None) =================
def v_full_name(message: types.Message):
    if not message.text:
        return None
    words = message.text.split()
    if len(words) != 3:
        return None
    if not all(re.fullmatch(r"[А-Яа-яЁёA-Za-z-]+", w) for w in words):
        return None
    return " ".join(w[:1].upper() + w[1:] for w in words)


def v_birth_date(message: types.Message):
    if not message.text:
        return None
    try:
        d = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        return None
    if d > date.today() or d.year < 1950:
        return None
    return d.strftime("%d.%m.%Y")


def v_group(message: types.Message):
    if not message.text:
        return None
    value = message.text.strip().upper()
    if re.fullmatch(r"[А-ЯЁA-Z]{1,5}\d{0,2}-\d{1,3}[А-ЯЁA-Z]{0,2}", value):
        return value
    return None


def v_tg_nick(message: types.Message):
    if not message.text:
        return None
    value = message.text.strip()
    if re.fullmatch(r"@[A-Za-z0-9_]{5,32}", value):
        return value
    return None


def v_phone(message: types.Message):
    if message.contact:
        digits = re.sub(r"\D", "", message.contact.phone_number)
        # +7XXXXXXXXXX или 7XXXXXXXXXX -> 8XXXXXXXXXX
        if len(digits) == 11 and digits[0] == "7":
            digits = "8" + digits[1:]
        return digits if re.fullmatch(r"8\d{10}", digits) else None
    if not message.text:
        return None
    value = message.text.strip()
    return value if re.fullmatch(r"8\d{10}", value) else None


def v_yes_no(message: types.Message):
    if not message.text:
        return None
    text = message.text.strip().lower()
    if text == BTN_YES.lower():
        return "Да"
    if text == BTN_NO.lower():
        return "Нет"
    return None


def v_health_details(message: types.Message):
    if not message.text:
        return None
    value = message.text.strip()
    return value if len(value) >= 2 else None


VALIDATORS = {
    "full_name": v_full_name,
    "birth_date": v_birth_date,
    "group": v_group,
    "tg_nick": v_tg_nick,
    "phone": v_phone,
    "meat": v_yes_no,
    "health": v_yes_no,
    "health_details": v_health_details,
}


# ================= Анкета =================
def format_profile(record: dict) -> str:
    def e(key):
        return html.escape(str(record.get(key, "") or "—"))

    return (
        "📋 <b>Твоя анкета</b>\n\n"
        f"👤 <b>ФИО:</b> {e('full_name')}\n"
        f"🎂 <b>Дата рождения:</b> {e('birth_date')}\n"
        f"🎓 <b>Группа:</b> {e('group')}\n"
        f"💬 <b>Ник в Telegram:</b> {e('tg_nick')}\n"
        f"📞 <b>Телефон:</b> {e('phone')}\n"
        f"🍖 <b>Ест мясо:</b> {e('meat')}\n"
        f"🩺 <b>Здоровье / аллергии / питание:</b> {e('health')}"
    )


# ================= Сохранение значения (регистрация и редактирование) =================
async def accept_value(message: types.Message, state: FSMContext, field: str, value: str):
    data = await state.get_data()
    user = message.from_user
    edit_field = data.get("edit_field")

    # --- Режим редактирования: меняем одно поле и сразу сохраняем ---
    if edit_field:
        record = get_participant(user.id) or {}
        record[field] = value
        record["username"] = user.username or "нет"
        upsert_participant(user.id, record)
        await state.clear()
        await message.answer("✅ Данные обновлены!", reply_markup=main_menu(True))
        await message.answer(format_profile(record))
        return

    # --- Режим регистрации: копим данные и идём дальше ---
    await state.update_data(**{field: value})
    idx = ORDER.index(field)

    if idx + 1 < len(ORDER):
        await ask(message, state, ORDER[idx + 1])
        return

    # Последний шаг — сохраняем анкету
    data = await state.get_data()
    record = {key: data.get(key, "") for key in ORDER}
    record["username"] = user.username or "нет"
    upsert_participant(user.id, record)
    await state.clear()
    await message.answer(
        "🎉 <b>Регистрация завершена!</b>\n\n"
        "Спасибо! Твоя анкета сохранена. Посмотреть или изменить её можно "
        "с помощью кнопок меню ниже. Важные новости мы пришлём в этот чат.",
        reply_markup=main_menu(True),
    )
    await message.answer(format_profile(record))


# ================= Хендлеры =================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await setup_chat_commands(message.chat.id)
    registered = get_participant(message.from_user.id) is not None
    await message.answer(WELCOME_TEXT, reply_markup=main_menu(registered))


@dp.message(Command("cancel_registration"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    was_filling = await state.get_state() is not None
    await state.clear()
    registered = get_participant(message.from_user.id) is not None
    if was_filling:
        text = "❌ Заполнение анкеты отменено. Введённые в этот раз данные не сохранены."
    else:
        text = "Сейчас нечего отменять — ты не заполняешь анкету."
    await message.answer(text, reply_markup=main_menu(registered))


@dp.message(Command("help"))
@dp.message(F.text == BTN_HELP)
async def show_help(message: types.Message):
    await message.answer(HELP_TEXT)


@dp.message(Command("info"))
@dp.message(F.text == BTN_TRIP)
async def show_trip_info(message: types.Message):
    await message.answer(TRIP_INFO_TEXT)


@dp.message(Command("registration"))
@dp.message(F.text == BTN_REGISTER)
async def start_reg(message: types.Message, state: FSMContext):
    if get_participant(message.from_user.id):
        await message.answer(
            "Ты уже зарегистрирован ✅ Свою анкету можно посмотреть или изменить в меню.",
            reply_markup=main_menu(True),
        )
        return
    await state.clear()
    await ask(message, state, "full_name")


@dp.message(Command("profile"))
@dp.message(F.text == BTN_VIEW)
async def view_profile(message: types.Message, state: FSMContext):
    await state.clear()
    record = get_participant(message.from_user.id)
    if not record:
        await message.answer("Анкета не найдена. Нажми «Регистрация».", reply_markup=main_menu(False))
        return
    await message.answer(format_profile(record), reply_markup=main_menu(True))


@dp.message(Command("edit"))
@dp.message(F.text == BTN_EDIT)
async def edit_profile(message: types.Message, state: FSMContext):
    await state.clear()
    if not get_participant(message.from_user.id):
        await message.answer("Анкета не найдена. Нажми «Регистрация».", reply_markup=main_menu(False))
        return
    await message.answer("✏️ Какие данные ты хочешь изменить?", reply_markup=edit_fields_kb())


@dp.callback_query(F.data.startswith("edit:"))
async def choose_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split(":", 1)[1]
    await callback.answer()

    if field == "cancel":
        await callback.message.edit_text("Изменение анкеты отменено.")
        return

    if field not in FIELD_TITLES or not get_participant(callback.from_user.id):
        return

    await callback.message.edit_text(f"✏️ Изменяем: <b>{FIELD_TITLES[field]}</b>")
    await state.clear()
    await state.update_data(edit_field=field)
    await ask(callback.message, state, field)


# Один обработчик на все шаги анкеты (регистрация и редактирование)
@dp.message(StateFilter(*STEP_STATE.values()))
async def process_step(message: types.Message, state: FSMContext):
    step = STATE_TO_STEP[await state.get_state()]

    # Кнопка «Назад» на шаге уточнения болезней — возвращаемся к вопросу Да/Нет
    if step == "health_details" and message.text == BTN_BACK:
        await ask(message, state, "health")
        return

    value = VALIDATORS[step](message)

    if value is None:
        await message.answer(ERRORS[step])
        return

    # Вопрос про болезни: «Нет» — идём дальше, «Да» — просим описать
    if step == "health":
        if value == "Да":
            await ask(message, state, "health_details")
        else:
            await accept_value(message, state, "health", "Нет")
        return

    field = "health" if step == "health_details" else step
    await accept_value(message, state, field, value)


# Админ-команда для рассылки: /send Текст сообщения
@dp.message(Command("send"))
async def cmd_send_all(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    text_to_send = message.text.replace("/send", "", 1).strip()
    if not text_to_send:
        await message.answer(
            "Напишите текст рассылки после команды. Пример:\n"
            "<code>/send Внимание! Мероприятие переносится на 19:00</code>"
        )
        return

    users = get_all_user_ids()
    if not users:
        await message.answer("Список участников пока пуст.")
        return

    count = 0
    for uid in users:
        try:
            await bot.send_message(
                chat_id=uid,
                text=f"📢 Уведомление от организаторов:\n\n{text_to_send}",
                parse_mode=None,
            )
            count += 1
        except Exception:
            pass  # Пользователь заблокировал бота — идём дальше
        await asyncio.sleep(0.05)  # чтобы не упереться в лимиты Telegram

    await message.answer(f"✅ Рассылка завершена! Сообщение получили: {count} чел.")


COMMANDS = [
    BotCommand(command="start", description="перезапуск бота"),
    BotCommand(command="info", description="о выезде"),
    BotCommand(command="registration", description="регистрация"),
    BotCommand(command="profile", description="посмотреть свою анкету"),
    BotCommand(command="edit", description="изменить свою анкету"),
    BotCommand(command="cancel_registration", description="отмена регистрации"),
    BotCommand(command="help", description="помощь"),
]


async def setup_commands():
    """Ставит меню команд во всех областях и языках, чтобы старые настройки его не перекрывали."""
    scopes = [BotCommandScopeDefault(), BotCommandScopeAllPrivateChats()]
    languages = [None, "ru", "en"]
    for scope in scopes:
        for lang in languages:
            try:
                await bot.set_my_commands(COMMANDS, scope=scope, language_code=lang)
            except Exception as e:
                print(f"Не удалось установить команды ({type(scope).__name__}, {lang}): {e}")
    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    except Exception as e:
        print(f"Не удалось включить кнопку «Меню»: {e}")

    try:
        current = await bot.get_my_commands(scope=BotCommandScopeAllPrivateChats())
        print("Команды в меню:", [c.command for c in current])
    except Exception as e:
        print(f"Не удалось проверить команды: {e}")


async def setup_chat_commands(chat_id: int):
    """Команды именно для этого чата — у них самый высокий приоритет в Telegram."""
    try:
        await bot.set_my_commands(COMMANDS, scope=BotCommandScopeChat(chat_id=chat_id))
        await bot.set_chat_menu_button(chat_id=chat_id, menu_button=MenuButtonCommands())
    except Exception as e:
        print(f"Не удалось установить команды для чата {chat_id}: {e}")


async def main():
    await setup_commands()
    print("Бот успешно запущен и готов к работе!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())