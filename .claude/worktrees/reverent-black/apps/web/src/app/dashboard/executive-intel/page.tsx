"use client";
import { useEffect, useState } from "react";
import { useAuthStore } from "@/lib/store";
import { apiFetch } from "@/lib/api";

interface KPI { id: string; period: string; total_revenue: number; total_profit: number; total_spend: number; content_produced: number; content_published: number; avg_engagement_rate: number; active_accounts: number; active_campaigns: number; }
interface Alert { id: string; alert_type: string; severity: string; title: string; detail: string; recommended_action: string | null; }
interface Forecast { id: string; forecast_type: string; predicted_value: number; confidence: number; explanation: string | null; }

export default function ExecutiveIntelPage() {
  const user = useAuthStore((s) => s.user);
  const orgId = user?.organization_id ?? "";
  const [kpis, setKpis] = useState<KPI[]>([]); const [alerts, setAlerts] = useState<Alert[]>([]); const [forecasts, setForecasts] = useState<Forecast[]>([]); const [loading, setLoading] = useState(true);
  useEffect(() => { if (!orgId) return; Promise.all([apiFetch<any>(`/api/v1/orgs/${orgId}/executive/kpis`), apiFetch<any>(`/api/v1/orgs/${orgId}/executive/alerts`), apiFetch<any>(`/api/v1/orgs/${orgId}/executive/forecasts`)]).then(([k, a, f]) => { setKpis(Array.isArray(k) ? k : []); setAlerts(Array.isArray(a) ? a : []); setForecasts(Array.isArray(f) ? f : []); }).catch(() => {}).finally(() => setLoading(false)); }, [orgId]);
  const latest = kpis[0];

  if (!orgId) return <div className="p-6"><p className="text-gray-500">Loading organization...</p></div>;

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Executive Intelligence</h1>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <>
          {latest && (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {[
                { label: "REVENUE", value: `$${Number(latest.total_revenue ?? 0).toLocaleString()}`, color: "text-cyan-300" },
                { label: "PROFIT", value: `$${Number(latest.total_profit ?? 0).toLocaleString()}`, color: "text-green-400" },
                { label: "SPEND", value: `$${Number(latest.total_spend ?? 0).toLocaleString()}` },
                { label: "PRODUCED", value: latest.content_produced ?? 0 },
                { label: "PUBLISHED", value: latest.content_published ?? 0 },
                { label: "ENGAGEMENT", value: `${(Number(latest.avg_engagement_rate ?? 0) * 100).toFixed(1)}%` },
                { label: "ACCOUNTS", value: latest.active_accounts ?? 0 },
                { label: "CAMPAIGNS", value: latest.active_campaigns ?? 0 },
              ].map((s, i) => (
                <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                  <p className="text-[10px] text-gray-500 font-mono">{s.label}</p>
                  <p className={`text-xl font-black mt-1 ${s.color || "text-white"}`}>{s.value}</p>
                </div>
              ))}
            </div>
          )}
          {forecasts.length > 0 && (
            <div className="mt-4"><h2 className="text-lg font-semibold text-white mb-3">Forecasts</h2>
              <div className="grid gap-3 md:grid-cols-2">{forecasts.map(f => (
                <div key={f.id} className="bg-gray-900 border border-cyan-900/30 rounded-lg p-4">
                  <div className="flex justify-between"><span className="text-cyan-400 text-xs uppercase">{f.forecast_type}</span><span className="text-gray-500 text-xs">{(Number(f.confidence ?? 0) * 100).toFixed(0)}% conf</span></div>
                  <p className="text-2xl font-bold text-white mt-2">${Number(f.predicted_value ?? 0).toLocaleString()}</p>
                  {f.explanation && <p className="text-gray-500 text-xs mt-1">{f.explanation}</p>}
                </div>
              ))}</div>
            </div>
          )}
          {alerts.length > 0 && (
            <div className="mt-4"><h2 className="text-lg font-semibold text-white mb-3">Executive Alerts</h2>
              <div className="space-y-3">{alerts.map(a => (
                <div key={a.id} className={`border rounded-lg p-4 ${a.severity === "critical" ? "bg-red-950 border-red-800" : "bg-yellow-950 border-yellow-800"}`}>
                  <div className="flex justify-between items-center mb-1"><span className={`font-medium ${a.severity === "critical" ? "text-red-300" : "text-yellow-300"}`}>{a.title}</span><span className="text-xs text-gray-500">{a.severity}</span></div>
                  <p className="text-gray-400 text-sm">{a.detail}</p>
                  {a.recommended_action && <p className="text-green-400 text-xs mt-2">{a.recommended_action}</p>}
                </div>
              ))}</div>
            </div>
          )}
          {!latest && alerts.length === 0 && <p className="text-gray-500">No executive data yet. Run recompute.</p>}
        </>
      )}
    </div>
  );
}
