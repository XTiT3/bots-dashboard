import { NavLink, Outlet, useNavigate } from "react-router-dom";
import useSWR from "swr";
import { Bot, LayoutGrid, LogOut } from "lucide-react";
import { api } from "../api";
export default function Layout() {
  const nav = useNavigate();
  const { data: me, error } = useSWR("me", api.me, { revalidateOnFocus: false });
  if (error) { nav("/login"); return null; }
  return (
    <div className="min-h-full flex">
      <aside className="w-64 shrink-0 border-r border-white/5 bg-navy-900/60 backdrop-blur flex flex-col">
        <div className="px-5 py-6 flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-brand-blue to-brand-cyan grid place-items-center shadow-glow"><Bot size={18} /></div>
          <div><div className="text-sm font-semibold">Bots Dashboard</div><div className="text-xs text-slate-400">Control center</div></div>
        </div>
        <nav className="px-3 space-y-1">
          <NavLink to="/" end className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-2 text-sm ${isActive ? "bg-white/10 text-white" : "text-slate-300 hover:bg-white/5"}`}><LayoutGrid size={16} /> Overview</NavLink>
        </nav>
        <div className="mt-auto px-5 py-6 text-xs text-slate-400">
          <div className="flex items-center justify-between">
            <div className="truncate">{me?.username ?? "…"}</div>
            <button className="btn btn-ghost !px-2 !py-1" onClick={async () => { await api.logout(); nav("/login"); }}><LogOut size={14} /></button>
          </div>
        </div>
      </aside>
      <main className="flex-1 min-w-0 p-8"><Outlet /></main>
    </div>
  );
}
