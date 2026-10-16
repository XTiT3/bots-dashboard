import { Link } from "react-router-dom";
import { ExternalLink, Sparkles } from "lucide-react";
import type { BotSummary } from "../api";
export default function BotCard({ bot }: { bot: BotSummary }) {
  const online = bot.online && bot.live;
  return (
    <div className="card p-5 flex flex-col gap-4">
      <div className="flex items-start gap-4">
        <div className="h-12 w-12 rounded-xl grid place-items-center text-white font-bold" style={{ background: `linear-gradient(135deg, ${bot.color}, #22d3ee)` }}>{bot.name.slice(0, 1)}</div>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-lg truncate">{bot.name}</h3>
            <span className={`pill ${online ? "bg-emerald-500/15 text-emerald-300" : bot.online ? "bg-amber-500/15 text-amber-300" : "bg-slate-500/15 text-slate-300"}`}>
              <span className={`inline-block h-2 w-2 rounded-full mr-1.5 align-middle ${online ? "bg-emerald-400" : bot.online ? "bg-amber-400" : "bg-slate-400"}`} />
              {online ? "Online" : bot.online ? "Idle" : "Offline"}
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1 line-clamp-2">{bot.tagline}</p>
        </div>
      </div>
      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-slate-400">
        {bot.features.slice(0, 6).map((f) => (<li key={f} className="flex items-center gap-2"><Sparkles size={12} className="text-brand-cyan" /> {f}</li>))}
      </ul>
      <div className="flex gap-2 mt-auto">
        <Link to={`/bots/${bot.id}`} className="btn btn-primary flex-1 justify-center">Manage</Link>
        {bot.invite && (<a className="btn btn-ghost" href={bot.invite} target="_blank" rel="noreferrer">Invite <ExternalLink size={14} /></a>)}
      </div>
    </div>
  );
}
