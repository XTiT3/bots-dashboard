from contextlib import asynccontextmanager
import os
import traceback
import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from .auth import (cookie_name, exchange_code, fetch_me, fetch_my_guilds, oauth_login_url, require_user, sign_session, upsert_user)
from .bot_registry import BOTS, bot_live, bot_token, data_dir
from .config import settings
from .db import AuditLog, User, get_session, init_db
from .discord_api import bot_guilds, bot_invite_url, bot_user
from .json_store import bot_file_list, read_bot_file, write_bot_file

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(); yield

app = FastAPI(title="Discord Bots Dashboard API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[settings.FRONTEND_URL], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.exception_handler(Exception)
async def all_errors(request: Request, exc: Exception):
    tb = traceback.format_exc()
    print("="*60)
    print("ERROR on", request.url.path)
    print(tb)
    print("="*60)
    return JSONResponse(status_code=500, content={"error": str(exc), "traceback": tb.splitlines()[-5:]})

@app.get("/api/health")
def health(): return {"ok": True, "data_dir": str(data_dir()), "secret_set": bool(settings.DISCORD_CLIENT_SECRET)}

@app.get("/api/auth/login")
def auth_login(): return RedirectResponse(oauth_login_url())

@app.get("/api/auth/callback")
async def auth_callback(code: str):
    try:
        payload = await exchange_code(code)
        me = await fetch_me(payload["access_token"])
        user = upsert_user(payload, me)
        redirect = RedirectResponse(settings.FRONTEND_URL)
        redirect.set_cookie(cookie_name(), sign_session(user.id), httponly=True, samesite="lax", secure=False, max_age=60*60*24*30)
        return redirect
    except Exception as e:
        print("CALLBACK ERROR:", traceback.format_exc())
        return JSONResponse(status_code=500, content={"callback_error": str(e), "type": type(e).__name__})

@app.post("/api/auth/logout")
def auth_logout(response: Response):
    response.delete_cookie(cookie_name()); return {"ok": True}

@app.get("/api/me")
def get_me(user: User = Depends(require_user)): return {"id": user.discord_id, "username": user.username, "avatar": user.avatar}

@app.get("/api/guilds")
async def get_guilds(user: User = Depends(require_user)):
    try: guilds = await fetch_my_guilds(user.access_token)
    except httpx.HTTPError: return []
    out = []
    for g in guilds:
        perms = int(g.get("permissions", 0))
        if perms & 0x8 or perms & 0x20 or g.get("owner"):
            out.append({"id": g["id"], "name": g["name"], "icon": g.get("icon"), "owner": g.get("owner", False), "admin": bool(perms & 0x8), "manage": bool(perms & 0x20)})
    return out

async def _user_can_manage(user: User, guild_id: str) -> bool:
    try: guilds = await fetch_my_guilds(user.access_token)
    except httpx.HTTPError: return False
    for g in guilds:
        if g["id"] == guild_id:
            p = int(g.get("permissions", 0)); return bool(g.get("owner") or (p & 0x8) or (p & 0x20))
    return False

@app.get("/api/bots")
async def list_bots():
    out = []
    for bot_id, entry in BOTS.items():
        token = bot_token(bot_id); me = await bot_user(token) if token else None
        out.append({"id": bot_id, "name": entry["name"], "tagline": entry["tagline"], "color": entry["color"], "features": entry["features"], "configured": bool(token), "online": bool(me), "live": bot_live(bot_id), "discord_id": me["id"] if me else None, "avatar": me.get("avatar") if me else None, "invite": await bot_invite_url(me["id"]) if me else None})
    return out

@app.get("/api/bots/{bot_id}")
async def get_bot(bot_id: str):
    entry = BOTS.get(bot_id)
    if entry is None: raise HTTPException(status_code=404, detail="Unknown bot")
    token = bot_token(bot_id); me = await bot_user(token) if token else None; guilds = await bot_guilds(token) if token else []
    return {"id": bot_id, "name": entry["name"], "tagline": entry["tagline"], "color": entry["color"], "features": entry["features"], "files": bot_file_list(bot_id), "configured": bool(token), "online": bool(me), "live": bot_live(bot_id), "discord_id": me["id"] if me else None, "avatar": me.get("avatar") if me else None, "invite": await bot_invite_url(me["id"]) if me else None, "guilds": [{"id": g["id"], "name": g["name"]} for g in guilds]}

@app.get("/api/bots/{bot_id}/files")
def list_files(bot_id: str, user: User = Depends(require_user)): return bot_file_list(bot_id)

@app.get("/api/bots/{bot_id}/files/{name}")
def get_file(bot_id: str, name: str, user: User = Depends(require_user)): return read_bot_file(bot_id, name)

@app.put("/api/bots/{bot_id}/files/{name}")
def put_file(bot_id: str, name: str, payload: dict, user: User = Depends(require_user), session: Session = Depends(get_session)):
    write_bot_file(bot_id, name, payload)
    session.add(AuditLog(user_id=user.id, guild_id="*", bot_id=bot_id, action="write_file", details=name))
    session.commit(); return {"ok": True}

@app.get("/api/guilds/{guild_id}/bots")
async def bots_in_guild(guild_id: str, user: User = Depends(require_user)):
    if not await _user_can_manage(user, guild_id): raise HTTPException(status_code=403, detail="You cannot manage this guild")
    out = []
    for bot_id, entry in BOTS.items():
        token = bot_token(bot_id); guilds = await bot_guilds(token) if token else []
        present = any(str(g["id"]) == guild_id for g in guilds)
        out.append({"id": bot_id, "name": entry["name"], "color": entry["color"], "present": present, "live": bot_live(bot_id)})
    return out

# ---- Serve the React frontend ----
_FRONTEND_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
if os.path.isdir(_FRONTEND_DIST):
    _assets = os.path.join(_FRONTEND_DIST, "assets")
    if os.path.isdir(_assets):
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        fp = os.path.join(_FRONTEND_DIST, full_path)
        if full_path and os.path.isfile(fp):
            return FileResponse(fp)
        return FileResponse(os.path.join(_FRONTEND_DIST, "index.html"))