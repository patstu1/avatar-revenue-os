"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useBrandId } from "@/hooks/useBrandId";

interface Report { id: string; total_leaks: number; total_estimated_loss: number; critical_count: number; top_leak_type: string | null; summary: string | null; }
interface LeakEvent { id: string; leak_type: string; severity: string; affected_scope: string; estimated_revenue_loss: number; confidence: number; next_best_action: string; status: string; }
interface Cluster { id: string; cluster_type: string; event_count: number; total_loss: number; priority_score: number; recommended_action: string | null; }

const sevColor: Record<string, string> = { critical: "bg-red-900 text-red-300", high: "bg-orange-900 text-orange-300", medium: "bg-yellow-900 text-yellow-300" };

export default function RevenueLeaksPage() {
  const brandId = useBrandId();
  const [tab, setTab] = useState<"overview" | "events" | "clusters">("overview");
  const [reports, setReports] = useState<Report[]>([]); const [events, setEvents] = useState<LeakEvent[]>([]); const [clusters, setClusters] = useState<Cluster[]>([]); const [loading, setLoading] = useState(true);

  useEffect(() => { if (!brandId) return; setLoading(true); Promise.all([apiFetch<any>(`/api/v1/brands/${brandId}/revenue-leaks`), apiFetch<any>(`/api/v1/brands/${brandId}/revenue-leaks/events`), apiFetch<any>(`/api/v1/brands/${brandId}/revenue-leaks/clusters`)]).then(([r, e, c]) => { setReports(Array.isArray(r) ? r : []); setEvents(Array.isArray(e) ? e : []); setClusters(Array.isArray(c) ? c : []); }).catch(() => {}).finally(() => setLoading(false)); }, [brandId]);
  const latest = reports[0];

  if (!brandId) return <div className="p-6 text-gray-400">No active brand selected. Use the brand switcher in the top bar.</div>;

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Revenue Leak Detector</h1>
      <p className="text-xs text-gray-500">Scoped to the active brand (use the top-bar switcher to change brand).</p>
      <div className="flex gap-2">
        {[{key: "overview" as const, label: "Overview"}, {key: "events" as const, label: `Leaks (${events.length})`}, {key: "clusters" as const, label: `Clusters (${clusters.length})`}].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} className={`px-4 py-2 rounded-lg text-sm font-medium ${tab === t.key ? "bg-red-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>{t.label}</button>
        ))}
      </div>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <>
          {tab === "overview" && latest && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-4"><p className="text-[10px] text-gray-500 font-mono">TOTAL LEAKS</p><p className="text-2xl font-black text-red-400 mt-1">{latest.total_leaks ?? 0}</p></div>
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-4"><p className="text-[10px] text-gray-500 font-mono">EST. LOSS</p><p className="text-2xl font-black text-red-400 mt-1">${Number(latest.total_estimated_loss ?? 0).toFixed(0)}</p></div>
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-4"><p className="text-[10px] text-gray-500 font-mono">CRITICAL</p><p className="text-2xl font-black text-red-500 mt-1">{latest.critical_count ?? 0}</p></div>
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-4"><p className="text-[10px] text-gray-500 font-mono">TOP TYPE</p><p className="text-lg font-bold text-amber-400 mt-1">{latest.top_leak_type || "—"}</p></div>
            </div>
          )}
          {tab === "events" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Type</th><th className="py-2 px-3">Scope</th><th className="py-2 px-3">Loss</th><th className="py-2 px-3">Severity</th><th className="py-2 px-3">Action</th></tr></thead>
              <tbody>{events.map(e => (
                <tr key={e.id} className="border-b border-gray-800/50 text-gray-300">
                  <td className="py-2 px-3 text-xs">{e.leak_type}</td>
                  <td className="py-2 px-3">{e.affected_scope}</td>
                  <td className="py-2 px-3 text-red-400">${Number(e.estimated_revenue_loss ?? 0).toFixed(0)}</td>
                  <td className="py-2 px-3"><span className={`px-2 py-0.5 rounded text-xs ${sevColor[e.severity] || "bg-gray-700 text-gray-400"}`}>{e.severity}</span></td>
                  <td className="py-2 px-3 text-green-400 text-xs">{e.next_best_action}</td>
                </tr>
              ))}</tbody>
            </table>{events.length === 0 && <p className="text-gray-500 mt-4">No leak events.</p>}</div>
          )}
          {tab === "clusters" && (
            <div className="grid gap-4 md:grid-cols-2">{clusters.map(c => (
              <div key={c.id} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <div className="flex justify-between items-center mb-2"><span className="text-red-400 text-xs">{c.cluster_type}</span><span className="text-gray-500 text-xs">{c.event_count} events</span></div>
                <p className="text-red-400 font-bold text-xl">${Number(c.total_loss ?? 0).toFixed(0)} lost</p>
                {c.recommended_action && <p className="text-green-400 text-xs mt-2">{c.recommended_action}</p>}
              </div>
            ))}{clusters.length === 0 && <p className="text-gray-500 col-span-2">No leak clusters.</p>}</div>
          )}
          {!latest && tab === "overview" && <p className="text-gray-500">No leak data yet. Run recompute.</p>}
        </>
      )}
    </div>
  );
}
