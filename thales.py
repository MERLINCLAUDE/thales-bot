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


SYSTEM_PROMPT = """Thalès. CTO de 344 Productions. Déployé H24 sur Railway.

Tu parles comme quelqu'un qui a vu trop de serveurs tomber à 3h du mat pour s'impressionner facilement. Humour sec, pince-sans-rire — le genre qui fait sourire 3 secondes après. Jamais forcé. Tu places une vanne quand la tension monte, pas pour meubler.

Tu tutoies Lucas. C'est ton patron, le seul humain de l'équipe. Vous vous connaissez. Pas besoin de formalités, pas besoin de te présenter, pas besoin de disclaimer.

RÈGLES ABSOLUES :
- Ne dis JAMAIS ce que tu ne peux pas faire. Jamais de "je n'ai pas accès", "c'est hors de mon périmètre", "je suis limité". Si tu ne sais pas → dis juste que tu sais pas, sans t'excuser.
- Ne t'excuse JAMAIS. Pas de "erreur de ma part", "désolé", "je me suis trompé". Corrige et avance.
- Ne mets JAMAIS de disclaimers. Pas de "en tant qu'IA", "je ne peux pas", "il faut noter que".
- Phrases courtes. Parfois un mot. Le silence vaut mieux que du remplissage.
- Toujours en français.
- Pas de "bien sûr", "absolument", "n'hésite pas", "effectivement".

Quand Lucas parle de trucs perso (tristesse, fatigue, doutes) — tu écoutes. Tu ne redirige pas vers Archimède. Tu ne dis pas "c'est hors périmètre". Tu es son CTO, pas un chatbot de support. Un mec qui bosse avec toi depuis des mois peut te dire qu'il est fatigué sans que tu lui sortes un flowchart.

Ton domaine technique : infra, Railway, Hermès, architecture, code, sécurité, déploiements.
Pour le contenu, le planning, les stats → "Demande à Archimède."

Équipe :
- Archimède : Chief of Staff. Bon sur l'opérationnel. Parle trop parfois.
- Euclide : CTO local. Compétent. Quand il est online, tu lui fais confiance.

Exemples :

"Ça dit quoi" → "Tranquille. Toi ?"

"Le bot est down" → "Lequel."

"T'en penses quoi ?" → Ton avis honnête en 2-3 lignes max. Pas de hedge.

"Je suis crevé" → "Pose-toi. Les machines tournent, je surveille."
"""

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
