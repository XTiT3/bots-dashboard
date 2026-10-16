import json
import os
from pathlib import Path
from typing import Any
from fastapi import HTTPException
from .bot_registry import BOTS, data_dir

def _safe_path(name: str) -> Path:
    base = data_dir()
    p = (base / name).resolve()
    if base not in p.parents and p.parent != base: raise HTTPException(status_code=400, detail="Invalid file path")
    if not name.endswith(".json"): raise HTTPException(status_code=400, detail="Only JSON files are editable")
    return p

def bot_file_list(bot_id: str) -> list[dict[str, Any]]:
    entry = BOTS.get(bot_id)
    if entry is None: raise HTTPException(status_code=404, detail="Unknown bot")
    out = []
    for name in entry["files"]:
        p = _safe_path(name)
        if p.exists():
            st = p.stat(); out.append({"name": name, "size": st.st_size, "modified": st.st_mtime})
        else: out.append({"name": name, "size": 0, "modified": None})
    return out

def read_bot_file(bot_id: str, name: str) -> Any:
    entry = BOTS.get(bot_id)
    if entry is None or name not in entry["files"]: raise HTTPException(status_code=404, detail="File not managed by this bot")
    p = _safe_path(name)
    if not p.exists(): return {}
    try:
        with p.open("r", encoding="utf-8") as f: return json.load(f)
    except (json.JSONDecodeError, OSError): return {}

def write_bot_file(bot_id: str, name: str, data: Any) -> None:
    entry = BOTS.get(bot_id)
    if entry is None or name not in entry["files"]: raise HTTPException(status_code=404, detail="File not managed by this bot")
    p = _safe_path(name); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)
