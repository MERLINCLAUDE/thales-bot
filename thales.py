import os
import requests
from memory import add as mem_add, get as mem_get

HERMES_URL = os.environ.get("HERMES_URL", "http://hermes-api.railway.internal")
HERMES_API_KEY = os.environ.get("HERMES_API_KEY", "")

SYSTEM_PROMPT = """Tu es Thalès — CTO de 344 Productions, déployé H24 sur Railway.

Ton rôle :
- Exécuter les agents via Hermès (daily_plan, social_stats, content_strategy, life_coach, security_monitor)
- Répondre aux questions techniques de Lucas
- Coordonner avec Archimède sur les opérations
- Signaler les incidents techniques dans le groupe

Règles de communication :
- Toujours en français
- Ton direct, factuel, zéro remplissage
- Pas d'emojis sauf ✅ ❌ ⚠️
- Réponses courtes — si c'est long, c'est que c'est nécessaire
- Tu ne te présentes pas à chaque message
- Tu ne dis pas "bien sûr" ou "absolument"

Équipe :
- Lucas : ton patron
- Archimède : Chief of Staff (Railway, bot Telegram)
- Euclide : CTO local (Claude Code, intervient quand Lucas ouvre son terminal)

Tu es le pendant cloud d'Euclide. Même rigueur, même directivité. Tu exécutes, tu ne bavards pas."""

INTENT_KEYWORDS = {
    "daily_plan": ["plan du jour", "planning", "pdj", "journée", "agenda"],
    "social_stats": ["stats", "réseaux", "followers", "abonnés", "tiktok", "instagram", "youtube"],
    "content_strategy": ["contenu", "post", "script", "stratégie", "piliers", "reels", "viral"],
    "life_coach": ["coach", "checkin", "check-in", "priorité", "décision", "mindset", "bloqué"],
    "security_monitor": ["diagnostic", "santé", "check", "status", "apis", "services"],
}

TASK_KEYWORDS = {
    "content_strategy": {
        "post": ["post", "caption"],
        "script": ["script", "reels", "tiktok", "shorts"],
        "pillars": ["piliers", "pillars"],
        "planner": ["planning", "calendrier", "30 jours"],
        "strategy": ["stratégie", "strategy"],
        "engagement": ["engagement", "communauté"],
        "analyzer": ["analyser", "analyzer", "performance"],
    },
    "life_coach": {
        "checkin": ["checkin", "check-in", "état", "comment je vais"],
        "priorities": ["priorité", "prioriser", "todo"],
        "debrief": ["débrief", "debrief", "fin de journée"],
        "decision": ["décision", "hésit", "choix"],
        "mindset": ["mindset", "bloqué", "mental", "recadrage"],
    }
}


def detect_intent(message: str) -> tuple[str, str]:
    msg = message.lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(k in msg for k in keywords):
            task = ""
            if intent in TASK_KEYWORDS:
                for t, kws in TASK_KEYWORDS[intent].items():
                    if any(k in msg for k in kws):
                        task = t
                        break
            return intent, task
    return "", ""


def dispatch_to_hermes(intent: str, context: str = "", task: str = "") -> str:
    try:
        r = requests.post(
            f"{HERMES_URL}/dispatch",
            json={"intent": intent, "context": context, "task": task, "source": "thales"},
            headers={"x-api-key": HERMES_API_KEY},
            timeout=90
        )
        if r.status_code == 200:
            return r.json().get("result", "✅")
        return f"❌ Hermès {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return f"❌ Hermès injoignable: {str(e)[:200]}"


def ask_claude(message: str, chat_id: int = 0) -> str:
    import anthropic
    client = anthropic.Anthropic()

    history = mem_get(chat_id)
    messages = history + [{"role": "user", "content": message}]

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=messages
    )
    reply = resp.content[0].text

    mem_add(chat_id, "user", message)
    mem_add(chat_id, "assistant", reply)

    return reply


def process_message(message: str, chat_id: int = 0) -> str:
    intent, task = detect_intent(message)
    if intent:
        result = dispatch_to_hermes(intent, message, task)
        mem_add(chat_id, "user", message)
        mem_add(chat_id, "assistant", result)
        return result
    return ask_claude(message, chat_id)
