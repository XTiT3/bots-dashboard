from contextlib import asynccontextmanager
import os
import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from .auth import (cookie_name, exchange_code, fetch_me, fetch_my_guilds, oauth_login_url, require_user, sign_session, upsert_user, current_user)
from .bot_registry import BOTS, bot_live, bot_token, data_dir
from .config import settings
from .db import AuditLog, User, get_session, init_db
from .discord_api import bot_guilds, bot_invite_url, bot_user
from .json_store import bot_file_list, read_bot_file, write_bot_file
from .features import FEATURES, read_feature_flags, write_feature_flags

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(); yield

app = FastAPI(title="Bots Dashboard", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[settings.FRONTEND_URL], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/api/health")
def health(): return {"ok": True}

@app.get("/api/auth/login")
def auth_login(): return RedirectResponse(oauth_login_url())

@app.get("/api/auth/callback")
async def auth_callback(code: str):
    payload = await exchange_code(code)
    me = await fetch_me(payload["access_token"])
    user = upsert_user(payload, me)
    redirect = RedirectResponse("/")
    redirect.set_cookie(cookie_name(), sign_session(user.id), httponly=True, samesite="lax", secure=False, max_age=60*60*24*30)
    return redirect

@app.post("/api/auth/logout")
def auth_logout(response: Response):
    response.delete_cookie(cookie_name()); return {"ok": True}

@app.get("/api/auth/status")
def auth_status(request: Request):
    u = current_user(request)
    if u is None: return {"logged_in": False}
    avatar_url = f"https://cdn.discordapp.com/avatars/{u.discord_id}/{u.avatar}.png" if u.avatar else f"https://cdn.discordapp.com/embed/avatars/{(int(u.discord_id) >> 22) % 6}.png"
    return {"logged_in": True, "username": u.username, "id": u.discord_id, "avatar": avatar_url}

@app.get("/api/me")
def get_me(user: User = Depends(require_user)):
    return {"id": user.discord_id, "username": user.username, "avatar": user.avatar}

@app.get("/api/guilds")
async def get_guilds(user: User = Depends(require_user)):
    try: guilds = await fetch_my_guilds(user.access_token)
    except httpx.HTTPError: return []
    out = []
    for g in guilds:
        perms = int(g.get("permissions", 0))
        if perms & 0x8 or perms & 0x20 or g.get("owner"):
            icon = f"https://cdn.discordapp.com/icons/{g['id']}/{g['icon']}.png" if g.get("icon") else None
            out.append({"id": g["id"], "name": g["name"], "icon": icon, "owner": g.get("owner", False), "admin": bool(perms & 0x8), "manage": bool(perms & 0x20)})
    return out

@app.get("/api/guilds/{guild_id}/bots")
async def bots_in_guild(guild_id: str, user: User = Depends(require_user)):
    """Returns every bot with a present/online flag for this specific server."""
    out = []
    for bot_id, entry in BOTS.items():
        token = bot_token(bot_id)
        if not token:
            out.append({
                "id": bot_id, "name": entry["name"], "color": entry["color"],
                "tagline": entry["tagline"], "present": False, "online": False,
                "configured": False,
            })
            continue
        guilds = await bot_guilds(token)
        present = any(str(g["id"]) == guild_id for g in guilds)
        me = await bot_user(token)
        out.append({
            "id": bot_id, "name": entry["name"], "color": entry["color"],
            "tagline": entry["tagline"], "present": present,
            "online": bool(me) and present,
            "configured": True,
        })
    return {"id": guild_id, "bots": out}

@app.get("/api/bots")
async def list_bots():
    out = []
    for bot_id, entry in BOTS.items():
        token = bot_token(bot_id); me = await bot_user(token) if token else None
        out.append({"id": bot_id, "name": entry["name"], "tagline": entry["tagline"], "color": entry["color"], "features": entry["features"], "configured": bool(token), "online": bool(me), "live": bot_live(bot_id), "discord_id": me["id"] if me else None, "invite": await bot_invite_url(me["id"]) if me else None})
    return out

@app.get("/api/bots/{bot_id}")
async def get_bot(bot_id: str):
    entry = BOTS.get(bot_id)
    if entry is None: raise HTTPException(status_code=404, detail="Unknown bot")
    token = bot_token(bot_id); me = await bot_user(token) if token else None; guilds = await bot_guilds(token) if token else []
    return {"id": bot_id, "name": entry["name"], "tagline": entry["tagline"], "color": entry["color"], "features": entry["features"], "files": bot_file_list(bot_id), "configured": bool(token), "online": bool(me), "live": bot_live(bot_id), "discord_id": me["id"] if me else None, "invite": await bot_invite_url(me["id"]) if me else None, "guilds": [{"id": g["id"], "name": g["name"]} for g in guilds]}

@app.get("/api/bots/{bot_id}/files")
def list_files(bot_id: str, user: User = Depends(require_user)): return bot_file_list(bot_id)

@app.get("/api/bots/{bot_id}/files/{name}")
def get_file(bot_id: str, name: str, user: User = Depends(require_user)): return read_bot_file(bot_id, name)

@app.put("/api/bots/{bot_id}/files/{name}")
def put_file(bot_id: str, name: str, payload: dict, user: User = Depends(require_user), session: Session = Depends(get_session)):
    write_bot_file(bot_id, name, payload)
    session.add(AuditLog(user_id=user.id, guild_id="*", bot_id=bot_id, action="write_file", details=name))
    session.commit(); return {"ok": True}

@app.get("/api/bots/{bot_id}/features")
async def get_features(bot_id: str):
    if bot_id not in FEATURES: raise HTTPException(status_code=404, detail="Unknown bot")
    return {"features": FEATURES[bot_id], "enabled": read_feature_flags(bot_id)}

@app.put("/api/bots/{bot_id}/features")
def put_features(bot_id: str, payload: dict, user: User = Depends(require_user)):
    if bot_id not in FEATURES: raise HTTPException(status_code=404, detail="Unknown bot")
    write_feature_flags(bot_id, payload)
    return {"ok": True, "enabled": read_feature_flags(bot_id)}

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
<title>Bots Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=Instrument+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#10141b; --side:#0c1015; --surface:#171c25; --raised:#1e2430; --line:#2a313e; --line-soft:#212835;
  --text:#ebe8e2; --muted:#98a0ae; --faint:#677082;
  --accent:#a99bff; --accent-ink:#17122e; --accent-soft:rgba(169,155,255,.14);
  --ok:#62d394; --warn:#f0b955; --off:#6b7485; --bad:#ff8a8a;
  --head:'Bricolage Grotesque','Segoe UI',system-ui,sans-serif;
  --body:'Instrument Sans','Segoe UI',system-ui,-apple-system,sans-serif;
  --mono:'JetBrains Mono',ui-monospace,'SF Mono',Menlo,monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%}
body{font:15px/1.55 var(--body);background:var(--bg);color:var(--text);min-height:100vh}
a{color:inherit;text-decoration:none}
button{font:inherit;color:inherit;cursor:pointer;background:none;border:0}
.hidden{display:none!important}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:6px}
h1,h2,h3{font-family:var(--head);font-weight:700;letter-spacing:-.01em;line-height:1.15}

.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:10px 18px;border-radius:10px;font-weight:600;font-size:14px;border:1px solid transparent;transition:background .15s,border-color .15s}
.btn-primary{background:var(--accent);color:var(--accent-ink)}
.btn-primary:hover{background:#bcb1ff}
.btn-quiet{border-color:var(--line);color:var(--text)}
.btn-quiet:hover{background:var(--raised)}
.btn-discord{background:#5865f2;color:#fff;width:100%;padding:13px 18px;font-size:15px}
.btn-discord:hover{background:#6b77f5}

.login{min-height:100vh;display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr)}
.login-art{padding:56px;display:flex;flex-direction:column;justify-content:space-between;background:var(--side);border-right:1px solid var(--line-soft);position:relative;overflow:hidden}
.login-art h1{font-size:clamp(34px,4.4vw,56px);max-width:12ch}
.login-art p{color:var(--muted);max-width:38ch;margin-top:16px}
.login-art .rows{display:grid;gap:10px;max-width:360px}
.mini{display:flex;align-items:center;gap:12px;padding:12px 14px;background:var(--surface);border:1px solid var(--line-soft);border-radius:12px;font-size:13px;color:var(--muted)}
.mini b{color:var(--text);font-weight:600}
.mini .tile{width:30px;height:30px;font-size:14px;border-radius:8px}
.login-form{display:flex;align-items:center;justify-content:center;padding:40px}
.login-box{width:100%;max-width:360px}
.login-box h2{font-size:24px;margin-bottom:8px}
.login-box p{color:var(--muted);font-size:14px;margin-bottom:24px}
.login-box small{display:block;margin-top:16px;color:var(--faint);font-size:12.5px}
@media(max-width:800px){.login{grid-template-columns:1fr}.login-art{display:none}}

.mark{width:36px;height:36px;border-radius:10px;background:var(--accent);display:grid;place-items:center;flex-shrink:0}
.mark svg{width:20px;height:20px;color:var(--accent-ink)}

.app{display:grid;grid-template-columns:264px minmax(0,1fr);min-height:100vh}
.sidebar{background:var(--side);border-right:1px solid var(--line-soft);padding:20px 14px;display:flex;flex-direction:column;position:sticky;top:0;height:100vh}
.brand{display:flex;align-items:center;gap:12px;padding:4px 8px 20px}
.brand h2{font-size:16px}
.brand p{font-size:12px;color:var(--faint)}
.nav-title{padding:18px 10px 6px;font-size:12.5px;font-weight:600;color:var(--faint)}
.nav-item{display:flex;align-items:center;gap:10px;width:100%;text-align:left;padding:9px 10px;border-radius:9px;font-size:14px;color:var(--muted);transition:background .12s,color .12s}
.nav-item:hover{background:var(--surface);color:var(--text)}
.nav-item.active{background:var(--accent-soft);color:var(--text);font-weight:600}
.nav-item svg{width:16px;height:16px;flex-shrink:0}
.nav-scroll{overflow-y:auto;min-height:0}
.dot{width:8px;height:8px;border-radius:50%;background:var(--off);flex-shrink:0}
.dot.live{background:var(--ok)}.dot.idle{background:var(--warn)}
.srv-ic{width:20px;height:20px;border-radius:6px;background:var(--raised);display:grid;place-items:center;font-size:10px;font-weight:600;color:var(--muted);flex-shrink:0;overflow:hidden}
.srv-ic img{width:100%;height:100%;object-fit:cover}
.who{margin-top:auto;padding:14px 8px 0;border-top:1px solid var(--line-soft);display:flex;align-items:center;gap:10px}
.who img{width:34px;height:34px;border-radius:50%;background:var(--raised)}
.who .n{font-size:13.5px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.who .s{font-size:12px;color:var(--faint)}
.who>div{flex:1;min-width:0}
.icon-btn{padding:8px;border-radius:8px;color:var(--muted)}
.icon-btn:hover{background:var(--surface);color:var(--text)}
.icon-btn svg{width:18px;height:18px;display:block}

.main{padding:44px clamp(20px,4.5vw,64px) 80px;min-width:0;max-width:1200px;width:100%}
.page-head{margin-bottom:32px}
.page-head h1{font-size:34px;margin-bottom:8px}
.page-head p{color:var(--muted)}

.status{display:inline-flex;align-items:center;gap:7px;font-size:13px;font-weight:500;color:var(--muted)}
.status.live{color:var(--ok)}.status.idle{color:var(--warn)}.status.off{color:var(--faint)}

.tile{width:48px;height:48px;border-radius:13px;display:grid;place-items:center;font:700 21px var(--head);color:#fff;flex-shrink:0;text-shadow:0 1px 2px rgba(0,0,0,.25)}

.bot-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:18px}
.bot-card{background:var(--surface);border:1px solid var(--line-soft);border-radius:16px;padding:22px;display:flex;flex-direction:column;gap:18px;text-align:left;transition:border-color .15s,background .15s}
.bot-card:hover{border-color:var(--line);background:#1a202a}
.bot-head{display:flex;gap:14px;align-items:center}
.bot-name{font:700 19px var(--head);margin-bottom:2px}
.bot-tag{color:var(--muted);font-size:14px;margin-top:2px}
.feat-tags{display:flex;flex-wrap:wrap;gap:6px}
.chip{padding:3px 10px;border-radius:999px;background:var(--raised);font-size:12.5px;color:var(--muted)}
.card-btns{display:flex;gap:8px;margin-top:auto}
.card-btns .btn{flex:1}
.empty{padding:40px;border:1px dashed var(--line);border-radius:16px;color:var(--muted);text-align:center}

/* server detail: bot presence rows */
.pres-row{display:flex;align-items:center;gap:16px;padding:16px 0;border-top:1px solid var(--line-soft)}
.pres-row:first-child{border-top:0}
.pres-row .tile{width:44px;height:44px;font-size:19px;border-radius:12px}
.pres-info{flex:1;min-width:0}
.pres-name{font:700 16px var(--head);margin-bottom:2px}
.pres-tag{color:var(--muted);font-size:13.5px}
.pres-badge{padding:5px 12px;border-radius:999px;font-size:12.5px;font-weight:600;white-space:nowrap}
.pres-badge.on{background:rgba(98,211,148,.15);color:var(--ok)}
.pres-badge.off{background:rgba(107,116,133,.2);color:var(--faint)}
.pres-badge.none{background:rgba(255,138,138,.12);color:var(--bad)}

.back{display:inline-flex;align-items:center;gap:6px;color:var(--muted);font-size:14px;padding:6px 10px 6px 6px;margin:-6px 0 20px -6px;border-radius:8px}
.back:hover{color:var(--text);background:var(--surface)}
.back svg{width:16px;height:16px}
.detail-head{display:flex;align-items:center;gap:18px;margin-bottom:32px;flex-wrap:wrap}
.detail-head .tile{width:64px;height:64px;font-size:28px;border-radius:17px}
.detail-head h1{font-size:30px;margin-bottom:4px}
.detail-head .grow{flex:1;min-width:200px}
.grid-2{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);gap:18px;margin-bottom:18px;align-items:start}
@media(max-width:900px){.grid-2{grid-template-columns:1fr}}
.card{background:var(--surface);border:1px solid var(--line-soft);border-radius:16px;padding:22px 24px}
.card h3{font-size:17px;margin-bottom:4px}
.card .sub{color:var(--muted);font-size:13.5px;margin-bottom:12px}
.feat-row{display:flex;justify-content:space-between;align-items:center;gap:20px;padding:14px 0;border-top:1px solid var(--line-soft)}
.feat-name{font-weight:600;font-size:14.5px}
.feat-desc{color:var(--muted);font-size:13.5px;margin-top:2px}
.switch{position:relative;width:44px;height:26px;border-radius:13px;background:var(--line);flex-shrink:0;transition:background .18s}
.switch::after{content:'';position:absolute;top:3px;left:3px;width:20px;height:20px;border-radius:50%;background:#fff;transition:transform .18s}
.switch[aria-checked=true]{background:var(--accent)}
.switch[aria-checked=true]::after{transform:translateX(18px);background:var(--accent-ink)}
.srv-list{list-style:none}
.srv-list li{display:flex;align-items:center;gap:10px;padding:11px 0;border-top:1px solid var(--line-soft);font-size:14px}
.muted-note{color:var(--faint);font-size:14px;padding:12px 0}

.tabs{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 14px}
.tab{padding:7px 13px;border-radius:8px;border:1px solid var(--line);font:13px var(--mono);color:var(--muted);transition:background .12s}
.tab:hover{background:var(--raised);color:var(--text)}
.tab.active{background:var(--accent-soft);border-color:var(--accent);color:var(--text)}
textarea{display:block;width:100%;height:400px;resize:vertical;background:#0b0e13;color:#d9dce3;border:1px solid var(--line);border-radius:12px;padding:16px;font:13px/1.7 var(--mono);tab-size:2}
textarea:focus{outline:none;border-color:var(--accent)}
textarea:disabled{opacity:.5}
.save-row{display:flex;align-items:center;gap:14px;margin-top:14px;flex-wrap:wrap}
.valid{font-size:13px;color:var(--faint)}
.valid.ok{color:var(--ok)}.valid.bad{color:var(--bad)}

.loader{display:flex;align-items:center;justify-content:center;gap:12px;padding:80px;color:var(--muted)}
.spinner{width:18px;height:18px;border:2px solid var(--line);border-top-color:var(--accent);border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.toast{position:fixed;right:24px;bottom:24px;padding:12px 18px;border-radius:12px;background:var(--raised);border:1px solid var(--line);font-size:14px;font-weight:500;box-shadow:0 12px 32px rgba(0,0,0,.4);transform:translateY(12px);opacity:0;pointer-events:none;transition:opacity .2s,transform .2s;z-index:50}
.toast.show{opacity:1;transform:none}
.toast.err{border-color:var(--bad);color:var(--bad)}

@media(max-width:820px){
  .app{grid-template-columns:1fr}
  .sidebar{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line-soft)}
  .nav-scroll{max-height:200px}
  .who{margin-top:16px}
  .main{padding-top:28px}
}
@media(prefers-reduced-motion:reduce){*{transition:none!important;animation-duration:.01ms!important}}
</style></head><body>

<div id="login" class="login hidden">
  <section class="login-art">
    <div class="brand"><div class="mark"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="8" width="16" height="11" rx="3"/><path d="M12 8V4M9 13h.01M15 13h.01"/></svg></div><div><h2>Bots Dashboard</h2></div></div>
    <div>
      <h1>Every bot, one control room.</h1>
      <p>Switch features on and off, edit config files, and see which servers each bot is running in.</p>
    </div>
    <div class="rows" aria-hidden="true">
      <div class="mini"><span class="tile" style="background:#e0736a">A</span><span><b>Features</b><br>Toggle without restarting</span></div>
      <div class="mini"><span class="tile" style="background:#4aa3a0">B</span><span><b>Config files</b><br>Edit JSON with validation</span></div>
    </div>
  </section>
  <section class="login-form">
    <div class="login-box">
      <h2>Sign in</h2>
      <p>Use the Discord account that manages your servers.</p>
      <a class="btn btn-discord" href="/api/auth/login">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M20.317 4.37a19.79 19.79 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/></svg>
        Continue with Discord
      </a>
      <small>We only read your username and server list. Your password stays with Discord.</small>
    </div>
  </section>
</div>

<div id="app" class="app hidden">
  <aside class="sidebar">
    <div class="brand"><div class="mark"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="8" width="16" height="11" rx="3"/><path d="M12 8V4M9 13h.01M15 13h.01"/></svg></div><div><h2>Bots Dashboard</h2><p>Control center</p></div></div>
    <button class="nav-item active" id="nav-overview" type="button"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>Overview</button>
    <div class="nav-title">Bots</div>
    <div id="nav-bots"></div>
    <div class="nav-title">Your servers</div>
    <div id="nav-servers" class="nav-scroll"></div>
    <div class="who">
      <img id="user-avatar" src="" alt="">
      <div><div class="n" id="user-name">—</div><div class="s">Signed in</div></div>
      <button class="icon-btn" id="logout" type="button" title="Sign out" aria-label="Sign out"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/></svg></button>
    </div>
  </aside>
  <main class="main" id="main"></main>
</div>
<div class="toast" id="toast" role="status" aria-live="polite"></div>

<script>
var state = { bots: [], servers: [], currentBot: null, currentFile: null };
var $ = function(id){ return document.getElementById(id); };
function esc(s){ return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
function statusOf(b){ return b.online ? ['live','Running'] : ['off','Offline']; }
function statusHtml(b){ var s = statusOf(b); return '<span class="status ' + s[0] + '"><span class="dot ' + s[0] + '"></span>' + s[1] + '</span>'; }
function tileHtml(b){ return '<div class="tile" style="background:' + esc(b.color) + '" aria-hidden="true">' + esc(b.name.charAt(0)) + '</div>'; }
var toastTimer;
function toast(msg, err){ var t = $('toast'); t.textContent = msg; t.className = 'toast show' + (err ? ' err' : ''); clearTimeout(toastTimer); toastTimer = setTimeout(function(){ t.className = 'toast'; }, 2600); }

async function boot() {
  var r = await fetch('/api/auth/status'); var d = await r.json();
  if (!d.logged_in) { $('login').classList.remove('hidden'); return; }
  $('app').classList.remove('hidden');
  $('user-name').textContent = d.username; $('user-avatar').src = d.avatar;
  var res = await Promise.all([
    fetch('/api/bots').then(function(r){ return r.json(); }),
    fetch('/api/guilds').then(function(r){ return r.json(); }).catch(function(){ return []; })
  ]);
  state.bots = res[0]; state.servers = res[1];
  $('nav-overview').onclick = showOverview; $('logout').onclick = logout;
  renderBotNav(); renderServerNav(); showOverview();
}

function renderBotNav() {
  var el = $('nav-bots'); el.innerHTML = '';
  state.bots.forEach(function(b) {
    var a = document.createElement('button'); a.type = 'button'; a.className = 'nav-item'; a.id = 'nav-bot-' + b.id;
    a.innerHTML = '<span class="dot ' + statusOf(b)[0] + '"></span>' + esc(b.name);
    a.onclick = function(){ openBot(b.id); }; el.appendChild(a);
  });
}
function renderServerNav() {
  var el = $('nav-servers'); el.innerHTML = '';
  if (!state.servers.length) { el.innerHTML = '<div class="muted-note" style="padding:6px 10px;font-size:13px">No servers you manage</div>'; return; }
  state.servers.forEach(function(s) {
    var d = document.createElement('button'); d.type = 'button'; d.className = 'nav-item'; d.id = 'nav-srv-' + s.id;
    d.innerHTML = '<span class="srv-ic">' + (s.icon ? '<img alt="" src="' + esc(s.icon) + '">' : esc(s.name.charAt(0))) + '</span><span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(s.name) + '</span>';
    d.onclick = function(){ showServer(s.id, s.name, s.icon); };
    el.appendChild(d);
  });
}
function clearActive(){ document.querySelectorAll('.nav-item').forEach(function(e){ e.classList.remove('active'); }); }
function showLoading(){ $('main').innerHTML = '<div class="loader"><div class="spinner"></div>Loading…</div>'; }

function showOverview() {
  clearActive(); $('nav-overview').classList.add('active'); state.currentBot = null;
  var live = state.bots.filter(function(b){ return b.online; }).length;
  $('main').innerHTML = '<div class="page-head"><h1>Overview</h1><p>' + (state.bots.length ? live + ' of ' + state.bots.length + ' bots running. Pick one to change its features or config.' : 'No bots are registered yet.') + '</p></div><div class="bot-grid" id="bot-grid"></div>';
  var grid = $('bot-grid');
  if (!state.bots.length) { grid.outerHTML = '<div class="empty">Add a bot to bot_registry.py and it will show up here.</div>'; return; }
  state.bots.forEach(function(b) {
    var card = document.createElement('div'); card.className = 'bot-card';
    card.innerHTML =
      '<div class="bot-head">' + tileHtml(b) + '<div><div class="bot-name">' + esc(b.name) + '</div>' + statusHtml(b) + '</div></div>' +
      '<div class="bot-tag" style="margin:-6px 0 0">' + esc(b.tagline) + '</div>' +
      '<div class="feat-tags">' + b.features.slice(0, 4).map(function(f){ return '<span class="chip">' + esc(f) + '</span>'; }).join('') + '</div>' +
      '<div class="card-btns"><button class="btn btn-primary" type="button">Manage</button>' +
      (b.invite ? '<a class="btn btn-quiet" href="' + esc(b.invite) + '" target="_blank" rel="noopener">Add to server</a>' : '') + '</div>';
    card.querySelector('button').onclick = function(){ openBot(b.id); };
    grid.appendChild(card);
  });
}

/* ---- Server detail: shows every bot for this server ---- */
async function showServer(id, name, icon) {
  clearActive();
  var nav = $('nav-srv-' + id); if (nav) nav.classList.add('active');
  state.currentBot = null; showLoading();
  var data = await fetch('/api/guilds/' + id + '/bots').then(function(r){ return r.json(); });
  var bots = data.bots || [];
  var present = bots.filter(function(b){ return b.present; });
  var online = bots.filter(function(b){ return b.online; });

  var subtitle;
  if (present.length === 0) {
    subtitle = 'No bots are in this server yet. Use “Add to server” below to invite one.';
  } else {
    subtitle = online.length + ' of ' + present.length + ' bot' + (present.length === 1 ? '' : 's') + ' running in this server.';
  }

  var rowsHtml = bots.map(function(b) {
    var badge, badgeClass;
    if (!b.configured) { badge = 'Not configured'; badgeClass = 'none'; }
    else if (b.online) { badge = 'Running'; badgeClass = 'on'; }
    else if (b.present) { badge = 'In server · offline'; badgeClass = 'off'; }
    else { badge = 'Not in server'; badgeClass = 'none'; }
    var action = b.present
      ? '<span class="pres-badge ' + badgeClass + '">' + badge + '</span>'
      : (b.invite ? '<a class="btn btn-primary" style="padding:8px 14px;font-size:13px" href="' + esc(b.invite) + '" target="_blank" rel="noopener">Add to server</a>' : '<span class="pres-badge ' + badgeClass + '">' + badge + '</span>');
    return '<div class="pres-row">' + tileHtml(b) +
      '<div class="pres-info"><div class="pres-name">' + esc(b.name) + '</div>' +
      '<div class="pres-tag">' + esc(b.tagline) + '</div></div>' +
      action + '</div>';
  }).join('');

  var iconHtml = icon ? '<img src="' + esc(icon) + '" alt="" style="width:64px;height:64px;border-radius:17px">' :
                        '<div class="tile" style="width:64px;height:64px;font-size:28px;border-radius:17px;background:var(--raised)">' + esc(name.charAt(0)) + '</div>';

  $('main').innerHTML =
    '<button class="back" type="button" id="back"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>Overview</button>' +
    '<div class="detail-head">' + iconHtml +
      '<div class="grow"><h1>' + esc(name) + '</h1><p style="color:var(--muted);margin-bottom:8px">' + esc(subtitle) + '</p></div></div>' +
    '<section class="card"><h3>Bots for this server</h3><p class="sub">See which bots are installed, running, or missing.</p><div id="pres-list">' + rowsHtml + '</div></section>';

  $('back').onclick = showOverview;
}

async function openBot(id) {
  clearActive(); var nav = $('nav-bot-' + id); if (nav) nav.classList.add('active');
  state.currentBot = id; state.currentFile = null; showLoading();
  var res = await Promise.all([
    fetch('/api/bots/' + id).then(function(r){ return r.json(); }),
    fetch('/api/bots/' + id + '/features').then(function(r){ return r.json(); }).catch(function(){ return { features: [], enabled: {} }; }),
    fetch('/api/bots/' + id + '/files').then(function(r){ return r.json(); }).catch(function(){ return []; })
  ]);
  var br = res[0], fr = res[1], flr = res[2];
  $('main').innerHTML =
    '<button class="back" type="button" id="back"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>Overview</button>' +
    '<div class="detail-head">' + tileHtml(br) + '<div class="grow"><h1>' + esc(br.name) + '</h1><p style="color:var(--muted);margin-bottom:8px">' + esc(br.tagline) + '</p>' + statusHtml(br) + '</div>' +
    (br.invite ? '<a class="btn btn-primary" href="' + esc(br.invite) + '" target="_blank" rel="noopener">Add to server</a>' : '') + '</div>' +
    '<div class="grid-2">' +
      '<section class="card"><h3>Features</h3><p class="sub">Changes save as soon as you flip a switch.</p><div id="feat-list"></div></section>' +
      '<section class="card"><h3>Servers</h3><p class="sub">' + (br.guilds.length ? 'Running in ' + br.guilds.length + (br.guilds.length === 1 ? ' server' : ' servers') : 'Not added anywhere yet') + '</p><ul class="srv-list" id="srv-list"></ul></section>' +
    '</div>' +
    '<section class="card"><h3>Config files</h3><p class="sub">Choose a file, edit the JSON, then save.</p><div class="tabs" id="tabs"></div>' +
      '<textarea id="editor" spellcheck="false" disabled placeholder="Select a file to edit it."></textarea>' +
      '<div class="save-row"><button class="btn btn-primary" type="button" id="save">Save changes</button><span class="valid" id="valid"></span></div></section>';
  $('back').onclick = showOverview;

  var fl = $('feat-list');
  if (!fr.features.length) fl.innerHTML = '<div class="muted-note">This bot has no switchable features.</div>';
  fr.features.forEach(function(f) {
    var row = document.createElement('div'); row.className = 'feat-row';
    row.innerHTML = '<div><div class="feat-name">' + esc(f.name) + '</div><div class="feat-desc">' + esc(f.desc) + '</div></div>' +
      '<button type="button" role="switch" class="switch" aria-label="' + esc(f.name) + '" aria-checked="' + (fr.enabled[f.id] ? 'true' : 'false') + '" data-id="' + esc(f.id) + '"></button>';
    fl.appendChild(row);
  });
  fl.querySelectorAll('.switch').forEach(function(t) {
    t.onclick = async function() {
      var was = t.getAttribute('aria-checked') === 'true';
      t.setAttribute('aria-checked', String(!was));
      var all = {}; fl.querySelectorAll('.switch').forEach(function(x){ all[x.getAttribute('data-id')] = x.getAttribute('aria-checked') === 'true'; });
      try {
        var r = await fetch('/api/bots/' + id + '/features', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(all) });
        if (!r.ok) throw new Error(r.status);
        toast('Feature saved');
      } catch (e) { t.setAttribute('aria-checked', String(was)); toast('Could not save feature', true); }
    };
  });

  var sl = $('srv-list');
  br.guilds.forEach(function(g){ var li = document.createElement('li'); li.innerHTML = '<span class="srv-ic">' + esc(g.name.charAt(0)) + '</span>' + esc(g.name); sl.appendChild(li); });
  if (!br.guilds.length) sl.innerHTML = '<li class="muted-note">Use “Add to server” to invite this bot.</li>';

  var tabs = $('tabs');
  if (!flr.length) tabs.innerHTML = '<div class="muted-note">No config files found.</div>';
  flr.forEach(function(f){ var b = document.createElement('button'); b.type = 'button'; b.className = 'tab'; b.textContent = f.name; b.onclick = function(){ loadFile(id, f.name, b); }; tabs.appendChild(b); });
  $('save').onclick = saveFile;
  $('editor').addEventListener('input', checkJson);
  $('editor').addEventListener('keydown', function(e){ if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); saveFile(); } });
}

function checkJson() {
  var v = $('valid'), ed = $('editor');
  if (ed.disabled) { v.textContent = ''; return true; }
  try { JSON.parse(ed.value); v.className = 'valid ok'; v.textContent = 'Valid JSON'; return true; }
  catch (e) { v.className = 'valid bad'; v.textContent = e.message; return false; }
}

async function loadFile(botId, name, btn) {
  document.querySelectorAll('.tab').forEach(function(x){ x.classList.remove('active'); });
  btn.classList.add('active'); state.currentFile = name;
  var ed = $('editor'); ed.disabled = true; ed.value = 'Loading…';
  try {
    var data = await fetch('/api/bots/' + botId + '/files/' + name).then(function(r){ return r.json(); });
    ed.value = JSON.stringify(data, null, 2); ed.disabled = false; checkJson();
  } catch (e) { ed.value = ''; toast('Could not load ' + name, true); }
}

async function saveFile() {
  if (!state.currentBot || !state.currentFile) { toast('Choose a file first', true); return; }
  if (!checkJson()) { toast('Fix the JSON before saving', true); return; }
  try {
    var r = await fetch('/api/bots/' + state.currentBot + '/files/' + state.currentFile, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(JSON.parse($('editor').value)) });
    if (!r.ok) throw new Error(r.status);
    toast('Saved ' + state.currentFile);
  } catch (e) { toast('Could not save ' + state.currentFile, true); }
}

async function logout() { await fetch('/api/auth/logout', { method: 'POST' }); location.reload(); }
boot();
</script></body></html>"""

@app.get("/", response_class=HTMLResponse)
async def root():
    return INDEX_HTML

_FRONTEND_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
if os.path.isdir(_FRONTEND_DIST):
    _assets = os.path.join(_FRONTEND_DIST, "assets")
    if os.path.isdir(_assets):
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")