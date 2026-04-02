"use client";
import { useEffect, useState } from "react";
import { brandsApi } from "@/lib/api";

const API = process.env.NEXT_PUBLIC_API_URL ?? (typeof window !== "undefined" ? window.location.origin : "http://localhost:8001");

function getAuthHeaders(): Record<string, string> {
  const token = typeof window !== "undefined" ? localStorage.getItem("aro_token") : null;
  return { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) };
}

async function apiFetch(path: string) { const r = await fetch(`${API}${path}`, { headers: getAuthHeaders() }); if (!r.ok) throw new Error(await r.text()); return r.json(); }

interface Offer { id: string; product_name: string; epc: number; conversion_rate: number; commission_rate: number; trust_score: number; rank_score: number; truth_label: string; }
interface Leak { id: string; leak_type: string; severity: string; revenue_loss_estimate: number; recommendation: string; }
interface Blocker { id: string; blocker_type: string; description: string; severity: string; }

export default function AffiliateIntelPage() {
  const [brandId, setBrandId] = useState("");
  const [brands, setBrands] = useState<{id: string; name: string}[]>([]);
  const [tab, setTab] = useState<"offers" | "leaks" | "blockers">("offers");
  const [offers, setOffers] = useState<Offer[]>([]); const [leaks, setLeaks] = useState<Leak[]>([]); const [blockers, setBlockers] = useState<Blocker[]>([]); const [loading, setLoading] = useState(true);

  useEffect(() => {
    brandsApi.list().then((r) => {
      const list = r.data ?? r;
      setBrands(Array.isArray(list) ? list : []);
      if (Array.isArray(list) && list.length > 0) setBrandId(list[0].id);
    }).catch(() => {});
  }, []);

  useEffect(() => { if (!brandId) return; setLoading(true); Promise.all([apiFetch(`/api/v1/brands/${brandId}/affiliate-offers`), apiFetch(`/api/v1/brands/${brandId}/affiliate-leaks`), apiFetch(`/api/v1/brands/${brandId}/affiliate-blockers`)]).then(([o, l, b]) => { setOffers(o); setLeaks(l); setBlockers(b); }).catch(() => {}).finally(() => setLoading(false)); }, [brandId]);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Affiliate Intelligence</h1>
      <div className="flex items-center gap-3">
        <label className="text-sm text-gray-400">Brand:</label>
        <select aria-label="Select brand" className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white" value={brandId} onChange={e => setBrandId(e.target.value)}>
          {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </div>
      <div className="flex gap-2">
        {[{key: "offers" as const, label: `Offers (${offers.length})`}, {key: "leaks" as const, label: `Leaks (${leaks.length})`}, {key: "blockers" as const, label: `Blockers (${blockers.length})`}].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} className={`px-4 py-2 rounded-lg text-sm font-medium ${tab === t.key ? "bg-amber-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>{t.label}</button>
        ))}
      </div>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <>
          {tab === "offers" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Product</th><th className="py-2 px-3">EPC</th><th className="py-2 px-3">CVR</th><th className="py-2 px-3">Commission</th><th className="py-2 px-3">Trust</th><th className="py-2 px-3">Rank</th></tr></thead>
              <tbody>{offers.map(o => (
                <tr key={o.id} className="border-b border-gray-800/50 text-gray-300">
                  <td className="py-2 px-3 font-medium">{o.product_name}</td>
                  <td className="py-2 px-3 text-cyan-400">${o.epc.toFixed(2)}</td>
                  <td className="py-2 px-3">{(o.conversion_rate * 100).toFixed(1)}%</td>
                  <td className="py-2 px-3">{o.commission_rate}%</td>
                  <td className="py-2 px-3">{(o.trust_score * 100).toFixed(0)}%</td>
                  <td className="py-2 px-3 font-bold text-amber-400">{(o.rank_score * 100).toFixed(0)}</td>
                </tr>
              ))}</tbody>
            </table>{offers.length === 0 && <p className="text-gray-500 mt-4">No affiliate offers yet.</p>}</div>
          )}
          {tab === "leaks" && (
            <div className="space-y-3">{leaks.map(l => (
              <div key={l.id} className="bg-red-950 border border-red-800 rounded-lg p-4">
                <div className="flex justify-between items-center mb-1"><span className="text-red-300 font-medium">{l.leak_type}</span><span className="text-red-400 text-sm">${l.revenue_loss_estimate.toFixed(0)} lost</span></div>
                <p className="text-gray-400 text-sm">{l.recommendation}</p>
              </div>
            ))}{leaks.length === 0 && <p className="text-gray-500">No leaks detected.</p>}</div>
          )}
          {tab === "blockers" && (
            <div className="space-y-3">{blockers.map(b => (
              <div key={b.id} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <span className="text-pink-400 font-medium">{b.blocker_type}</span>
                <p className="text-gray-400 text-sm mt-1">{b.description}</p>
              </div>
            ))}{blockers.length === 0 && <p className="text-gray-500">No affiliate blockers.</p>}</div>
          )}
        </>
      )}
    </div>
  );
}
