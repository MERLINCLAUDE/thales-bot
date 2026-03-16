"""
Mémoire conversationnelle persistante par chat_id.
Stockage in-memory + backup JSON /tmp/thales_memory.json.
Survit aux restarts in-process, wiped au redeploy (acceptable V1).
"""

import json
import os
from collections import defaultdict
from datetime import datetime

MEMORY_FILE = "/tmp/thales_memory.json"
MAX_MESSAGES = 20  # messages par chat

_store: dict[str, list[dict]] = defaultdict(list)


def _load():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE) as f:
                data = json.load(f)
                for k, v in data.items():
                    _store[k] = v
        except Exception:
            pass


def _save():
    try:
        with open(MEMORY_FILE, "w") as f:
            json.dump(dict(_store), f)
    except Exception:
        pass


def add(chat_id: int | str, role: str, content: str, name: str = ""):
    """Ajoute un message à l'historique du chat."""
    key = str(chat_id)
    entry = {"role": role, "content": content}
    if name:
        entry["name"] = name
    _store[key].append(entry)
    # Fenêtre glissante
    if len(_store[key]) > MAX_MESSAGES:
        _store[key] = _store[key][-MAX_MESSAGES:]
    _save()


def get(chat_id: int | str) -> list[dict]:
    """Retourne l'historique formaté pour l'API Claude (alternance user/assistant)."""
    key = str(chat_id)
    history = _store.get(key, [])

    # Claude exige alternance user/assistant — on déduplique les consécutifs same-role
    cleaned = []
    for msg in history:
        if cleaned and cleaned[-1]["role"] == msg["role"]:
            # Fusionne les messages consécutifs de même rôle
            cleaned[-1]["content"] += f"\n{msg['content']}"
        else:
            cleaned.append({"role": msg["role"], "content": msg["content"]})
    return cleaned


def clear(chat_id: int | str):
    key = str(chat_id)
    _store.pop(key, None)
    _save()


# Charger au démarrage
_load()
