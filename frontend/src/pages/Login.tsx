import { Bot } from "lucide-react";
import { api } from "../api";
export default function Login() {
  return (
    <div className="min-h-full grid place-items-center p-6">
      <div className="card max-w-md w-full p-8 text-center">
        <div className="mx-auto h-14 w-14 rounded-2xl bg-gradient-to-br from-brand-blue to-brand-cyan grid place-items-center shadow-glow"><Bot size={26} /></div>
        <h1 className="mt-6 text-2xl font-semibold">Bots Dashboard</h1>
        <p className="mt-2 text-sm text-slate-400">One place to manage Ali, Organizer and Translator.</p>
        <button onClick={api.login} className="btn btn-primary mt-8 w-full justify-center">Log in with Discord</button>
        <p className="mt-4 text-xs text-slate-500">Only servers where you have <b>Manage Server</b> or <b>Administrator</b> are shown.</p>
      </div>
    </div>
  );
}
