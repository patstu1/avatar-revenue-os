"use client";
import { useEffect, useState } from "react";
import { useAuthStore } from "@/lib/store";
import { apiFetch, brandsApi } from "@/lib/api";

interface Rule { id: string; rule_type: string; rule_key: string; severity: string; explanation: string | null; }
interface Violation { id: string; violation_type: string; severity: string; detail: string; }

export default function BrandGovernancePage() {
  const [tab, setTab] = useState<"rules" | "violations">("rules");
  const [rules, setRules] = useState<Rule[]>([]); const [violations, setViolations] = useState<Violation[]>([]); const [loading, setLoading] = useState(true);
  const [brandId, setBrandId] = useState("");
  const [brands, setBrands] = useState<{id: string; name: string}[]>([]);
  useEffect(() => {
    brandsApi.list().then((r) => {
      const list = r.data ?? r;
      setBrands(Array.isArray(list) ? list : []);
      if (Array.isArray(list) && list.length > 0) setBrandId(list[0].id);
    }).catch(() => {});
  }, []);
  useEffect(() => { if (!brandId) return; Promise.all([apiFetch<any>(`/api/v1/brands/${brandId}/governance-voice-rules`), apiFetch<any>(`/api/v1/brands/${brandId}/governance-violations`)]).then(([r, v]) => { setRules(r); setViolations(v); }).catch(() => {}).finally(() => setLoading(false)); }, [brandId]);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Brand Governance OS</h1>
      <div className="flex items-center gap-3">
        <label className="text-sm text-gray-400">Brand:</label>
        <select aria-label="Select brand" className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white" value={brandId} onChange={e => setBrandId(e.target.value)}>
          {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </div>
      <div className="flex gap-2">
        {[{key: "rules" as const, label: `Voice Rules (${rules.length})`}, {key: "violations" as const, label: `Violations (${violations.length})`}].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} className={`px-4 py-2 rounded-lg text-sm font-medium ${tab === t.key ? "bg-cyan-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>{t.label}</button>
        ))}
      </div>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <>
          {tab === "rules" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Type</th><th className="py-2 px-3">Key</th><th className="py-2 px-3">Severity</th><th className="py-2 px-3">Explanation</th></tr></thead>
              <tbody>{rules.map(r => (
                <tr key={r.id} className="border-b border-gray-800/50 text-gray-300">
                  <td className="py-2 px-3"><span className="text-cyan-400 text-xs">{r.rule_type}</span></td>
                  <td className="py-2 px-3 font-medium">{r.rule_key}</td>
                  <td className="py-2 px-3"><span className={`text-xs px-2 py-0.5 rounded ${r.severity === "hard" ? "bg-red-900 text-red-300" : "bg-yellow-900 text-yellow-300"}`}>{r.severity}</span></td>
                  <td className="py-2 px-3 text-gray-500 text-xs">{r.explanation || "—"}</td>
                </tr>
              ))}</tbody>
            </table>{rules.length === 0 && <p className="text-gray-500 mt-4">No voice rules configured.</p>}</div>
          )}
          {tab === "violations" && (
            <div className="space-y-3">{violations.map(v => (
              <div key={v.id} className={`border rounded-lg p-4 ${v.severity === "hard" ? "bg-red-950 border-red-800" : "bg-yellow-950 border-yellow-800"}`}>
                <div className="flex justify-between items-center mb-1"><span className={`font-medium ${v.severity === "hard" ? "text-red-300" : "text-yellow-300"}`}>{v.violation_type}</span><span className="text-xs text-gray-500">{v.severity}</span></div>
                <p className="text-gray-400 text-sm">{v.detail}</p>
              </div>
            ))}{violations.length === 0 && <p className="text-gray-500">No governance violations.</p>}</div>
          )}
        </>
      )}
    </div>
  );
}
