"use client";
import { useEffect, useState } from "react";
const API = process.env.NEXT_PUBLIC_API_URL ?? "https://app.nvironments.com";
const brandId = "00000000-0000-0000-0000-000000000001";
async function apiFetch(path: string) { const r = await fetch(`${API}${path}`, { credentials: "include", headers: { "Content-Type": "application/json" } }); if (!r.ok) throw new Error(await r.text()); return r.json(); }

interface Camp { id: string; campaign_type: string; campaign_name: string; objective: string; budget_tier: string; expected_upside: number; confidence: number; launch_status: string; truth_label: string; }
interface Blocker { id: string; blocker_type: string; description: string; severity: string; }

export default function CampaignsPage() {
  const [tab, setTab] = useState<"campaigns" | "blockers">("campaigns");
  const [camps, setCamps] = useState<Camp[]>([]); const [blockers, setBlockers] = useState<Blocker[]>([]); const [loading, setLoading] = useState(true);
  useEffect(() => { Promise.all([apiFetch(`/api/v1/brands/${brandId}/campaigns`), apiFetch(`/api/v1/brands/${brandId}/campaign-blockers`)]).then(([c, b]) => { setCamps(c); setBlockers(b); }).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Campaign Constructor</h1>
      <div className="flex gap-2">
        {[{key: "campaigns" as const, label: `Campaigns (${camps.length})`}, {key: "blockers" as const, label: `Blockers (${blockers.length})`}].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} className={`px-4 py-2 rounded-lg text-sm font-medium ${tab === t.key ? "bg-amber-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>{t.label}</button>
        ))}
      </div>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <>
          {tab === "campaigns" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Type</th><th className="py-2 px-3">Name</th><th className="py-2 px-3">Tier</th><th className="py-2 px-3">Upside</th><th className="py-2 px-3">Confidence</th><th className="py-2 px-3">Status</th><th className="py-2 px-3">Truth</th></tr></thead>
              <tbody>{camps.map(c => (
                <tr key={c.id} className="border-b border-gray-800/50 text-gray-300">
                  <td className="py-2 px-3"><span className="text-cyan-400 text-xs">{c.campaign_type}</span></td>
                  <td className="py-2 px-3 font-medium">{c.campaign_name}</td>
                  <td className="py-2 px-3"><span className={`px-2 py-0.5 rounded text-xs ${c.budget_tier === "hero" ? "bg-amber-900 text-amber-300" : "bg-gray-700 text-gray-400"}`}>{c.budget_tier}</span></td>
                  <td className="py-2 px-3">${c.expected_upside.toFixed(0)}</td>
                  <td className="py-2 px-3">{(c.confidence * 100).toFixed(0)}%</td>
                  <td className="py-2 px-3">{c.launch_status}</td>
                  <td className="py-2 px-3 text-xs text-gray-500">{c.truth_label}</td>
                </tr>
              ))}</tbody>
            </table>{camps.length === 0 && <p className="text-gray-500 mt-4">No campaigns yet. Run recompute.</p>}</div>
          )}
          {tab === "blockers" && (
            <div className="space-y-3">{blockers.map(b => (
              <div key={b.id} className="bg-red-950 border border-red-800 rounded-lg p-4">
                <div className="flex justify-between items-center mb-1"><span className="text-red-300 font-medium">{b.blocker_type}</span><span className={`text-xs px-2 py-0.5 rounded ${b.severity === "critical" ? "bg-red-800 text-red-300" : "bg-yellow-900 text-yellow-300"}`}>{b.severity}</span></div>
                <p className="text-gray-400 text-sm">{b.description}</p>
              </div>
            ))}{blockers.length === 0 && <p className="text-gray-500">No campaign blockers.</p>}</div>
          )}
        </>
      )}
    </div>
  );
}
