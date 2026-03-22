import asyncio
import os
import aiohttp
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

from thales import process_message

# ─── API interne pour ask_thales (Archimède → Thalès) ────────────────────────
_api = FastAPI(title="Thalès Internal API")


class AskRequest(BaseModel):
    question: str
    context: Optional[str] = ""


@_api.post("/ask")
async def api_ask(req: AskRequest):
    result = await process_message(req.question, chat_id=0)
    return {"result": result}


@_api.get("/health")
def api_health():
    return {"status": "ok", "service": "thales"}


async def _run_api():
    port = int(os.environ.get("PORT", 8000))
    config = uvicorn.Config(_api, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)
    print(f"[thales] API interne démarrée sur port {port}")
    await server.serve()


TELEGRAM_TOKEN = os.environ.get("THALES_TELEGRAM_TOKEN", "")
ALLOWED_USER_ID = int(os.environ.get("ALLOWED_USER_ID") or "0")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    if ALLOWED_USER_ID and update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("❌ Accès non autorisé.")
        return

    text = update.message.text
    if not text:
        return

    thinking = await update.message.reply_text("…")
    chat_id = update.effective_chat.id
    try:
        result = await process_message(text, chat_id)
        await thinking.edit_text(result)
    except Exception as e:
        await thinking.edit_text(f"❌ {str(e)[:200]}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Thalès opérationnel.\n\n"
        "• Diagnostic → *diagnostic*\n"
        "• Statut Railway → *status*\n"
        "• Questions tech → directement\n\n"
        f"ID : `{update.effective_user.id}`",
        parse_mode="Markdown"
    )


async def post_init(app: Application):
    if ALLOWED_USER_ID:
        try:
            await app.bot.send_message(
                chat_id=ALLOWED_USER_ID,
                text="Thalès en ligne."
            )
        except Exception as e:
            print(f"[thales] ⚠️ DM inaccessible: {e}")


async def _run_bot():
    if not TELEGRAM_TOKEN:
        print("[thales] ⚠️ THALES_TELEGRAM_TOKEN manquant — bot Telegram désactivé")
        return

    print("[thales] Bot démarré — attente 15s pour libérer le polling...")
    await asyncio.sleep(15)

    tg_app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    async with tg_app:
        await tg_app.start()
        await tg_app.updater.start_polling(drop_pending_updates=True)
        await asyncio.Event().wait()
        await tg_app.updater.stop()
        await tg_app.stop()


async def _register_thales():
    hermes_url = os.environ.get("HERMES_URL", "http://hermes-api.railway.internal:8000")
    hermes_key = os.environ.get("HERMES_API_KEY", "")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{hermes_url}/agents/register",
                json={
                    "name": "thales",
                    "agent_type": "cloud",
                    "capabilities": ["infrastructure", "railway", "docker", "architecture", "code_review"],
                    "metadata": {"version": "1.0", "platform": "railway"}
                },
                headers={"x-api-key": hermes_key},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status == 200:
                    print("[thales] ✅ Enregistré auprès d'Hermès")
                else:
                    print(f"[thales] ⚠️ Enregistrement échoué: HTTP {r.status}")
    except Exception as e:
        print(f"[thales] ⚠️ Enregistrement erreur: {e}")


async def _heartbeat_loop():
    hermes_url = os.environ.get("HERMES_URL", "http://hermes-api.railway.internal:8000")
    hermes_key = os.environ.get("HERMES_API_KEY", "")
    consecutive_failures = 0
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{hermes_url}/agents/heartbeat",
                    params={"name": "thales"},
                    headers={"x-api-key": hermes_key},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as r:
                    if r.status == 200:
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1
                        if consecutive_failures <= 3:
                            print(f"[thales] ⚠️ Heartbeat échoué: HTTP {r.status}")
        except Exception as e:
            consecutive_failures += 1
            if consecutive_failures <= 3:
                print(f"[thales] ⚠️ Heartbeat erreur: {e}")
        await asyncio.sleep(30)


async def main():
    # Registration en background — ne bloque pas le startup
    asyncio.create_task(_register_thales())
    asyncio.create_task(_heartbeat_loop())
    await asyncio.gather(_run_api(), _run_bot())


if __name__ == "__main__":
    asyncio.run(main())
