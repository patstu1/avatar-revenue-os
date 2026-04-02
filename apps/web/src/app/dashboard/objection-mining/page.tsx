"use client";
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "https://app.nvironments.com";
const brandId = "00000000-0000-0000-0000-000000000001";
async function apiFetch(path: string) { const r = await fetch(`${API}${path}`, { credentials: "include", headers: { "Content-Type": "application/json" } }); if (!r.ok) throw new Error(await r.text()); return r.json(); }

interface Cluster { id: string; objection_type: string; cluster_label: string; signal_count: number; avg_severity: number; avg_monetization_impact: number; recommended_response_angle: string | null; }
interface Signal { id: string; source_type: string; objection_type: string; extracted_objection: string; severity: number; monetization_impact: number; platform: string | null; }

const typeColors: Record<string, string> = { price: "bg-red-900 text-red-300", trust: "bg-orange-900 text-orange-300", complexity: "bg-yellow-900 text-yellow-300", timing: "bg-blue-900 text-blue-300", competitor: "bg-purple-900 text-purple-300", relevance: "bg-cyan-900 text-cyan-300", proof: "bg-green-900 text-green-300", identity: "bg-pink-900 text-pink-300", skepticism: "bg-gray-700 text-gray-300" };

export default function ObjectionMiningPage() {
  const [tab, setTab] = useState<"clusters" | "signals">("clusters");
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch(`/api/v1/brands/${brandId}/objection-clusters`),
      apiFetch(`/api/v1/brands/${brandId}/objection-signals`),
    ]).then(([c, s]) => { setClusters(c); setSignals(s); }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Objection Mining</h1>
      <div className="flex gap-2">
        {[{key: "clusters" as const, label: `Clusters (${clusters.length})`}, {key: "signals" as const, label: `Signals (${signals.length})`}].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} className={`px-4 py-2 rounded-lg text-sm font-medium ${tab === t.key ? "bg-amber-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>{t.label}</button>
        ))}
      </div>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <>
          {tab === "clusters" && (
            <div className="grid gap-4 md:grid-cols-2">{clusters.map(c => (
              <div key={c.id} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <div className="flex justify-between items-center mb-2">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${typeColors[c.objection_type] || "bg-gray-700 text-gray-400"}`}>{c.objection_type}</span>
                  <span className="text-gray-500 text-xs">{c.signal_count} signals</span>
                </div>
                <p className="text-white font-medium">{c.cluster_label}</p>
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                  <div><span className="text-gray-500">Severity</span><p className="text-white">{(c.avg_severity * 100).toFixed(0)}%</p></div>
                  <div><span className="text-gray-500">$ Impact</span><p className="text-amber-400">{(c.avg_monetization_impact * 100).toFixed(0)}%</p></div>
                </div>
                {c.recommended_response_angle && <p className="text-green-400 text-xs mt-2">{c.recommended_response_angle}</p>}
              </div>
            ))}{clusters.length === 0 && <p className="text-gray-500 col-span-2">No objection clusters yet.</p>}</div>
          )}
          {tab === "signals" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Type</th><th className="py-2 px-3">Source</th><th className="py-2 px-3">Objection</th><th className="py-2 px-3">Severity</th><th className="py-2 px-3">Impact</th></tr></thead>
              <tbody>{signals.map(s => (
                <tr key={s.id} className="border-b border-gray-800/50 text-gray-300">
                  <td className="py-2 px-3"><span className={`px-2 py-0.5 rounded text-xs ${typeColors[s.objection_type] || "bg-gray-700"}`}>{s.objection_type}</span></td>
                  <td className="py-2 px-3">{s.source_type}</td>
                  <td className="py-2 px-3 max-w-xs truncate">{s.extracted_objection}</td>
                  <td className="py-2 px-3">{(s.severity * 100).toFixed(0)}%</td>
                  <td className="py-2 px-3 text-amber-400">{(s.monetization_impact * 100).toFixed(0)}%</td>
                </tr>
              ))}</tbody>
            </table>{signals.length === 0 && <p className="text-gray-500 mt-4">No objection signals yet.</p>}</div>
          )}
        </>
      )}
    </div>
  );
}
