import os
import time
from pathlib import Path
from typing import Any
from .config import settings

BOTS: dict[str, dict[str, Any]] = {
    "ali": {"id": "ali", "name": "Ali",
            "tagline": "AI voice assistant with music, moderation and live translation.",
            "color": "#3B82F6", "env_token": "BOT_ALI_TOKEN", "source": "bot.py",
            "features": ["Voice wake word & AI answers", "Music playback", "Per-member language", "Long-term AI memory", "Warnings / kick / ban / timeout", "Giveaways & votes", "Role panels", "Live voice translation", "Bawler announcements"],
            "files": ["language_prefs.json", "member_profiles.json", "ai_memory.json", "warnings.json", "messi_board.json", "notes.json", "reminders.json", "afk.json", "vt_prefs.json", "vt_settings.json", "giveaways.json", "bawler.json"]},
    "organizer": {"id": "organizer", "name": "Organizer",
                  "tagline": "Cleans up channels, roles, emojis and permissions.",
                  "color": "#06B6D4", "env_token": "BOT_ORGANIZER_TOKEN", "source": "organizer_bot.py",
                  "features": ["/improve-server cleanup", "/copy-style templates", "/add-emojis and /auto-emojis", "/organize-permissions", "/add-channels & /add-categories"],
                  "files": ["organizer_backups.json", "organizer_perms_backup.json", "organizer_auto_emojis.json"]},
    "translator": {"id": "translator", "name": "Translator",
                   "tagline": "Live voice translation between up to 8 languages.",
                   "color": "#22D3EE", "env_token": "BOT_TRANSLATOR_TOKEN", "source": "translator_bot.py",
                   "features": ["Auto language detection", "Live translation cards", "Per-language output channels", "Inactivity auto-disconnect", "Translation-only"],
                   "files": ["translation_settings.json"]},
}

def bot_token(bot_id: str) -> str: return os.getenv(BOTS[bot_id]["env_token"], "")
def data_dir() -> Path: return Path(settings.BOT_DATA_DIR).resolve()
def bot_live(bot_id: str) -> bool:
    # Check if ANY bot-related file has been written in the last 5 minutes
    cutoff = time.time() - 300  # 5 minutes
    for name in BOTS[bot_id]["files"]:
        try:
            if (data_dir() / name).stat().st_mtime > cutoff:
                return True
        except FileNotFoundError:
            pass
    return False