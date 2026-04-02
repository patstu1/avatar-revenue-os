"use client";
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const brandId = "00000000-0000-0000-0000-000000000001";
async function apiFetch(path: string) { const r = await fetch(`${API}${path}`, { credentials: "include", headers: { "Content-Type": "application/json" } }); if (!r.ok) throw new Error(await r.text()); return r.json(); }

interface FFReport { id: string; family_type: string; family_key: string; failure_count: number; avg_fail_score: number; recommended_alternative: string | null; explanation: string | null; }
interface Rule { id: string; family_type: string; family_key: string; suppression_mode: string; retest_after_days: number; reason: string | null; is_active: boolean; }

export default function FailureFamiliesPage() {
  const [tab, setTab] = useState<"families" | "rules">("families");
  const [families, setFamilies] = useState<FFReport[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch(`/api/v1/brands/${brandId}/failure-families`),
      apiFetch(`/api/v1/brands/${brandId}/suppression-rules`),
    ]).then(([f, r]) => { setFamilies(f); setRules(r); }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Failure-Family Suppression</h1>
      <div className="flex gap-2">
        {[{key: "families" as const, label: `Failure Families (${families.length})`}, {key: "rules" as const, label: `Suppression Rules (${rules.length})`}].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} className={`px-4 py-2 rounded-lg text-sm font-medium ${tab === t.key ? "bg-red-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>{t.label}</button>
        ))}
      </div>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <>
          {tab === "families" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Type</th><th className="py-2 px-3">Key</th><th className="py-2 px-3">Failures</th><th className="py-2 px-3">Avg Score</th><th className="py-2 px-3">Alternative</th></tr></thead>
              <tbody>{families.map(f => (
                <tr key={f.id} className="border-b border-gray-800/50 text-gray-300">
                  <td className="py-2 px-3"><span className="text-red-400 text-xs">{f.family_type}</span></td>
                  <td className="py-2 px-3 font-medium">{f.family_key}</td>
                  <td className="py-2 px-3">{f.failure_count}</td>
                  <td className="py-2 px-3">{(f.avg_fail_score * 100).toFixed(0)}%</td>
                  <td className="py-2 px-3 text-green-400 text-xs">{f.recommended_alternative || "—"}</td>
                </tr>
              ))}</tbody>
            </table>{families.length === 0 && <p className="text-gray-500 mt-4">No failure families detected.</p>}</div>
          )}
          {tab === "rules" && (
            <div className="space-y-3">{rules.map(r => (
              <div key={r.id} className="bg-red-950 border border-red-800 rounded-lg p-4">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-red-300 font-medium">{r.family_type}: {r.family_key}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${r.suppression_mode === "persistent" ? "bg-red-800 text-red-300" : "bg-yellow-900 text-yellow-300"}`}>{r.suppression_mode}</span>
                </div>
                <p className="text-gray-400 text-sm">{r.reason}</p>
                <p className="text-gray-600 text-xs mt-1">Retest after {r.retest_after_days} days</p>
              </div>
            ))}{rules.length === 0 && <p className="text-gray-500">No active suppression rules.</p>}</div>
          )}
        </>
      )}
    </div>
  );
}
