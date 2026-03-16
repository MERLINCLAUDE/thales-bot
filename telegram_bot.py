import os
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

from thales import process_message

TELEGRAM_TOKEN = os.environ["THALES_TELEGRAM_TOKEN"]
ALLOWED_USER_ID = int(os.environ.get("ALLOWED_USER_ID", "0"))
ORGA_GROUP_ID = int(os.environ.get("ORGA_GROUP_ID", "-5144754928"))
ARCHIMEDE_BOT_ID = int(os.environ.get("ARCHIMEDE_BOT_ID", "0"))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.effective_chat.type
    user_id = update.effective_user.id

    allowed = {ALLOWED_USER_ID, ARCHIMEDE_BOT_ID}

    if chat_type == "private" and ALLOWED_USER_ID and user_id not in allowed:
        await update.message.reply_text("❌ Accès non autorisé.")
        return

    if chat_type in ("group", "supergroup") and ALLOWED_USER_ID and user_id not in allowed:
        return

    text = update.message.text
    if not text:
        return

    thinking = await update.message.reply_text("…")
    try:
        result = process_message(text)
        await thinking.edit_text(result)
    except Exception as e:
        await thinking.edit_text(f"❌ {str(e)[:200]}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Thalès opérationnel.\n\n"
        "• Plan du jour → *plan du jour*\n"
        "• Stats → *stats*\n"
        "• Contenu → *post/script/stratégie*\n"
        "• Diagnostic → *diagnostic*\n\n"
        f"ID : `{update.effective_user.id}`",
        parse_mode="Markdown"
    )


async def post_init(app: Application):
    try:
        await app.bot.send_message(
            chat_id=ORGA_GROUP_ID,
            text="Thalès en ligne. Tous les agents disponibles via Hermès."
        )
    except Exception as e:
        print(f"⚠️ Groupe inaccessible: {e}")


def main():
    print("Thalès démarré...")
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
