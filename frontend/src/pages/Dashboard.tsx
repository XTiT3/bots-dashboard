import useSWR from "swr";
import { api, type BotSummary, type Guild } from "../api";
import BotCard from "../components/BotCard";
import { Link } from "react-router-dom";
export default function Dashboard() {
  const { data: bots } = useSWR<BotSummary[]>("bots", api.bots, { refreshInterval: 8000 });
  const { data: guilds } = useSWR<Guild[]>("guilds", api.guilds);
  return (
    <div className="space-y-10">
      <header><h1 className="text-3xl font-semibold">Overview</h1><p className="text-slate-400 mt-1">Live status of your three bots and quick access to every management screen.</p></header>
      <section>
        <h2 className="text-lg font-medium mb-3">Bots</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {(bots ?? []).map((b) => <BotCard key={b.id} bot={b} />)}
          {!bots && <div className="text-slate-500">Loading…</div>}
        </div>
      </section>
      <section>
        <h2 className="text-lg font-medium mb-3">Your servers</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {(guilds ?? []).map((g) => (
            <Link key={g.id} to={`/servers/${g.id}`} className="card p-4 flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-navy-800 grid place-items-center">
                {g.icon ? <img className="rounded-xl" src={`https://cdn.discordapp.com/icons/${g.id}/${g.icon}.png`} /> : <span className="text-sm">{g.name.slice(0, 1)}</span>}
              </div>
              <div className="min-w-0"><div className="font-medium truncate">{g.name}</div><div className="text-xs text-slate-400">{g.owner ? "Owner" : g.admin ? "Administrator" : g.manage ? "Manage Server" : "Member"}</div></div>
            </Link>
          ))}
          {guilds && guilds.length === 0 && (<div className="text-slate-500">No servers where you can manage bots.</div>)}
        </div>
      </section>
    </div>
  );
}
