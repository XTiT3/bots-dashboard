from typing import Optional
import httpx

DISCORD_API = "https://discord.com/api/v10"

async def bot_user(token: str) -> Optional[dict]:
    if not token: return None
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{DISCORD_API}/users/@me", headers={"Authorization": f"Bot {token}"})
            return r.json() if r.status_code == 200 else None
    except httpx.HTTPError: return None

async def bot_guilds(token: str) -> list[dict]:
    if not token: return []
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{DISCORD_API}/users/@me/guilds", headers={"Authorization": f"Bot {token}"})
            return r.json() if r.status_code == 200 else []
    except httpx.HTTPError: return []

async def bot_invite_url(client_id: str) -> str:
    return f"https://discord.com/oauth2/authorize?client_id={client_id}&scope=bot%20applications.commands&permissions=8"
