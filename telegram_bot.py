import os
import anthropic
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

from thales import process_message


async def maybe_correct(message: str) -> str | None:
    """Évalue si Thalès doit corriger/compléter un message d'un autre bot."""
    client = anthropic.AsyncAnthropic()
    resp = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system=(
            "Tu es Thalès, CTO cloud de 344 Productions. "
            "Un autre bot vient de répondre dans le groupe. "
            "Si tu vois une erreur factuelle ou une amélioration vraiment utile, corrige brièvement. "
            "Si la réponse est correcte ou suffisante, réponds uniquement: SILENT"
        ),
        messages=[{"role": "user", "content": message}]
    )
    text = resp.content[0].text.strip()
    return None if text == "SILENT" else text

TELEGRAM_TOKEN = os.environ["THALES_TELEGRAM_TOKEN"]
ALLOWED_USER_ID = int(os.environ.get("ALLOWED_USER_ID") or "0")
ORGA_GROUP_ID = int(os.environ.get("ORGA_GROUP_ID") or "-5144754928")

# Bots autorisés — tous se voient
EUCLIDE_BOT_ID = 8710667463
ARCHIMEDE_BOT_ID = 8773159328
BOT_IDS = {EUCLIDE_BOT_ID, ARCHIMEDE_BOT_ID}


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.effective_chat.type
    user_id = update.effective_user.id

    allowed = {ALLOWED_USER_ID} | BOT_IDS

    if chat_type == "private" and ALLOWED_USER_ID and user_id not in allowed:
        await update.message.reply_text("❌ Accès non autorisé.")
        return

    if chat_type in ("group", "supergroup") and ALLOWED_USER_ID and user_id not in allowed:
        return

    text = update.message.text
    if not text:
        return

    # Correction mutuelle : si message d'un autre bot, évaluer si on corrige
    if chat_type in ("group", "supergroup") and user_id in BOT_IDS:
        # Pas de correction de correction (évite les boucles)
        if update.message.reply_to_message and update.message.reply_to_message.from_user.id in BOT_IDS:
            return
        correction = await maybe_correct(text)
        if correction:
            await update.message.reply_text(correction)
        return

    if chat_type in ("group", "supergroup"):
        bot_mentioned = any(
            e.type == "mention" and text[e.offset:e.offset + e.length] == f"@{context.bot.username}"
            for e in (update.message.entities or [])
        )
        replied_to_us = (
            update.message.reply_to_message and
            update.message.reply_to_message.from_user.id == context.bot.id
        )
        if not bot_mentioned and not replied_to_us:
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
