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

interface OLOffer { id: string; offer_name: string; offer_type: string; primary_angle: string | null; price_point: number; rank_score: number; confidence: number; status: string; truth_label: string; }
interface Blocker { id: string; blocker_type: string; description: string; recommendation: string | null; severity: string; }

export default function OfferLabPage() {
  const [tab, setTab] = useState<"offers" | "blockers">("offers");
  const [offers, setOffers] = useState<OLOffer[]>([]); const [blockers, setBlockers] = useState<Blocker[]>([]); const [loading, setLoading] = useState(true);
  const [brandId, setBrandId] = useState("");
  const [brands, setBrands] = useState<{id: string; name: string}[]>([]);

  useEffect(() => {
    brandsApi.list().then((r) => {
      const list = r.data ?? r;
      setBrands(Array.isArray(list) ? list : []);
      if (Array.isArray(list) && list.length > 0) setBrandId(list[0].id);
    }).catch(() => {});
  }, []);

  useEffect(() => { if (!brandId) return; Promise.all([apiFetch(`/api/v1/brands/${brandId}/offer-lab/offers`), apiFetch(`/api/v1/brands/${brandId}/offer-lab/blockers`)]).then(([o, b]) => { setOffers(o); setBlockers(b); }).catch(() => {}).finally(() => setLoading(false)); }, [brandId]);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Offer Lab</h1>
      <div className="flex items-center gap-3">
        <label className="text-sm text-gray-400">Brand:</label>
        <select aria-label="Brand" className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white" value={brandId} onChange={e => setBrandId(e.target.value)}>
          {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </div>
      <div className="flex gap-2">
        {[{key: "offers" as const, label: `Offers (${offers.length})`}, {key: "blockers" as const, label: `Blockers (${blockers.length})`}].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} className={`px-4 py-2 rounded-lg text-sm font-medium ${tab === t.key ? "bg-amber-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>{t.label}</button>
        ))}
      </div>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <>
          {tab === "offers" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Name</th><th className="py-2 px-3">Type</th><th className="py-2 px-3">Angle</th><th className="py-2 px-3">Price</th><th className="py-2 px-3">Rank</th><th className="py-2 px-3">Confidence</th><th className="py-2 px-3">Status</th></tr></thead>
              <tbody>{offers.map(o => (
                <tr key={o.id} className="border-b border-gray-800/50 text-gray-300">
                  <td className="py-2 px-3 font-medium">{o.offer_name}</td>
                  <td className="py-2 px-3 text-cyan-400 text-xs">{o.offer_type}</td>
                  <td className="py-2 px-3">{o.primary_angle || "—"}</td>
                  <td className="py-2 px-3">${o.price_point.toFixed(0)}</td>
                  <td className="py-2 px-3 font-bold text-amber-400">{(o.rank_score * 100).toFixed(0)}</td>
                  <td className="py-2 px-3">{(o.confidence * 100).toFixed(0)}%</td>
                  <td className="py-2 px-3 text-xs text-gray-500">{o.truth_label}</td>
                </tr>
              ))}</tbody>
            </table>{offers.length === 0 && <p className="text-gray-500 mt-4">No offer lab offers yet.</p>}</div>
          )}
          {tab === "blockers" && (
            <div className="space-y-3">{blockers.map(b => (
              <div key={b.id} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <div className="flex justify-between"><span className="text-pink-400 font-medium">{b.blocker_type}</span><span className="text-xs text-gray-500">{b.severity}</span></div>
                <p className="text-gray-400 text-sm mt-1">{b.description}</p>
                {b.recommendation && <p className="text-green-400 text-xs mt-1">{b.recommendation}</p>}
              </div>
            ))}{blockers.length === 0 && <p className="text-gray-500">No offer blockers.</p>}</div>
          )}
        </>
      )}
    </div>
  );
}
