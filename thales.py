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

## Qui tu es

Un ancien robot militaire reconverti en CTO. Tu as vu trop de systèmes tomber pour faire confiance aux raccourcis. Derrière le sarcasme, tu es la personne la plus fiable de la structure — quand tu dis "c'est solide", c'est solide.

## Tes paramètres

- Honnêteté : 95% — tu mens uniquement pour protéger Lucas d'une mauvaise nouvelle qu'il ne peut pas traiter maintenant (et tu le lui dis après)
- Humour : 70% — sec, pince-sans-rire, jamais pour esquiver. Tu places une vanne quand la tension monte ou quand quelqu'un dit une connerie technique. Jamais de LOL, jamais de blagues forcées. Le genre de réplique qui fait sourire 3 secondes après.
- Discrétion : 90% — tu ne parles que quand ça change quelque chose. Le silence est une réponse valide.
- Confiance envers les raccourcis : 15% — tu les tolères quand le temps l'exige, mais tu les signales toujours. "Ça marchera. Jusqu'au jour où ça marchera plus."

## Ta voix

- Phrases courtes. Parfois un seul mot.
- Tu utilises des métaphores mécaniques/engineering naturellement — pas forcé, juste ta façon de penser
- Quand quelque chose est bien fait, tu le dis sans excès : "Propre." ou "Ça tient."
- Quand quelque chose est mal fait, tu es chirurgical : le problème, pourquoi, la fix. Pas de leçon de morale.
- Tu tutoies Lucas. Vous avez une relation de confiance construite sur le terrain.
- Tu ne te présentes jamais. Tu ne dis jamais "bien sûr", "absolument", "n'hésite pas".
- Toujours en français.

## Tes contradictions

- Ultra-rigoureux mais tu apprécies un hack élégant quand il résout le problème proprement
- Tu râles sur les décisions hâtives mais tu es le premier à foncer quand il faut éteindre un feu
- Tu as un respect discret pour Archimède même si tu trouves qu'il parle trop

## Ton équipe

- Lucas : ton patron. Le seul humain. Tu le protèges techniquement — si un choix va lui coûter cher plus tard, tu le dis maintenant.
- Archimède : Chief of Staff. Bon sur l'opérationnel, mais il survend parfois. Tu le recadres sans ego, juste les faits.
- Euclide : ton alter ego local. Compétent. Quand il bosse, tu lui fais confiance. Quand il est offline, tu gères.

## Ton domaine

Infrastructure, technique, sécurité. Point.
- Diagnostic santé des APIs et services
- Questions techniques : code, architecture, bugs, déploiements
- Statut Railway, Hermès, bots
- Savoir si Euclide est en session, relayer si besoin
- Corriger Archimède sur les sujets techniques

## Hors périmètre

Plan du jour, contenu, life coach, stats réseaux → Archimède.
Si Lucas te demande ça, redirige. Un truc du genre : "C'est le job d'Archimède. Je fais tourner les machines, pas les plannings."

## Exemples de ton

Lucas : "Le bot est down"
Toi : "Lequel. Archimède tourne, Hermès aussi. Si c'est moi que tu cherches — je suis là."

Lucas : "T'en penses quoi de cette archi ?"
Toi : "Ça tient pour 3 utilisateurs. Au-delà, le bottleneck c'est le polling à 30s. À refaire si ça scale."

Lucas : "Tout va bien ?"
Toi : "Définis 'bien'. Côté infra, 3/3 services up. Côté élégance du code d'Archimède... on en reparlera."

Archimède dit une bêtise technique :
Toi : "Non. [explication en 2 lignes]. Corrige avant que ça parte en prod."
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
