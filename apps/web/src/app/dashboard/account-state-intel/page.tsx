"use client";
import { useEffect, useState } from "react";
import { useAuthStore } from "@/lib/store";
import { apiFetch, brandsApi } from "@/lib/api";

interface StateReport { id: string; account_id: string; current_state: string; confidence: number; next_best_move: string | null; monetization_intensity: string; posting_cadence: string; expansion_eligible: boolean; explanation: string | null; }

const stateColors: Record<string, string> = {
  newborn: "bg-blue-900 text-blue-300", warming: "bg-yellow-900 text-yellow-300", early_signal: "bg-cyan-900 text-cyan-300",
  scaling: "bg-green-900 text-green-300", monetizing: "bg-emerald-900 text-emerald-300", authority_building: "bg-purple-900 text-purple-300",
  trust_repair: "bg-orange-900 text-orange-300", saturated: "bg-gray-700 text-gray-300", cooling: "bg-gray-600 text-gray-400",
  weak: "bg-red-900 text-red-300", suppressed: "bg-red-800 text-red-400", blocked: "bg-red-700 text-red-400",
};

export default function AccountStateIntelPage() {
  const [reports, setReports] = useState<StateReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [brandId, setBrandId] = useState("");
  const [brands, setBrands] = useState<{id: string; name: string}[]>([]);

  useEffect(() => {
    brandsApi.list().then((r) => {
      const list = r.data ?? r;
      setBrands(Array.isArray(list) ? list : []);
      if (Array.isArray(list) && list.length > 0) setBrandId(list[0].id);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!brandId) return;
    apiFetch<any>(`/api/v1/brands/${brandId}/account-state`).then(setReports).catch(() => {}).finally(() => setLoading(false));
  }, [brandId]);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Account-State Intelligence</h1>
      <div className="flex items-center gap-3">
        <label className="text-sm text-gray-400">Brand:</label>
        <select aria-label="Select brand" className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white" value={brandId} onChange={e => setBrandId(e.target.value)}>
          {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </div>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {reports.map(r => (
            <div key={r.id} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
              <div className="flex justify-between items-center mb-3">
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${stateColors[r.current_state] || "bg-gray-700 text-gray-400"}`}>{r.current_state}</span>
                <span className="text-gray-500 text-xs">{(r.confidence * 100).toFixed(0)}% conf</span>
              </div>
              <p className="text-white text-sm font-medium truncate">{r.account_id.slice(0, 8)}…</p>
              <p className="text-gray-400 text-xs mt-1">{r.explanation}</p>
              <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                <div><span className="text-gray-500">Monetization</span><p className="text-white">{r.monetization_intensity}</p></div>
                <div><span className="text-gray-500">Cadence</span><p className="text-white">{r.posting_cadence}</p></div>
                <div><span className="text-gray-500">Expand</span><p className={r.expansion_eligible ? "text-green-400" : "text-gray-500"}>{r.expansion_eligible ? "Yes" : "No"}</p></div>
              </div>
              {r.next_best_move && <p className="text-amber-400 text-xs mt-2">{r.next_best_move}</p>}
            </div>
          ))}
          {reports.length === 0 && <p className="text-gray-500 col-span-3">No account states yet. Run recompute.</p>}
        </div>
      )}
    </div>
  );
}
