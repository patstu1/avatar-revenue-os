"use client";
import { useEffect, useState } from "react";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const brandId = "00000000-0000-0000-0000-000000000001";
async function apiFetch(path: string) { const r = await fetch(`${API}${path}`, { credentials: "include", headers: { "Content-Type": "application/json" } }); if (!r.ok) throw new Error(await r.text()); return r.json(); }

interface Scenario { id: string; scenario_type: string; option_label: string; compared_to: string | null; expected_upside: number; expected_cost: number; expected_risk: number; confidence: number; time_to_signal_days: number; is_recommended: boolean; explanation: string | null; }
interface Rec { id: string; scenario_type: string; recommended_action: string; expected_profit_delta: number; confidence: number; explanation: string | null; }

export default function SimulationsPage() {
  const [tab, setTab] = useState<"scenarios" | "recs">("recs");
  const [scenarios, setScenarios] = useState<Scenario[]>([]); const [recs, setRecs] = useState<Rec[]>([]); const [loading, setLoading] = useState(true);
  useEffect(() => { Promise.all([apiFetch(`/api/v1/brands/${brandId}/simulations/scenarios`), apiFetch(`/api/v1/brands/${brandId}/simulations/recommendations`)]).then(([s, r]) => { setScenarios(s); setRecs(r); }).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Digital Twin / Simulations</h1>
      <div className="flex gap-2">
        {[{key: "recs" as const, label: `Recommendations (${recs.length})`}, {key: "scenarios" as const, label: `Scenarios (${scenarios.length})`}].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} className={`px-4 py-2 rounded-lg text-sm font-medium ${tab === t.key ? "bg-cyan-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>{t.label}</button>
        ))}
      </div>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <>
          {tab === "recs" && (
            <div className="space-y-3">{recs.map(r => (
              <div key={r.id} className="bg-gray-900 border border-cyan-900/30 rounded-lg p-4">
                <div className="flex justify-between items-center mb-2"><span className="text-cyan-400 text-xs">{r.scenario_type}</span><span className="text-gray-500 text-xs">{(r.confidence * 100).toFixed(0)}% conf</span></div>
                <p className="text-white font-medium">{r.recommended_action}</p>
                <p className="text-green-400 text-sm mt-1">+${r.expected_profit_delta.toFixed(0)} profit delta</p>
                {r.explanation && <p className="text-gray-500 text-xs mt-1">{r.explanation}</p>}
              </div>
            ))}{recs.length === 0 && <p className="text-gray-500">No simulation recommendations yet. Run simulation.</p>}</div>
          )}
          {tab === "scenarios" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Type</th><th className="py-2 px-3">Option</th><th className="py-2 px-3">vs</th><th className="py-2 px-3">Upside</th><th className="py-2 px-3">Cost</th><th className="py-2 px-3">Risk</th><th className="py-2 px-3">Pick</th></tr></thead>
              <tbody>{scenarios.map(s => (
                <tr key={s.id} className={`border-b border-gray-800/50 ${s.is_recommended ? "text-cyan-300" : "text-gray-400"}`}>
                  <td className="py-2 px-3 text-xs">{s.scenario_type}</td>
                  <td className="py-2 px-3 font-medium">{s.option_label}</td>
                  <td className="py-2 px-3 text-xs">{s.compared_to || "—"}</td>
                  <td className="py-2 px-3">${s.expected_upside.toFixed(0)}</td>
                  <td className="py-2 px-3">${s.expected_cost.toFixed(0)}</td>
                  <td className="py-2 px-3">{(s.expected_risk * 100).toFixed(0)}%</td>
                  <td className="py-2 px-3">{s.is_recommended ? <span className="text-cyan-400 font-bold">✓</span> : ""}</td>
                </tr>
              ))}</tbody>
            </table>{scenarios.length === 0 && <p className="text-gray-500 mt-4">No scenarios. Run simulation.</p>}</div>
          )}
        </>
      )}
    </div>
  );
}
