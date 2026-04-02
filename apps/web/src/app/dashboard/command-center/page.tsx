"use client";
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const brandId = "00000000-0000-0000-0000-000000000001";
async function apiFetch(path: string) {
  const r = await fetch(`${API}${path}`, { credentials: "include", headers: { "Content-Type": "application/json" } });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

interface Provider { provider_key: string; provider_name: string; status: string; credential_status: string; is_ready: boolean; blockers: { type: string; severity: string; action: string }[]; }
interface Platform { platform: string; status: string; accounts: number; healthy: number; weak: number; blocked: number; saturated: number; scaling: number; }
interface Alert { title: string; urgency: number; action: string | null; }
interface TopAction { rank: number; type: string; key: string; urgency: number; delay_cost: number; }

interface CommandData {
  revenue: { lifetime_revenue: number; lifetime_profit: number; lifetime_spend: number; today_revenue: number; week_revenue: number; month_revenue: number; by_platform: Record<string, number>; by_offer: Record<string, number>; by_account: Record<string, number>; strongest_lane: string | null; weakest_lane: string | null; };
  providers: Provider[];
  platforms: Platform[];
  accounts: { total: number; by_state: Record<string, number>; scaling: number; weak: number; saturated: number; blocked: number; expansion_eligible: number; };
  alerts: { critical_alerts: Alert[]; quality_blocks: { reason: string; severity: string }[]; active_suppressions: { type: string; key: string; mode: string }[]; top_actions: TopAction[]; };
}

const statusGlow = (s: string) => {
  if (s === "healthy") return "border-cyan-400/60 shadow-[0_0_15px_rgba(34,211,238,0.3)]";
  if (s === "needs_attention" || s === "degraded" || s === "weak" || s === "saturated" || s === "warming") return "border-pink-400/60 shadow-[0_0_15px_rgba(236,72,153,0.4)] animate-pulse";
  if (s === "blocked") return "border-red-500/80 shadow-[0_0_20px_rgba(239,68,68,0.5)] animate-pulse";
  return "border-gray-700/50 opacity-50";
};
const statusDot = (s: string) => {
  if (s === "healthy") return "bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)]";
  if (s === "needs_attention" || s === "degraded" || s === "weak") return "bg-pink-400 shadow-[0_0_8px_rgba(236,72,153,0.8)] animate-pulse";
  if (s === "blocked") return "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)] animate-pulse";
  return "bg-gray-600";
};

export default function CommandCenterPage() {
  const [data, setData] = useState<CommandData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch(`/api/v1/brands/${brandId}/command-center`).then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex items-center justify-center h-screen bg-gray-950"><div className="text-cyan-400 text-lg animate-pulse">INITIALIZING COMMAND CENTER...</div></div>;
  if (!data) return <div className="flex items-center justify-center h-screen bg-gray-950"><div className="text-red-400 text-lg">COMMAND CENTER OFFLINE</div></div>;

  const { revenue: rev, providers, platforms, accounts: accts, alerts } = data;

  return (
    <div className="min-h-screen bg-gray-950 text-white p-6 space-y-8">
      {/* HEADER */}
      <div className="flex items-center justify-between border-b border-cyan-900/30 pb-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">SYSTEM COMMAND CENTER</h1>
          <p className="text-gray-500 text-xs mt-1 font-mono">AUTONOMOUS REVENUE OS • LIVE</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)] animate-pulse"></span>
          <span className="text-cyan-400 text-xs font-mono">OPERATIONAL</span>
        </div>
      </div>

      {/* REVENUE COMMAND CENTER */}
      <section>
        <h2 className="text-sm font-bold text-cyan-400/80 uppercase tracking-widest mb-4">Revenue Command Center</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
          {[
            { label: "LIFETIME REVENUE", value: `$${rev.lifetime_revenue.toLocaleString()}`, color: "text-cyan-300" },
            { label: "LIFETIME PROFIT", value: `$${rev.lifetime_profit.toLocaleString()}`, color: "text-green-400" },
            { label: "TOTAL SPEND", value: `$${rev.lifetime_spend.toLocaleString()}`, color: "text-gray-400" },
            { label: "TODAY", value: `$${rev.today_revenue.toLocaleString()}`, color: "text-cyan-300" },
            { label: "7 DAYS", value: `$${rev.week_revenue.toLocaleString()}`, color: "text-cyan-300" },
            { label: "30 DAYS", value: `$${rev.month_revenue.toLocaleString()}`, color: "text-cyan-300" },
          ].map((s, i) => (
            <div key={i} className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-4 backdrop-blur-sm">
              <p className="text-[10px] text-gray-500 font-mono uppercase">{s.label}</p>
              <p className={`text-xl font-black mt-1 ${s.color}`}>{s.value}</p>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
          <div className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-4">
            <p className="text-[10px] text-gray-500 font-mono uppercase">BY PLATFORM</p>
            {Object.entries(rev.by_platform).map(([k, v]) => <div key={k} className="flex justify-between text-xs mt-1"><span className="text-gray-400">{k}</span><span className="text-cyan-300 font-mono">${v.toLocaleString()}</span></div>)}
            {Object.keys(rev.by_platform).length === 0 && <p className="text-gray-600 text-xs mt-1">No data yet</p>}
          </div>
          <div className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-4">
            <p className="text-[10px] text-gray-500 font-mono uppercase">BY OFFER</p>
            {Object.entries(rev.by_offer).slice(0, 5).map(([k, v]) => <div key={k} className="flex justify-between text-xs mt-1"><span className="text-gray-400 truncate max-w-[120px]">{k}</span><span className="text-cyan-300 font-mono">${v.toLocaleString()}</span></div>)}
            {Object.keys(rev.by_offer).length === 0 && <p className="text-gray-600 text-xs mt-1">No data yet</p>}
          </div>
          <div className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-4">
            <p className="text-[10px] text-gray-500 font-mono uppercase">STRONGEST LANE</p>
            <p className="text-green-400 font-bold mt-2">{rev.strongest_lane || "—"}</p>
          </div>
          <div className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-4">
            <p className="text-[10px] text-gray-500 font-mono uppercase">WEAKEST LANE</p>
            <p className="text-pink-400 font-bold mt-2">{rev.weakest_lane || "—"}</p>
          </div>
        </div>
      </section>

      {/* API / PROVIDER HEALTH WALL */}
      <section>
        <h2 className="text-sm font-bold text-cyan-400/80 uppercase tracking-widest mb-4">API / Provider Health Wall</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {providers.map(p => (
            <div key={p.provider_key} className={`bg-gray-900/60 border rounded-xl p-3 backdrop-blur-sm transition-all ${statusGlow(p.status)}`}>
              <div className="flex items-center gap-2 mb-2">
                <span className={`w-2 h-2 rounded-full ${statusDot(p.status)}`}></span>
                <span className="text-xs font-bold text-white truncate">{p.provider_name}</span>
              </div>
              <div className="space-y-1 text-[10px]">
                <div className="flex justify-between"><span className="text-gray-500">STATUS</span><span className={p.status === "healthy" ? "text-cyan-400" : p.status === "blocked" ? "text-red-400" : "text-pink-400"}>{p.status.toUpperCase()}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">CREDS</span><span className="text-gray-400">{p.credential_status}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">READY</span><span className={p.is_ready ? "text-cyan-400" : "text-gray-600"}>{p.is_ready ? "YES" : "NO"}</span></div>
              </div>
              {p.blockers.length > 0 && <div className="mt-2 text-[9px] text-red-400 border-t border-red-900/30 pt-1">{p.blockers[0].action}</div>}
            </div>
          ))}
          {providers.length === 0 && <p className="text-gray-600 text-xs col-span-5">No providers registered</p>}
        </div>
      </section>

      {/* PLATFORM HEALTH WALL */}
      <section>
        <h2 className="text-sm font-bold text-cyan-400/80 uppercase tracking-widest mb-4">Platform Health Wall</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {platforms.map(p => (
            <div key={p.platform} className={`bg-gray-900/60 border rounded-xl p-4 backdrop-blur-sm ${statusGlow(p.status)}`}>
              <div className="flex items-center gap-2 mb-3">
                <span className={`w-2.5 h-2.5 rounded-full ${statusDot(p.status)}`}></span>
                <span className="text-sm font-bold text-white uppercase">{p.platform}</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div><span className="text-gray-500 text-[10px]">ACCOUNTS</span><p className="text-white font-bold">{p.accounts}</p></div>
                <div><span className="text-gray-500 text-[10px]">SCALING</span><p className="text-cyan-400 font-bold">{p.scaling}</p></div>
                <div><span className="text-gray-500 text-[10px]">WEAK</span><p className="text-pink-400 font-bold">{p.weak}</p></div>
                <div><span className="text-gray-500 text-[10px]">BLOCKED</span><p className="text-red-400 font-bold">{p.blocked}</p></div>
              </div>
            </div>
          ))}
          {platforms.length === 0 && <p className="text-gray-600 text-xs col-span-4">No platforms active</p>}
        </div>
      </section>

      {/* ACCOUNT OPS */}
      <section>
        <h2 className="text-sm font-bold text-cyan-400/80 uppercase tracking-widest mb-4">Account Operations</h2>
        <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
          {[
            { label: "TOTAL", value: accts.total, color: "text-white" },
            { label: "SCALING", value: accts.scaling, color: "text-cyan-400" },
            { label: "WEAK", value: accts.weak, color: "text-pink-400" },
            { label: "SATURATED", value: accts.saturated, color: "text-yellow-400" },
            { label: "BLOCKED", value: accts.blocked, color: "text-red-400" },
            { label: "EXPAND OK", value: accts.expansion_eligible, color: "text-green-400" },
          ].map((s, i) => (
            <div key={i} className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-4 text-center">
              <p className="text-[10px] text-gray-500 font-mono">{s.label}</p>
              <p className={`text-2xl font-black mt-1 ${s.color}`}>{s.value}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ALERT / ACTION LAYER */}
      <section>
        <h2 className="text-sm font-bold text-cyan-400/80 uppercase tracking-widest mb-4">Alerts &amp; Actions</h2>
        <div className="grid md:grid-cols-2 gap-4">
          <div className="bg-gray-900/60 border border-red-900/30 rounded-xl p-4">
            <p className="text-[10px] text-red-400 font-mono uppercase mb-3">CRITICAL ALERTS</p>
            {alerts.critical_alerts.length === 0 && <p className="text-gray-600 text-xs">No critical alerts</p>}
            {alerts.critical_alerts.map((a, i) => (
              <div key={i} className="mb-2 border-l-2 border-red-500 pl-3">
                <p className="text-sm text-white font-medium">{a.title}</p>
                {a.action && <p className="text-xs text-gray-400 mt-0.5">{a.action}</p>}
              </div>
            ))}
          </div>
          <div className="bg-gray-900/60 border border-cyan-900/30 rounded-xl p-4">
            <p className="text-[10px] text-cyan-400 font-mono uppercase mb-3">WHAT MATTERS NOW</p>
            {alerts.top_actions.length === 0 && <p className="text-gray-600 text-xs">No ranked actions</p>}
            {alerts.top_actions.map((a, i) => (
              <div key={i} className="flex items-center gap-3 mb-2">
                <span className="text-cyan-400 font-mono text-xs w-6">#{a.rank}</span>
                <div className="flex-1">
                  <p className="text-sm text-white">{a.type}: {a.key}</p>
                  <p className="text-[10px] text-gray-500">${a.delay_cost.toFixed(0)}/day delay cost • {(a.urgency * 100).toFixed(0)}% urgency</p>
                </div>
              </div>
            ))}
          </div>
          <div className="bg-gray-900/60 border border-pink-900/30 rounded-xl p-4">
            <p className="text-[10px] text-pink-400 font-mono uppercase mb-3">QUALITY BLOCKS</p>
            {alerts.quality_blocks.length === 0 && <p className="text-gray-600 text-xs">No quality blocks</p>}
            {alerts.quality_blocks.map((b, i) => <p key={i} className="text-xs text-pink-300 mb-1">• {b.reason}</p>)}
          </div>
          <div className="bg-gray-900/60 border border-yellow-900/30 rounded-xl p-4">
            <p className="text-[10px] text-yellow-400 font-mono uppercase mb-3">ACTIVE SUPPRESSIONS</p>
            {alerts.active_suppressions.length === 0 && <p className="text-gray-600 text-xs">No active suppressions</p>}
            {alerts.active_suppressions.map((s, i) => <p key={i} className="text-xs text-yellow-300 mb-1">• {s.type}: {s.key} ({s.mode})</p>)}
          </div>
        </div>
      </section>

      {/* COPILOT LINK */}
      <section className="border-t border-cyan-900/20 pt-6">
        <a href="/dashboard/copilot" className="inline-flex items-center gap-3 bg-gradient-to-r from-cyan-900/40 to-blue-900/40 border border-cyan-700/30 rounded-xl px-6 py-4 hover:border-cyan-500/50 transition-all group">
          <span className="w-3 h-3 rounded-full bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.6)] group-hover:shadow-[0_0_15px_rgba(34,211,238,0.8)] transition-all"></span>
          <div>
            <p className="text-cyan-300 font-bold">OPERATOR COPILOT</p>
            <p className="text-gray-500 text-xs">Ask anything about the system state</p>
          </div>
        </a>
      </section>
    </div>
  );
}
