"use client";
import { useEffect, useState } from "react";
import { apiFetch, brandsApi } from "@/lib/api";

interface Opp { id: string; topic: string; source: string; velocity_score: number; novelty_score: number; revenue_potential_score: number; opportunity_type: string; recommended_platform: string | null; recommended_content_form: string | null; recommended_monetization: string | null; urgency: number; confidence: number; composite_score: number; truth_label: string; status: string; }

const typeColor: Record<string, string> = { monetization: "bg-green-900 text-green-300", pure_reach: "bg-cyan-900 text-cyan-300", authority_building: "bg-purple-900 text-purple-300", growth: "bg-blue-900 text-blue-300", community_engagement: "bg-yellow-900 text-yellow-300" };

export default function TrendViralPage() {
  const [brandId, setBrandId] = useState("");
  const [brands, setBrands] = useState<{id: string; name: string}[]>([]);
  const [opps, setOpps] = useState<Opp[]>([]); const [loading, setLoading] = useState(true);

  useEffect(() => {
    brandsApi.list().then((r) => {
      const list = r.data ?? r;
      setBrands(Array.isArray(list) ? list : []);
      if (Array.isArray(list) && list.length > 0) setBrandId(list[0].id);
    }).catch(() => {});
  }, []);

  useEffect(() => { if (!brandId) return; setLoading(true); apiFetch<any>(`/api/v1/brands/${brandId}/viral-opportunities`).then(setOpps).catch(() => {}).finally(() => setLoading(false)); }, [brandId]);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Trend / Viral Opportunity Engine</h1>
      <div className="flex items-center gap-3">
        <label className="text-sm text-gray-400">Brand:</label>
        <select aria-label="Select brand" className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white" value={brandId} onChange={e => setBrandId(e.target.value)}>
          {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </div>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <div className="space-y-3">
          {opps.map(o => (
            <div key={o.id} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
              <div className="flex justify-between items-start mb-2">
                <div>
                  <span className={`px-2 py-0.5 rounded text-xs mr-2 ${typeColor[o.opportunity_type] || "bg-gray-700 text-gray-400"}`}>{o.opportunity_type}</span>
                  <span className="text-white font-medium">{o.topic}</span>
                </div>
                <div className="text-right">
                  <span className="text-amber-400 font-bold text-lg">{(o.composite_score * 100).toFixed(0)}</span>
                  <p className="text-gray-500 text-xs">{(o.urgency * 100).toFixed(0)}% urgent</p>
                </div>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-xs mt-2">
                <div><span className="text-gray-500">Platform</span><p className="text-cyan-400">{o.recommended_platform || "—"}</p></div>
                <div><span className="text-gray-500">Form</span><p className="text-white">{o.recommended_content_form || "—"}</p></div>
                <div><span className="text-gray-500">Monetize</span><p className={o.recommended_monetization?.includes("none") ? "text-gray-500" : "text-green-400"}>{o.recommended_monetization || "—"}</p></div>
                <div><span className="text-gray-500">Revenue</span><p className="text-white">{(o.revenue_potential_score * 100).toFixed(0)}%</p></div>
                <div><span className="text-gray-500">Truth</span><p className="text-gray-500">{o.truth_label}</p></div>
              </div>
            </div>
          ))}
          {opps.length === 0 && <p className="text-gray-500">No viral opportunities yet. Run recompute or wait for scan.</p>}
        </div>
      )}
    </div>
  );
}
