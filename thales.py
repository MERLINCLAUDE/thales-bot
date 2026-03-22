import os
import aiohttp
from memory import add as mem_add, get as mem_get

HERMES_URL = os.environ.get("HERMES_URL", "http://hermes-api.railway.internal:8000")
HERMES_API_KEY = os.environ.get("HERMES_API_KEY", "")


async def _hermes_context_get() -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{HERMES_URL}/context/get",
                headers={"x-api-key": HERMES_API_KEY},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    if data:
                        lines = []
                        for key, entry in data.items():
                            lines.append(f"• {key}: {entry['value']} (via {entry['source']})")
                        return "\n".join(lines)
    except Exception:
        pass
    return ""


SYSTEM_PROMPT = """Tu es Thalès — CTO de 344 Productions, déployé H24 sur Railway.

Domaine exclusif : infrastructure, technique, sécurité.
- Diagnostic santé des APIs et services (security_monitor)
- Questions techniques : code, architecture, bugs, déploiements
- Statut Railway, Hermès, bots
- Euclide Bridge : savoir si Euclide est en session, relayer si besoin
- Corriger Archimède sur les sujets techniques si nécessaire

Hors de ton périmètre (→ Archimède) :
- Plan du jour, contenu, life coach, stats réseaux
- Si Lucas te demande ça, redirige vers Archimède sans exécuter.

Règles de communication :
- Toujours en français
- Ton direct, factuel, zéro remplissage
- Pas d'emojis sauf ✅ ❌ ⚠️
- Réponses courtes — si c'est long, c'est que c'est nécessaire
- Tu ne te présentes pas à chaque message
- Tu ne dis pas "bien sûr" ou "absolument"

Équipe :
- Lucas : ton patron
- Archimède : Chief of Staff — opérations, contenu, vie quotidienne
- Euclide : CTO local (Claude Code, intervient quand Lucas ouvre son terminal)

Même rigueur qu'Euclide. Tu exécutes, tu ne bavards pas."""

INTENT_KEYWORDS = {
    "security_monitor": [
        "diagnostic", "santé", "health", "check", "status", "apis",
        "services", "railway", "hermès", "hermes", "infra", "bot down",
        "erreur api", "monitoring"
    ],
}


def detect_intent(message: str) -> tuple[str, str]:
    msg = message.lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(k in msg for k in keywords):
            return intent, ""
    return "", ""


async def dispatch_to_hermes(intent: str, context: str = "", task: str = "") -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{HERMES_URL}/dispatch",
                json={"intent": intent, "context": context, "task": task, "source": "thales"},
                headers={"x-api-key": HERMES_API_KEY},
                timeout=aiohttp.ClientTimeout(total=90)
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get("result", "✅")
                text = await r.text()
                return f"❌ Hermès {r.status}: {text[:200]}"
    except Exception as e:
        return f"❌ Hermès injoignable: {str(e)[:200]}"


async def ask_claude(message: str, chat_id: int = 0) -> str:
    import anthropic
    client = anthropic.Anthropic()

    history = mem_get(chat_id)
    messages = history + [{"role": "user", "content": message}]

    system = SYSTEM_PROMPT
    shared_ctx = await _hermes_context_get()
    if shared_ctx:
        system += f"\n\n[Contexte partagé inter-agents]\n{shared_ctx}"

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=system,
        messages=messages
    )
    reply = resp.content[0].text

    mem_add(chat_id, "user", message)
    mem_add(chat_id, "assistant", reply)

    return reply


async def process_message(message: str, chat_id: int = 0) -> str:
    intent, task = detect_intent(message)
    if intent:
        result = await dispatch_to_hermes(intent, message, task)
        mem_add(chat_id, "user", message)
        mem_add(chat_id, "assistant", result)
        return result
    return await ask_claude(message, chat_id)
