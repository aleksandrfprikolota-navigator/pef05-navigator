from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from psycopg.types.json import Json

from app.allowlist import DISCLAIMER, PUBLIC_CONTACTS
from app.answer import answer_question
from app.config import get_settings
from app.db import connect, ensure_schema, set_setting, spend_summary
from app.indexer import rebuild_index

logger = logging.getLogger(__name__)
router = Router()

MENU = {
    "Услуги и форматы": "Какие форматы работы опубликованы на сайте личной практики и что входит в экспертную консультацию?",
    "Опыт и проекты": "Какой опыт, роли и проекты опубликованы у Александра Приколоты?",
    "Сервисы 1С-Премиум": "Какие публичные сервисы есть у ООО «1С-Премиум»?",
}
LEAD_BUTTONS = {"Оставить заявку", "Позвать Александра"}
STEPS = ("name", "company", "role", "task", "contact", "consent")
STEP_TEXT = {
    "name": "Как к вам обращаться?",
    "company": "Из какой вы компании? Если компании нет, напишите «частное лицо».",
    "role": "Какая у вас роль? Например: собственник, ИТ-директор, руководитель проекта.",
    "task": "В чём задача? Двух-трёх предложений достаточно.",
    "contact": "Телефон или почта, если хотите. Можно написать «пропустить».",
    "consent": (
        "Согласны на обработку имени, контакта и описания задачи, чтобы Александр связался с вами? "
        "Оператор — Приколота Александр Фёдорович, как на странице komfortnavigator.ru/privacy. "
        "Заявка хранится на сервере в России до обработки и не дольше 12 месяцев, либо до вашего запроса на удаление. "
        "Напишите «да» или «нет»."
    ),
}


def keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Услуги и форматы"), KeyboardButton(text="Опыт и проекты")],
            [KeyboardButton(text="Сервисы 1С-Премиум")],
            [KeyboardButton(text="Оставить заявку"), KeyboardButton(text="Позвать Александра")],
        ],
        resize_keyboard=True,
    )


def _state(conn, chat_id: int):
    row = conn.execute(
        "SELECT disclaimer_shown, lead_step, lead_draft FROM chat_state WHERE chat_id = %s",
        (chat_id,),
    ).fetchone()
    if row is None:
        conn.execute("INSERT INTO chat_state (chat_id) VALUES (%s)", (chat_id,))
        return False, None, {}
    draft = row[2] if isinstance(row[2], dict) else {}
    return bool(row[0]), row[1], draft


def _save_state(conn, chat_id: int, shown: bool, step, draft: dict) -> None:
    conn.execute(
        """
        INSERT INTO chat_state (chat_id, disclaimer_shown, lead_step, lead_draft)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (chat_id) DO UPDATE
        SET disclaimer_shown = EXCLUDED.disclaimer_shown,
            lead_step = EXCLUDED.lead_step,
            lead_draft = EXCLUDED.lead_draft
        """,
        (chat_id, shown, step, Json(draft)),
    )


def _owner(message: Message) -> bool:
    settings = get_settings()
    return settings.owner_telegram_id != 0 and message.chat.id == settings.owner_telegram_id


def _too_fast(conn, chat_id: int) -> bool:
    row = conn.execute(
        """
        SELECT COUNT(*) FROM messages
        WHERE chat_id = %s AND role = 'user' AND created_at > now() - interval '10 minutes'
        """,
        (chat_id,),
    ).fetchone()
    return int(row[0]) >= 20


async def _finish_lead(message: Message, conn, draft: dict) -> None:
    settings = get_settings()
    consent = draft.get("consent") is True
    if not consent:
        _save_state(conn, message.chat.id, True, None, {})
        await message.answer(
            "Без согласия заявку не сохраняю. "
            f"Написать можно напрямую: {PUBLIC_CONTACTS}.",
            reply_markup=keyboard(),
        )
        return
    row = conn.execute(
        """
        INSERT INTO leads (chat_id, name, company, role_name, task, contact, consent)
        VALUES (%s, %s, %s, %s, %s, %s, true)
        RETURNING id
        """,
        (
            message.chat.id,
            draft.get("name", ""),
            draft.get("company", ""),
            draft.get("role", ""),
            draft.get("task", ""),
            draft.get("contact", ""),
        ),
    ).fetchone()
    lead_id = row[0]
    card = (
        "Заявка «Навигатор»\n"
        f"Номер: {lead_id}\n"
        f"Чат: {message.chat.id}\n"
        f"Имя: {draft.get('name', '')}\n"
        f"Компания: {draft.get('company', '')}\n"
        f"Роль: {draft.get('role', '')}\n"
        f"Задача: {draft.get('task', '')}\n"
        f"Контакт: {draft.get('contact') or 'не указан'}"
    )
    delivered = False
    if settings.owner_telegram_id:
        try:
            await message.bot.send_message(settings.owner_telegram_id, card)
            delivered = True
        except Exception:
            logger.exception("lead delivery failed")
    conn.execute("UPDATE leads SET delivered = %s WHERE id = %s", (delivered, lead_id))
    _save_state(conn, message.chat.id, True, None, {})
    tail = "Александр отвечает в течение рабочего дня."
    if not delivered:
        tail += f" Карточка сохранена. Если нужно быстрее, напишите {PUBLIC_CONTACTS}."
    await message.answer("Заявку принял. " + tail, reply_markup=keyboard())


@router.message(CommandStart())
async def start(message: Message) -> None:
    settings = get_settings()
    conn = connect(settings)
    ensure_schema(conn)
    _save_state(conn, message.chat.id, True, None, {})
    await message.answer(DISCLAIMER + "\n\nНапишите вопрос своими словами или выберите кнопку.", reply_markup=keyboard())


@router.message(Command("id"))
async def show_id(message: Message) -> None:
    await message.answer(f"Telegram ID этого чата: {message.chat.id}")


@router.message(Command("reindex"))
async def reindex(message: Message) -> None:
    if not _owner(message):
        await message.answer("Эту команду выполняет только владелец.")
        return
    await message.answer("Пересобираю индекс. Это занимает несколько минут.")
    try:
        stats = await asyncio.to_thread(rebuild_index, get_settings(), True)
    except Exception:
        logger.exception("reindex failed")
        await message.answer("Переиндексация не завершилась. База ответов осталась прежней.")
        return
    await message.answer(
        f"Индекс {stats['version']}: документов {stats['documents']}, фрагментов {stats['chunks']}, "
        f"новых эмбеддингов {stats['embedded']}."
    )


@router.message(Command("spend"))
async def spend(message: Message) -> None:
    if not _owner(message):
        await message.answer("Эту команду выполняет только владелец.")
        return
    summary = spend_summary(connect(get_settings()))
    await message.answer(
        "За 7 дней: "
        f"ответов {summary['answered_7d']}, отказов {summary['refused_7d']}, "
        f"{summary['cost_7d']:.2f} USD.\n"
        f"С начала месяца: {summary['cost_month']:.2f} USD из {get_settings().monthly_budget_usd:.0f}."
    )


@router.message(Command("sources"))
async def sources(message: Message) -> None:
    if not _owner(message):
        await message.answer("Эту команду выполняет только владелец.")
        return
    rows = connect(get_settings()).execute(
        "SELECT source_url, last_success, last_error FROM crawl_status ORDER BY source_url"
    ).fetchall()
    if not rows:
        await message.answer("Обхода ещё не было.")
        return
    lines = []
    for url, success, error in rows:
        when = success.strftime("%Y-%m-%d %H:%M") if success else "нет"
        extra = f", ошибка: {error}" if error else ""
        lines.append(f"{when}{extra}\n{url}")
    await message.answer("\n\n".join(lines)[:3500])


@router.message(Command("generation"))
async def generation(message: Message) -> None:
    if not _owner(message):
        await message.answer("Эту команду выполняет только владелец.")
        return
    argument = (message.text or "").split(maxsplit=1)
    mode = argument[1].strip().lower() if len(argument) > 1 else ""
    if mode not in {"on", "off"}:
        await message.answer("Напишите /generation on или /generation off.")
        return
    set_setting(connect(get_settings()), "generation_enabled", "1" if mode == "on" else "0")
    await message.answer("Генерация включена." if mode == "on" else "Генерация выключена. Заявка и контакты работают.")


@router.message(F.photo | F.voice | F.audio | F.video | F.document | F.sticker | F.video_note)
async def attachment(message: Message) -> None:
    await message.answer("В этой версии разбираю только текст. Напишите суть задачи словами.", reply_markup=keyboard())


@router.message(F.text)
async def on_text(message: Message) -> None:
    settings = get_settings()
    conn = connect(settings)
    ensure_schema(conn)
    shown, step, draft = _state(conn, message.chat.id)
    text = (message.text or "").strip()
    if text in LEAD_BUTTONS:
        draft = {"origin": text}
        _save_state(conn, message.chat.id, True, "name", draft)
        prefix = DISCLAIMER + "\n\n" if not shown else ""
        await message.answer(prefix + STEP_TEXT["name"], reply_markup=keyboard())
        return
    if step in STEPS:
        if text == "/cancel":
            _save_state(conn, message.chat.id, True, None, {})
            await message.answer("Заявку отменил. Можно задать вопрос.", reply_markup=keyboard())
            return
        if step == "consent":
            answer = text.casefold()
            if answer not in {"да", "нет"}:
                await message.answer("Нужно «да» или «нет».")
                return
            draft["consent"] = answer == "да"
            await _finish_lead(message, conn, draft)
            return
        draft[step] = "" if step == "contact" and text.casefold() == "пропустить" else text[:1000]
        next_index = STEPS.index(step) + 1
        next_step = STEPS[next_index]
        _save_state(conn, message.chat.id, True, next_step, draft)
        await message.answer(STEP_TEXT[next_step])
        return
    if _too_fast(conn, message.chat.id):
        await message.answer("Слишком много сообщений за 10 минут. Напишите чуть позже или оставьте заявку.")
        return
    question = MENU.get(text, text)
    note = ""
    if len(question) > 2000:
        question = question[:2000]
        note = "Сообщение длиннее 2 000 знаков, беру только начало.\n\n"
    if not shown:
        note = DISCLAIMER + "\n\n" + note
        _save_state(conn, message.chat.id, True, None, {})
    await message.bot.send_chat_action(message.chat.id, "typing")
    from app.db import recent_messages

    history = recent_messages(conn, message.chat.id)
    result = await asyncio.to_thread(answer_question, conn, settings, message.chat.id, question, history)
    await message.answer(note + result.text, reply_markup=keyboard())
    if result.warn_owner and settings.owner_telegram_id:
        try:
            await message.bot.send_message(
                settings.owner_telegram_id,
                "Расход OpenAI за месяц перешёл 80 USD. На 100 USD генерация для внешних чатов остановится.",
            )
        except Exception:
            logger.exception("budget warning failed")


async def run() -> None:
    settings = get_settings()
    if not settings.telegram_token:
        raise RuntimeError("В .env нет TELEGRAM_TOKEN. Нужен отдельный бот, не @ExpertDigitalProductsAndBPA_bot.")
    conn = None
    last_error: Exception | None = None
    for _ in range(30):
        try:
            conn = connect(settings)
            break
        except RuntimeError as exc:
            last_error = exc
            logger.info("База ещё не готова, жду 2 секунды")
            await asyncio.sleep(2)
    if conn is None:
        raise last_error
    ensure_schema(conn)
    bot = Bot(settings.telegram_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    await dispatcher.start_polling(bot)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(run())


if __name__ == "__main__":
    main()
