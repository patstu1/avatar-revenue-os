"use client";
import { useEffect, useState } from "react";
import { brandsApi } from "@/lib/api";

const API = process.env.NEXT_PUBLIC_API_URL ?? (typeof window !== "undefined" ? window.location.origin : "http://localhost:8001");

function getAuthHeaders(): Record<string, string> {
  const token = typeof window !== "undefined" ? localStorage.getItem("aro_token") : null;
  return { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) };
}

async function apiFetch(path: string) {
  const res = await fetch(`${API}${path}`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

interface Report { id: string; total_budget: number; allocated_budget: number; experiment_reserve: number; hero_spend: number; bulk_spend: number; target_count: number; starved_count: number; }
interface Decision { id: string; allocated_budget: number; allocated_volume: number; provider_tier: string; allocation_pct: number; starved: boolean; explanation: string | null; }

export default function CapitalAllocationPage() {
  const [brandId, setBrandId] = useState("");
  const [brands, setBrands] = useState<{id: string; name: string}[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    brandsApi.list().then((r) => {
      const list = r.data ?? r;
      setBrands(Array.isArray(list) ? list : []);
      if (Array.isArray(list) && list.length > 0) setBrandId(list[0].id);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!brandId) return;
    setLoading(true);
    Promise.all([
      apiFetch(`/api/v1/brands/${brandId}/capital-allocation`),
      apiFetch(`/api/v1/brands/${brandId}/capital-allocation/decisions`),
    ]).then(([r, d]) => { setReports(r); setDecisions(d); }).catch(() => {}).finally(() => setLoading(false));
  }, [brandId]);

  const latest = reports[0];

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Portfolio Capital Allocator</h1>
      <div className="flex items-center gap-3">
        <label className="text-sm text-gray-400">Brand:</label>
        <select aria-label="Select brand" className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white" value={brandId} onChange={e => setBrandId(e.target.value)}>
          {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </div>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <>
          {latest && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: "Total Budget", value: `$${latest.total_budget.toFixed(0)}` },
                { label: "Hero Spend", value: `$${latest.hero_spend.toFixed(0)}`, color: "text-amber-400" },
                { label: "Bulk Spend", value: `$${latest.bulk_spend.toFixed(0)}` },
                { label: "Experiment Reserve", value: `$${latest.experiment_reserve.toFixed(0)}`, color: "text-blue-400" },
                { label: "Targets", value: latest.target_count },
                { label: "Starved", value: latest.starved_count, color: "text-red-400" },
              ].map((s, i) => (
                <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                  <p className="text-gray-500 text-xs uppercase">{s.label}</p>
                  <p className={`text-xl font-bold mt-1 ${s.color || "text-white"}`}>{s.value}</p>
                </div>
              ))}
            </div>
          )}
          <h2 className="text-lg font-semibold text-white mt-6">Allocation Decisions</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800">
                <tr><th className="py-2 px-3">Allocation %</th><th className="py-2 px-3">Budget</th><th className="py-2 px-3">Volume</th><th className="py-2 px-3">Tier</th><th className="py-2 px-3">Status</th><th className="py-2 px-3">Details</th></tr>
              </thead>
              <tbody>
                {decisions.map(d => (
                  <tr key={d.id} className="border-b border-gray-800/50 text-gray-300">
                    <td className="py-2 px-3 font-medium">{d.allocation_pct.toFixed(1)}%</td>
                    <td className="py-2 px-3">${d.allocated_budget.toFixed(2)}</td>
                    <td className="py-2 px-3">{d.allocated_volume}</td>
                    <td className="py-2 px-3"><span className={`px-2 py-0.5 rounded text-xs ${d.provider_tier === "hero" ? "bg-amber-900 text-amber-300" : "bg-gray-700 text-gray-400"}`}>{d.provider_tier}</span></td>
                    <td className="py-2 px-3">{d.starved ? <span className="text-red-400 text-xs">STARVED</span> : <span className="text-green-400 text-xs">Active</span>}</td>
                    <td className="py-2 px-3 text-gray-500 text-xs">{d.explanation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {decisions.length === 0 && <p className="text-gray-500 mt-4">No allocation decisions yet. Run recompute.</p>}
          </div>
        </>
      )}
    </div>
  );
}
