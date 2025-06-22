import os
import logging
import sqlite3
from typing import TypedDict, List, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from telegram.helpers import escape_markdown

BOT_TOKEN = os.getenv("BOT_TOKEN") or " "
admin_ids = [5601411156]
ADMIN_USERNAME = "Men_of_G"
DB_PATH = "support_bot.db"

logging.basicConfig(level=logging.INFO)

class UserState(TypedDict):
    q_index: int
    answers: List[Tuple[str, str]]
    awaiting_answer: bool

user_states: dict[int, UserState] = {}
pending_replies = {}
survey_completed = set()
allowed_retake = set()

greeting_text = (
    "Привет! Я студент ММК, Богдан Толкачев, и я пишу проектную работу на тему зависимостей.\n\n"
    "Я изучаю то, как зависимости формируются, и как можно помочь человеку с зависимостью.\n\n"
    "Ваши ответы помогут более подробно раскрыть эту тему, постарайтесь быть как можно искренними, "
    "и пишите всё, что считаете нужным — тут нет мелочей. Если у вас есть другие зависимости "
    "(переедание/алкоголь), то можете написать о них — это действительно очень важно.\n\n"
    "⬇️ Нажмите кнопку ниже, чтобы начать:"
)

thank_you_text = (
    "Спасибо большое за твоё время. Это маленький вклад в большое дело. "
    "Дело, которое в дальнейшем, как я верю, спасёт не мало семей от разрушения 🙏"
)

questions = [
    "1️⃣ Расскажи, пожалуйста, о том дне, когда ты впервые закурил. Что ты почувствовал?",
    "2️⃣ Что ты чувствовал на следующий день?",
    "3️⃣ Какие события произошли в твоей жизни до того, как к тебе в голову пришла идея попробовать закурить?",
    "4️⃣ Расскажи, пожалуйста, обстановку в своей семье: часто ли ты чувствуешь напряжённую обстановку дома? Как твои отношения с родителями?",
    "5️⃣ Как ты думаешь, твоя привычка курить связана с тем, что произошло в твоей жизни?",
    "6️⃣ Почему ты продолжаешь курить? Доставляет ли тебе сейчас удовольствие твоя зависимость?",
    "7️⃣ Если бы тебе предоставили возможность бросить зависимость, пройти терапию и разобраться в проблеме, ты бы согласился/лась?"
]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            from_admin BOOLEAN,
            text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_message(user_id: int, text: str, from_admin: bool):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO messages (user_id, from_admin, text) VALUES (?, ?, ?)", (user_id, from_admin, text))
    conn.commit()
    conn.close()

def get_users_with_messages():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT DISTINCT user_id FROM messages").fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_chat_history(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT from_admin, text, timestamp FROM messages WHERE user_id = ? ORDER BY id", (user_id,)).fetchall()
    conn.close()
    return rows

def _escape_md(text: str) -> str:
    return escape_markdown(text or "", version=2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in admin_ids:
        await update.message.reply_text("👋 Привет, админ! Используй /users для просмотра чатов.")
        return
    if user_id in survey_completed and user_id not in allowed_retake:
        await update.message.reply_text("Вы уже проходили опрос. Обратитесь к администратору, чтобы пройти снова.")
        return
    keyboard = [[InlineKeyboardButton("Начать опрос", callback_data="start_survey")]]
    await update.message.reply_text(greeting_text, reply_markup=InlineKeyboardMarkup(keyboard))
    save_message(user_id, update.message.text or "/start", from_admin=False)

async def start_survey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id in survey_completed and user_id not in allowed_retake:
        await context.bot.send_message(user_id, "Вы уже завершили опрос. Администратор должен разрешить повтор.")
        return
    user_states[user_id] = {"q_index": 0, "answers": [], "awaiting_answer": True}
    await context.bot.send_message(chat_id=user_id, text=questions[0])

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id in admin_ids and user_id in pending_replies:
        target_id = pending_replies.pop(user_id)
        save_message(target_id, text, from_admin=True)
        await context.bot.send_message(chat_id=target_id, text=f"💬 Ответ от администратора:\n\n{text}")
        await update.message.reply_text("✅ Ответ отправлен.")
        return

    if user_id not in user_states:
        await update.message.reply_text("Пожалуйста, начни с команды /start.")
        return

    state = user_states[user_id]
    if not state["awaiting_answer"]:
        return

    q_index = state["q_index"]
    question = questions[q_index]

    if len(state["answers"]) > q_index:
        state["answers"][q_index] = (question, text)
    else:
        state["answers"].append((question, text))

    save_message(user_id, text, from_admin=False)
    state["awaiting_answer"] = False

    user = update.effective_user
    header = f"{user.full_name} (@{user.username})" if user.username else user.full_name
    message_md = (
        f"*Ответ пользователя* {_escape_md(header)}\n"
        f"*Вопрос:* {_escape_md(question)}\n"
        f"*Ответ:* {_escape_md(text)}"
    )

    for admin_id in admin_ids:
        await context.bot.send_message(admin_id, message_md, parse_mode="MarkdownV2")

    buttons = []
    if q_index > 0:
        buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data="back_question"))
    if q_index + 1 < len(questions):
        buttons.append(InlineKeyboardButton("➡️ Далее", callback_data="next_question"))
    else:
        buttons.append(InlineKeyboardButton("✅ Завершить", callback_data="finish_survey"))

    reply_markup = InlineKeyboardMarkup([buttons])
    await context.bot.send_message(chat_id=user_id, text=questions[state["q_index"]], reply_markup=reply_markup)
    state["awaiting_answer"] = True

async def next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    state = user_states.get(uid)
    if not state or state["awaiting_answer"]:
        if state:
            await query.answer("Сначала ответьте на текущий вопрос.", show_alert=True)
        return
    if state["q_index"] + 1 < len(questions):
        state["q_index"] += 1
        state["awaiting_answer"] = True
        await query.edit_message_text(questions[state["q_index"]])

async def back_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    state = user_states.get(uid)
    if state and state["q_index"] > 0:
        state["q_index"] -= 1
        state["awaiting_answer"] = True
        await query.edit_message_text(questions[state["q_index"]])

async def finish_survey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    user_states.pop(uid, None)
    survey_completed.add(uid)
    await query.edit_message_text(thank_you_text)
    kb = [[InlineKeyboardButton("Связаться с админом", url=f"https://t.me/{ADMIN_USERNAME}")]]
    await context.bot.send_message(uid, "Если у вас есть вопросы, свяжитесь с админом:", reply_markup=InlineKeyboardMarkup(kb))

async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admin_ids:
        return
    users = get_users_with_messages()
    if not users:
        await update.message.reply_text("Нет активных пользователей.")
        return
    keyboard = [[InlineKeyboardButton(f"Пользователь {uid}", callback_data=f"view_{uid}")] for uid in users]
    await update.message.reply_text("Выберите пользователя:", reply_markup=InlineKeyboardMarkup(keyboard))

async def view_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = int(query.data.split("_")[1])
    rows = get_chat_history(uid)
    lines = [f"{'👨‍💻 Админ' if from_admin else '👤 Пользователь'}: {text}" for from_admin, text, _ in rows]
    text = "\n\n".join(lines) or "История пуста."
    keyboard = [
        [InlineKeyboardButton("✉️ Ответить", callback_data=f"reply_{uid}")],
        [InlineKeyboardButton("♻️ Разрешить повтор", callback_data=f"allow_{uid}")]
    ]
    await query.message.reply_text(f"🗂 История с {uid}:\n\n{text}", reply_markup=InlineKeyboardMarkup(keyboard))

async def prepare_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = int(query.data.split("_")[1])
    pending_replies[query.from_user.id] = uid
    await query.message.reply_text("✍️ Напишите сообщение для пользователя:")

async def allow_retake(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = int(query.data.split("_")[1])
    allowed_retake.add(uid)
    await query.message.reply_text(f"✅ Пользователь {uid} теперь может пройти опрос повторно.")

async def handle_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    if data == "next_question":
        await next_question(update, context)
    elif data == "back_question":
        await back_question(update, context)
    elif data == "finish_survey":
        await finish_survey(update, context)

def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    app.add_handler(CallbackQueryHandler(start_survey, pattern="^start_survey$"))
    app.add_handler(CallbackQueryHandler(handle_navigation, pattern="^(next_question|back_question|finish_survey)$"))
    app.add_handler(CallbackQueryHandler(view_messages, pattern="^view_"))
    app.add_handler(CallbackQueryHandler(prepare_reply, pattern="^reply_"))
    app.add_handler(CallbackQueryHandler(allow_retake, pattern="^allow_"))

    app.run_polling()

if __name__ == "__main__":
    main()