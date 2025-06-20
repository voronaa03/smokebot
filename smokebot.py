from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)
from telegram.helpers import escape_markdown
import re

admin_id = 5601411156
BOT_TOKEN = "8064625815:AAFJKTIk2iU8IDBrsrdabMLqEAya_l_9Coo"
BUTTON_ADMIN_USERNAME = "Men_of_G"

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
    "1️⃣ Расскажи, пожалуйста, о том дне, когда ты впервые закурил. Что ты почувствовал? Какие мысли у тебя были во время этого?",
    "2️⃣ Что ты чувствовал на следующий день?",
    "3️⃣ Какие события произошли в твоей жизни до того, как к тебе в голову пришла идея попробовать закурить?",
    "4️⃣ Расскажи, пожалуйста, обстановку в своей семье: часто ли ты чувствуешь напряжённую обстановку дома? Как твои отношения с родителями?",
    "5️⃣ Как ты думаешь, твоя привычка курить связана с тем, что произошло в твоей жизни?",
    "6️⃣ Почему ты продолжаешь курить? Доставляет ли тебе сейчас удовольствие твоя зависимость?",
    "7️⃣ Если бы тебе предоставили возможность бросить зависимость, пройти терапию и разобраться в проблеме, ты бы согласился/лась?"
]

user_states: dict[int, dict] = {}

def _escape_md(text: str) -> str:
    return escape_markdown(text or "", version=2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[InlineKeyboardButton("Начать опрос", callback_data="start_survey")]]
    await update.message.reply_text(greeting_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def start_survey(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_states[user_id] = {"q_index": 0, "answers": [], "awaiting_answer": True}
    await query.edit_message_text(text=questions[0])

async def next_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = user_states.get(user_id)
    if not state:
        return
    if state["awaiting_answer"]:
        await query.answer("Сначала ответьте на текущий вопрос.", show_alert=True)
        return
    if state["q_index"] + 1 < len(questions):
        state["q_index"] += 1
        state["awaiting_answer"] = True
        await query.edit_message_text(text=questions[state["q_index"]])

async def back_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = user_states.get(user_id)
    if not state:
        return
    if state["q_index"] > 0:
        state["q_index"] -= 1
        state["awaiting_answer"] = True
        await query.edit_message_text(text=questions[state["q_index"]])

async def finish_survey(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = user_states.pop(user_id, None)
    if not state:
        return
    await query.edit_message_text(thank_you_text)

    keyboard = [[InlineKeyboardButton("Связаться с админом", callback_data="contact_admin")]]
    await context.bot.send_message(
        chat_id=user_id,
        text="Если у вас есть вопросы, свяжитесь с админом:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# async def contact_admin_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#    query = update.callback_query
#    await query.answer()
#    await query.message.reply_text(f"Напишите админу: @{BUTTON_ADMIN_USERNAME}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text
    state = user_states.get(user_id)

    if not state:
        await update.message.reply_text("Пожалуйста, начни с команды /start.")
        return

    if not state["awaiting_answer"]:
        return

    q_index = state["q_index"]

    if len(state["answers"]) > q_index:
        state["answers"][q_index] = (questions[q_index], text)
    else:
        state["answers"].append((questions[q_index], text))
    state["awaiting_answer"] = False

    user = update.effective_user
    header_raw = f"{user.full_name} (@{user.username})" if user.username else user.full_name
    header = _escape_md(header_raw)
    answer_md = (
        f"*Ответ пользователя* {header}\n"
        f"*Вопрос:* {_escape_md(questions[q_index])}\n"
        f"*Ответ:* {_escape_md(text)}"
    )

    await context.bot.send_message(chat_id=admin_id, text=answer_md, parse_mode="MarkdownV2")

    buttons = []
    if q_index > 0:
        buttons.append(InlineKeyboardButton("⬅️ Back", callback_data="back_question"))
    if q_index + 1 < len(questions):
        buttons.append(InlineKeyboardButton("➡️ Next", callback_data="next_question"))
    else:
        buttons.append(InlineKeyboardButton("✅ Finish", callback_data="finish_survey"))

    await update.message.reply_text(
        "Спасибо за ответ. Вы можете перейти дальше или вернуться к предыдущему вопросу:",
        reply_markup=InlineKeyboardMarkup([buttons])
    )


# 🚀 Запуск
def main() -> None:
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(start_survey, pattern="^start_survey$"))
    app.add_handler(CallbackQueryHandler(next_question, pattern="^next_question$"))
    app.add_handler(CallbackQueryHandler(back_question, pattern="^back_question$"))
    app.add_handler(CallbackQueryHandler(finish_survey, pattern="^finish_survey$"))
#    app.add_handler(CallbackQueryHandler(contact_admin_button, pattern="^contact_admin$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running… Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
