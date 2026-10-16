import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import useSWR from "swr";
import { ArrowLeft, ExternalLink, Save } from "lucide-react";
import { api, type BotDetail } from "../api";
export default function BotPage() {
  const { botId = "" } = useParams();
  const { data: bot } = useSWR<BotDetail>(["bot", botId], () => api.bot(botId));
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  if (!bot) return <div className="text-slate-500">Loading…</div>;
  return (
    <div className="space-y-8">
      <Link to="/" className="text-slate-400 hover:text-white inline-flex items-center gap-2 text-sm"><ArrowLeft size={14} /> Back</Link>
      <header className="flex items-start gap-5">
        <div className="h-16 w-16 rounded-2xl grid place-items-center text-2xl font-bold text-white" style={{ background: `linear-gradient(135deg, ${bot.color}, #22d3ee)` }}>{bot.name.slice(0, 1)}</div>
        <div className="flex-1 min-w-0">
          <h1 className="text-3xl font-semibold">{bot.name}</h1><p className="text-slate-400 mt-1">{bot.tagline}</p>
          <div className="flex gap-2 mt-3">
            <span className={`pill ${bot.online ? "bg-emerald-500/15 text-emerald-300" : "bg-slate-500/15 text-slate-300"}`}>{bot.online ? "Token valid" : "Not configured"}</span>
            <span className={`pill ${bot.live ? "bg-brand-cyan/15 text-brand-cyan" : "bg-slate-500/15 text-slate-300"}`}>{bot.live ? "Live" : "Idle"}</span>
            {bot.invite && (<a className="pill bg-white/5 hover:bg-white/10 inline-flex items-center gap-1" href={bot.invite} target="_blank" rel="noreferrer">Invite <ExternalLink size={12} /></a>)}
          </div>
        </div>
      </header>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <section className="card p-5 lg:col-span-1">
          <h2 className="font-medium mb-3">Features</h2><ul className="space-y-2 text-sm text-slate-300">{bot.features.map((f) => <li key={f}>• {f}</li>)}</ul>
          <h2 className="font-medium mt-6 mb-3">Servers ({bot.guilds.length})</h2><ul className="space-y-1 text-sm text-slate-400 max-h-60 overflow-y-auto pr-1">{bot.guilds.map((g) => <li key={g.id} className="truncate">{g.name}</li>)}{bot.guilds.length === 0 && <li>Not in any server.</li>}</ul>
        </section>
        <section className="card p-5 lg:col-span-2">
          <h2 className="font-medium mb-3">Configuration files</h2>
          <div className="flex flex-wrap gap-2 mb-4">{bot.files.map((f) => (<button key={f.name} onClick={() => setSelectedFile(f.name)} className={`pill ${selectedFile === f.name ? "bg-brand-blue text-white" : "bg-white/5 hover:bg-white/10"}`}>{f.name}</button>))}</div>
          {selectedFile ? <FileEditor botId={bot.id} name={selectedFile} /> : <p className="text-slate-500 text-sm">Select a file to view and edit it.</p>}
        </section>
      </div>
    </div>
  );
}
function FileEditor({ botId, name }: { botId: string; name: string }) {
  const { data, mutate } = useSWR(["file", botId, name], () => api.readBotFile(botId, name));
  const [text, setText] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("");
  const shown = text ?? (data === undefined ? "" : JSON.stringify(data, null, 2));
  async function save() {
    try { const parsed = JSON.parse(shown); await api.writeBotFile(botId, name, parsed); setStatus("Saved"); mutate(); setTimeout(() => setStatus(""), 2000); }
    catch (e) { setStatus(`Invalid JSON: ${(e as Error).message}`); }
  }
  return (
    <div className="space-y-3">
      <textarea spellCheck={false} value={shown} onChange={(e) => setText(e.target.value)} className="input font-mono !text-xs h-80" />
      <div className="flex items-center gap-3"><button className="btn btn-primary" onClick={save}><Save size={14} /> Save</button><button className="btn btn-ghost" onClick={() => { setText(null); mutate(); }}>Reset</button>{status && <span className="text-xs text-slate-400">{status}</span>}</div>
    </div>
  );
}
