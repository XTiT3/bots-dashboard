import { Link, useParams } from "react-router-dom";
import useSWR from "swr";
import { ArrowLeft } from "lucide-react";
import { api } from "../api";
export default function ServerPage() {
  const { guildId = "" } = useParams();
  const { data: bots } = useSWR(["guildBots", guildId], () => api.guildBots(guildId));
  return (
    <div className="space-y-8">
      <Link to="/" className="text-slate-400 hover:text-white inline-flex items-center gap-2 text-sm"><ArrowLeft size={14} /> Back</Link>
      <header><h1 className="text-3xl font-semibold">Server control</h1><p className="text-slate-400 mt-1">Which bots are in this server and what you can manage.</p></header>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {(bots ?? []).map((b) => (
          <div key={b.id} className="card p-5">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl grid place-items-center text-white font-bold" style={{ background: `linear-gradient(135deg, ${b.color}, #22d3ee)` }}>{b.name.slice(0, 1)}</div>
              <div><div className="font-medium">{b.name}</div><div className="text-xs text-slate-400">{b.present ? (b.live ? "Present · live" : "Present") : "Not in this server"}</div></div>
            </div>
            <Link to={`/bots/${b.id}`} className="btn btn-primary mt-4 w-full justify-center">Open bot settings</Link>
          </div>
        ))}
      </div>
    </div>
  );
}
