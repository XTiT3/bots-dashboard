import datetime as dt
import secrets
from typing import Optional
import httpx
from fastapi import HTTPException, Request
from sqlmodel import Session, select
from .config import settings
from .db import User, engine

DISCORD_API = "https://discord.com/api/v10"
SCOPES = "identify guilds"

def cookie_name() -> str: return "dashboard_session"
def sign_session(user_id: int) -> str:
    from itsdangerous import URLSafeTimedSerializer
    return URLSafeTimedSerializer(settings.SESSION_SECRET, salt="session").dumps({"uid": user_id})
def read_session(value: str) -> Optional[int]:
    from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
    try:
        data = URLSafeTimedSerializer(settings.SESSION_SECRET, salt="session").loads(value, max_age=60*60*24*30)
        return int(data.get("uid"))
    except (BadSignature, SignatureExpired, TypeError, ValueError): return None
def oauth_login_url() -> str:
    state = secrets.token_urlsafe(16)
    return ("https://discord.com/oauth2/authorize"
            f"?client_id={settings.DISCORD_CLIENT_ID}"
            f"&redirect_uri={settings.DISCORD_REDIRECT_URI}"
            f"&response_type=code&scope={SCOPES.replace(' ', '%20')}"
            f"&state={state}&prompt=consent")
async def exchange_code(code: str) -> dict:
    data = {"client_id": settings.DISCORD_CLIENT_ID, "client_secret": settings.DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code", "code": code, "redirect_uri": settings.DISCORD_REDIRECT_URI}
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{DISCORD_API}/oauth2/token", data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        r.raise_for_status()
        return r.json()
async def fetch_me(token: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{DISCORD_API}/users/@me", headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        return r.json()
async def fetch_my_guilds(token: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{DISCORD_API}/users/@me/guilds", headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        return r.json()
def upsert_user(token_payload: dict, me: dict) -> User:
    expires = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=int(token_payload.get("expires_in", 604800)))
    with Session(engine) as s:
        existing = s.exec(select(User).where(User.discord_id == me["id"])).first()
        if existing is None:
            existing = User(discord_id=me["id"], username=me.get("global_name") or me["username"], avatar=me.get("avatar"),
                            access_token=token_payload["access_token"], refresh_token=token_payload.get("refresh_token", ""), token_expires_at=expires)
            s.add(existing)
        else:
            existing.username = me.get("global_name") or me["username"]
            existing.avatar = me.get("avatar")
            existing.access_token = token_payload["access_token"]
            existing.refresh_token = token_payload.get("refresh_token", existing.refresh_token)
            existing.token_expires_at = expires
            s.add(existing)
        s.commit(); s.refresh(existing); return existing
def current_user(request: Request) -> Optional[User]:
    token = request.cookies.get(cookie_name())
    if not token: return None
    uid = read_session(token)
    if uid is None: return None
    with Session(engine) as s: return s.get(User, uid)
def require_user(request: Request) -> User:
    u = current_user(request)
    if u is None: raise HTTPException(status_code=401, detail="Not authenticated")
    return u
