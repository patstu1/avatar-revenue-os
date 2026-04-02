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

interface LP { id: string; page_type: string; headline: string; status: string; publish_status: string; truth_label: string; destination_url: string | null; }
interface LPQ { id: string; total_score: number; trust_score: number; conversion_fit: number; verdict: string; }

export default function LandingPagesPage() {
  const [pages, setPages] = useState<LP[]>([]); const [quality, setQuality] = useState<LPQ[]>([]); const [loading, setLoading] = useState(true);
  const [brandId, setBrandId] = useState("");
  const [brands, setBrands] = useState<{id: string; name: string}[]>([]);
  useEffect(() => {
    brandsApi.list().then((r) => {
      const list = r.data ?? r;
      setBrands(Array.isArray(list) ? list : []);
      if (Array.isArray(list) && list.length > 0) setBrandId(list[0].id);
    }).catch(() => {});
  }, []);
  useEffect(() => { if (!brandId) return; Promise.all([apiFetch(`/api/v1/brands/${brandId}/landing-pages`), apiFetch(`/api/v1/brands/${brandId}/landing-page-quality`)]).then(([p, q]) => { setPages(p); setQuality(q); }).catch(() => {}).finally(() => setLoading(false)); }, [brandId]);

  const verdictColor: Record<string, string> = { pass: "text-green-400", warn: "text-yellow-400", fail: "text-red-400", unscored: "text-gray-500" };

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Landing Page Engine</h1>
      <div className="flex items-center gap-3">
        <label className="text-sm text-gray-400">Brand:</label>
        <select aria-label="Select brand" className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white" value={brandId} onChange={e => setBrandId(e.target.value)}>
          {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </div>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <div className="overflow-x-auto"><table className="w-full text-sm text-left">
          <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Type</th><th className="py-2 px-3">Headline</th><th className="py-2 px-3">Status</th><th className="py-2 px-3">Published</th><th className="py-2 px-3">Truth</th><th className="py-2 px-3">URL</th></tr></thead>
          <tbody>{pages.map(p => (
            <tr key={p.id} className="border-b border-gray-800/50 text-gray-300">
              <td className="py-2 px-3"><span className="text-cyan-400 text-xs">{p.page_type}</span></td>
              <td className="py-2 px-3 font-medium max-w-xs truncate">{p.headline}</td>
              <td className="py-2 px-3">{p.status}</td>
              <td className="py-2 px-3">{p.publish_status}</td>
              <td className="py-2 px-3 text-xs text-gray-500">{p.truth_label}</td>
              <td className="py-2 px-3 text-xs">{p.destination_url || <span className="text-gray-600">none</span>}</td>
            </tr>
          ))}</tbody>
        </table>{pages.length === 0 && <p className="text-gray-500 mt-4">No landing pages yet. Run recompute.</p>}</div>
      )}
      {quality.length > 0 && (
        <div className="mt-6">
          <h2 className="text-lg font-semibold text-white mb-3">Quality Reports</h2>
          <div className="grid gap-3 md:grid-cols-3">{quality.map(q => (
            <div key={q.id} className="bg-gray-900 border border-gray-800 rounded-lg p-3">
              <div className="flex justify-between"><span className={`font-bold ${verdictColor[q.verdict]}`}>{q.verdict.toUpperCase()}</span><span className="text-gray-500 text-xs">{(q.total_score * 100).toFixed(0)}%</span></div>
              <div className="mt-2 text-xs text-gray-400"><p>Trust: {(q.trust_score * 100).toFixed(0)}%</p><p>Conversion: {(q.conversion_fit * 100).toFixed(0)}%</p></div>
            </div>
          ))}</div>
        </div>
      )}
    </div>
  );
}
