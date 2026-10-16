const API = import.meta.env.VITE_API_URL ?? "";
async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, { credentials: "include", headers: { "Content-Type": "application/json" }, ...init });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}
export const api = {
  me: () => jsonFetch<{ id: string; username: string; avatar?: string }>("/api/me"),
  login: () => { window.location.href = `${API}/api/auth/login`; },
  logout: () => jsonFetch<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
  bots: () => jsonFetch<BotSummary[]>("/api/bots"),
  bot: (id: string) => jsonFetch<BotDetail>(`/api/bots/${id}`),
  botFiles: (id: string) => jsonFetch<BotFile[]>(`/api/bots/${id}/files`),
  readBotFile: (id: string, name: string) => jsonFetch<unknown>(`/api/bots/${id}/files/${encodeURIComponent(name)}`),
  writeBotFile: (id: string, name: string, data: unknown) => jsonFetch<{ ok: boolean }>(`/api/bots/${id}/files/${encodeURIComponent(name)}`, { method: "PUT", body: JSON.stringify(data) }),
  guilds: () => jsonFetch<Guild[]>("/api/guilds"),
  guildBots: (gid: string) => jsonFetch<{ id: string; name: string; color: string; present: boolean; live: boolean }[]>(`/api/guilds/${gid}/bots`),
};
export interface BotSummary { id: string; name: string; tagline: string; color: string; features: string[]; configured: boolean; online: boolean; live: boolean; discord_id?: string; avatar?: string | null; invite?: string | null; }
export interface BotDetail extends BotSummary { files: BotFile[]; guilds: { id: string; name: string }[]; }
export interface BotFile { name: string; size: number; modified: number | null; }
export interface Guild { id: string; name: string; icon?: string | null; owner: boolean; admin: boolean; manage: boolean; }
