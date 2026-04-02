"use client";
import { useEffect, useState } from "react";
import { useAuthStore } from "@/lib/store";
import { brandsApi } from "@/lib/api";
const API = process.env.NEXT_PUBLIC_API_URL ?? (typeof window !== "undefined" ? window.location.origin : "http://localhost:8001");
function getAuthHeaders(): Record<string, string> {
  const token = typeof window !== "undefined" ? localStorage.getItem("aro_token") : null;
  return { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) };
}
async function apiFetch(path: string) { const r = await fetch(`${API}${path}`, { headers: getAuthHeaders() }); if (!r.ok) throw new Error(await r.text()); return r.json(); }

interface Report { id: string; target_metric: string; direction: string; magnitude: number; top_driver: string | null; total_hypotheses: number; summary: string | null; }
interface Hypothesis { id: string; driver_type: string; driver_name: string; estimated_lift_pct: number; confidence: number; recommended_action: string | null; }
interface Credit { id: string; driver_name: string; credit_pct: number; confidence: number; promote_cautiously: boolean; }

export default function CausalAttributionPage() {
  const [tab, setTab] = useState<"reports" | "hypotheses" | "credits">("reports");
  const [reports, setReports] = useState<Report[]>([]); const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]); const [credits, setCredits] = useState<Credit[]>([]); const [loading, setLoading] = useState(true);
  const [brandId, setBrandId] = useState("");
  const [brands, setBrands] = useState<{id: string; name: string}[]>([]);

  useEffect(() => {
    brandsApi.list().then((r) => {
      const list = r.data ?? r;
      setBrands(Array.isArray(list) ? list : []);
      if (Array.isArray(list) && list.length > 0) setBrandId(list[0].id);
    }).catch(() => {});
  }, []);

  useEffect(() => { if (!brandId) return; Promise.all([apiFetch(`/api/v1/brands/${brandId}/causal-attribution`), apiFetch(`/api/v1/brands/${brandId}/causal-attribution/hypotheses`), apiFetch(`/api/v1/brands/${brandId}/causal-attribution/credits`)]).then(([r, h, c]) => { setReports(r); setHypotheses(h); setCredits(c); }).catch(() => {}).finally(() => setLoading(false)); }, [brandId]);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Causal Attribution</h1>
      <div className="flex items-center gap-3">
        <label className="text-sm text-gray-400">Brand:</label>
        <select aria-label="Brand" className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white" value={brandId} onChange={e => setBrandId(e.target.value)}>
          {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </div>
      <div className="flex gap-2">
        {[{key: "reports" as const, label: `Reports (${reports.length})`}, {key: "hypotheses" as const, label: `Hypotheses (${hypotheses.length})`}, {key: "credits" as const, label: `Credits (${credits.length})`}].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} className={`px-4 py-2 rounded-lg text-sm font-medium ${tab === t.key ? "bg-cyan-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>{t.label}</button>
        ))}
      </div>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <>
          {tab === "reports" && reports.map(r => (
            <div key={r.id} className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-3">
              <div className="flex justify-between"><span className="text-cyan-400 text-xs">{r.target_metric}</span><span className={`text-xs font-bold ${r.direction === "lift" ? "text-green-400" : "text-red-400"}`}>{r.direction} {r.magnitude.toFixed(0)}%</span></div>
              <p className="text-white font-medium mt-1">{r.top_driver || "—"}</p>
              <p className="text-gray-500 text-xs mt-1">{r.summary}</p>
            </div>
          ))}
          {tab === "hypotheses" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Driver</th><th className="py-2 px-3">Type</th><th className="py-2 px-3">Lift</th><th className="py-2 px-3">Confidence</th><th className="py-2 px-3">Action</th></tr></thead>
              <tbody>{hypotheses.map(h => (
                <tr key={h.id} className="border-b border-gray-800/50 text-gray-300">
                  <td className="py-2 px-3 font-medium">{h.driver_name}</td>
                  <td className="py-2 px-3 text-xs text-cyan-400">{h.driver_type}</td>
                  <td className="py-2 px-3">{h.estimated_lift_pct > 0 ? "+" : ""}{h.estimated_lift_pct.toFixed(0)}%</td>
                  <td className="py-2 px-3">{(h.confidence * 100).toFixed(0)}%</td>
                  <td className="py-2 px-3 text-green-400 text-xs">{h.recommended_action}</td>
                </tr>
              ))}</tbody>
            </table></div>
          )}
          {tab === "credits" && (
            <div className="grid gap-3 md:grid-cols-2">{credits.map(c => (
              <div key={c.id} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <div className="flex justify-between items-center mb-2"><span className="text-white font-medium">{c.driver_name}</span><span className="text-amber-400 font-bold">{c.credit_pct.toFixed(0)}%</span></div>
                <div className="flex gap-3 text-xs"><span className="text-gray-500">Conf: {(c.confidence * 100).toFixed(0)}%</span>{c.promote_cautiously && <span className="text-yellow-400">CAUTIOUS</span>}</div>
              </div>
            ))}</div>
          )}
          {reports.length === 0 && tab === "reports" && <p className="text-gray-500">No causal attribution data yet. Run recompute.</p>}
        </>
      )}
    </div>
  );
}
