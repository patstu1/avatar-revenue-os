"use client";
import { useEffect, useState } from "react";
import { useAuthStore } from "@/lib/store";
import { apiFetch, brandsApi } from "@/lib/api";

interface Report { id: string; content_item_id: string; total_score: number; verdict: string; publish_allowed: boolean; confidence: number; reasons: string[] | null; }
interface Block { id: string; content_item_id: string; block_reason: string; severity: string; }

const verdictColor: Record<string, string> = { pass: "bg-green-900 text-green-300", warn: "bg-yellow-900 text-yellow-300", fail: "bg-red-900 text-red-300" };

export default function QualityGovernorPage() {
  const [tab, setTab] = useState<"reports" | "blocks">("reports");
  const [reports, setReports] = useState<Report[]>([]);
  const [blocks, setBlocks] = useState<Block[]>([]);
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
    Promise.all([
      apiFetch<any>(`/api/v1/brands/${brandId}/quality-governor`),
      apiFetch<any>(`/api/v1/brands/${brandId}/quality-governor/blocks`),
    ]).then(([r, b]) => { setReports(r); setBlocks(b); }).catch(() => {}).finally(() => setLoading(false));
  }, [brandId]);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Quality Governor</h1>
      <div className="flex items-center gap-3">
        <label className="text-sm text-gray-400">Brand:</label>
        <select aria-label="Brand" className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white" value={brandId} onChange={e => setBrandId(e.target.value)}>
          {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </div>
      <div className="flex gap-2">
        {[{key: "reports" as const, label: `Reports (${reports.length})`}, {key: "blocks" as const, label: `Blocks (${blocks.length})`}].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} className={`px-4 py-2 rounded-lg text-sm font-medium ${tab === t.key ? "bg-amber-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>{t.label}</button>
        ))}
      </div>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <>
          {tab === "reports" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Content</th><th className="py-2 px-3">Score</th><th className="py-2 px-3">Verdict</th><th className="py-2 px-3">Publish</th><th className="py-2 px-3">Confidence</th></tr></thead>
              <tbody>{reports.map(r => (
                <tr key={r.id} className="border-b border-gray-800/50 text-gray-300">
                  <td className="py-2 px-3 font-mono text-xs">{r.content_item_id.slice(0, 8)}…</td>
                  <td className="py-2 px-3">{(r.total_score * 100).toFixed(0)}%</td>
                  <td className="py-2 px-3"><span className={`px-2 py-0.5 rounded text-xs ${verdictColor[r.verdict] || "bg-gray-700 text-gray-400"}`}>{r.verdict}</span></td>
                  <td className="py-2 px-3">{r.publish_allowed ? <span className="text-green-400">Yes</span> : <span className="text-red-400">Blocked</span>}</td>
                  <td className="py-2 px-3">{(r.confidence * 100).toFixed(0)}%</td>
                </tr>
              ))}</tbody>
            </table>{reports.length === 0 && <p className="text-gray-500 mt-4">No quality reports yet.</p>}</div>
          )}
          {tab === "blocks" && (
            <div className="space-y-3">{blocks.map(b => (
              <div key={b.id} className="bg-red-950 border border-red-800 rounded-lg p-4">
                <p className="text-red-300 font-medium">{b.block_reason}</p>
                <p className="text-gray-500 text-xs mt-1">Severity: {b.severity} | Content: {b.content_item_id.slice(0, 8)}…</p>
              </div>
            ))}{blocks.length === 0 && <p className="text-gray-500">No quality blocks.</p>}</div>
          )}
        </>
      )}
    </div>
  );
}
