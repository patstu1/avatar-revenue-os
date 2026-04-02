"use client";
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const brandId = "00000000-0000-0000-0000-000000000001";
async function apiFetch(path: string) { const r = await fetch(`${API}${path}`, { credentials: "include", headers: { "Content-Type": "application/json" } }); if (!r.ok) throw new Error(await r.text()); return r.json(); }

interface Report { id: string; total_actions: number; top_action_type: string | null; total_opportunity_cost: number; safe_to_wait_count: number; summary: string | null; }
interface Action { id: string; action_type: string; action_key: string; expected_upside: number; cost_of_delay: number; urgency: number; confidence: number; composite_rank: number; rank_position: number; safe_to_wait: boolean; explanation: string | null; }

export default function OpportunityCostPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [actions, setActions] = useState<Action[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch(`/api/v1/brands/${brandId}/opportunity-cost`),
      apiFetch(`/api/v1/brands/${brandId}/opportunity-cost/ranked-actions`),
    ]).then(([r, a]) => { setReports(r); setActions(a); }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const latest = reports[0];

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Opportunity-Cost Ranking</h1>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <>
          {latest && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: "Total Actions", value: latest.total_actions },
                { label: "Opp. Cost / Day", value: `$${latest.total_opportunity_cost.toFixed(0)}`, color: "text-red-400" },
                { label: "Safe to Wait", value: latest.safe_to_wait_count, color: "text-green-400" },
                { label: "Top Priority", value: latest.top_action_type || "—", color: "text-amber-400" },
              ].map((s, i) => (
                <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                  <p className="text-gray-500 text-xs uppercase">{s.label}</p>
                  <p className={`text-xl font-bold mt-1 ${s.color || "text-white"}`}>{s.value}</p>
                </div>
              ))}
            </div>
          )}
          <h2 className="text-lg font-semibold text-white">Ranked Actions</h2>
          <div className="overflow-x-auto"><table className="w-full text-sm text-left">
            <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">#</th><th className="py-2 px-3">Action</th><th className="py-2 px-3">Upside</th><th className="py-2 px-3">Delay Cost</th><th className="py-2 px-3">Urgency</th><th className="py-2 px-3">Rank</th><th className="py-2 px-3">Wait?</th></tr></thead>
            <tbody>{actions.map(a => (
              <tr key={a.id} className="border-b border-gray-800/50 text-gray-300">
                <td className="py-2 px-3 font-medium">{a.rank_position}</td>
                <td className="py-2 px-3"><span className="text-amber-400 text-xs">{a.action_type}</span><br/><span className="text-gray-500 text-xs">{a.action_key}</span></td>
                <td className="py-2 px-3">{(a.expected_upside * 100).toFixed(0)}%</td>
                <td className="py-2 px-3 text-red-400">${a.cost_of_delay.toFixed(0)}/day</td>
                <td className="py-2 px-3">{(a.urgency * 100).toFixed(0)}%</td>
                <td className="py-2 px-3 font-medium">{(a.composite_rank * 100).toFixed(0)}</td>
                <td className="py-2 px-3">{a.safe_to_wait ? <span className="text-green-400 text-xs">Yes</span> : <span className="text-red-400 text-xs">No</span>}</td>
              </tr>
            ))}</tbody>
          </table>{actions.length === 0 && <p className="text-gray-500 mt-4">No ranked actions yet. Run recompute.</p>}</div>
        </>
      )}
    </div>
  );
}
