from pathlib import Path
from typing import Any
import json, os
from .config import settings

FEATURES = {
    "ali": [
        {"id": "voice_ai", "name": "Voice AI answers", "desc": "Answer questions spoken in voice channels"},
        {"id": "music", "name": "Music playback", "desc": "Play music in voice channels"},
        {"id": "wake_word", "name": "Wake word", "desc": "Listen for the name 'Ali'"},
        {"id": "memory", "name": "Long-term AI memory", "desc": "Remember members across sessions"},
        {"id": "moderation", "name": "Moderation", "desc": "Warnings, kick, ban, timeout"},
        {"id": "giveaways", "name": "Giveaways & votes", "desc": "Create giveaways and polls"},
        {"id": "role_panels", "name": "Role panels", "desc": "Self-assign role buttons"},
        {"id": "live_translation", "name": "Live voice translation", "desc": "Translate voice to text channels"},
        {"id": "bawler", "name": "Bawler announcements", "desc": "Daily scheduled announcements"},
        {"id": "greeting", "name": "Member greetings", "desc": "Welcome voice joiners"},
    ],
    "organizer": [
        {"id": "improve_server", "name": "Improve server", "desc": "/improve-server cleanup"},
        {"id": "copy_style", "name": "Copy style", "desc": "/copy-style templates"},
        {"id": "add_emojis", "name": "Add emojis", "desc": "/add-emojis and /auto-emojis"},
        {"id": "organize_permissions", "name": "Organize permissions", "desc": "/organize-permissions"},
        {"id": "add_channels", "name": "Add channels", "desc": "/add-channels and /add-categories"},
    ],
    "translator": [
        {"id": "live_translation", "name": "Live voice translation", "desc": "Translate voice to text"},
        {"id": "auto_detect", "name": "Auto language detection", "desc": "Detect spoken language automatically"},
        {"id": "multi_language", "name": "Multi-language", "desc": "Support up to 8 languages"},
        {"id": "auto_disconnect", "name": "Auto disconnect", "desc": "Leave empty channels automatically"},
    ],
}

def _flags_path() -> Path:
    return Path(settings.BOT_DATA_DIR) / "feature_flags.json"

def _load_all() -> dict:
    p = _flags_path()
    if not p.exists():
        return {}
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_all(data: dict) -> None:
    p = _flags_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)

def read_feature_flags(bot_id: str) -> dict:
    all_data = _load_all()
    bot_flags = all_data.get(bot_id, {})
    out = {}
    for f in FEATURES.get(bot_id, []):
        out[f["id"]] = bool(bot_flags.get(f["id"], True))
    return out

def write_feature_flags(bot_id: str, flags: dict) -> None:
    all_data = _load_all()
    allowed = {f["id"] for f in FEATURES.get(bot_id, [])}
    all_data[bot_id] = {k: bool(v) for k, v in flags.items() if k in allowed}
    _save_all(all_data)
