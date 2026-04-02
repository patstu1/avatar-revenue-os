"use client";
import { useEffect, useState } from "react";
import { useAuthStore } from "@/lib/store";
const API = process.env.NEXT_PUBLIC_API_URL ?? (typeof window !== "undefined" ? window.location.origin : "http://localhost:8001");
function getAuthHeaders(): Record<string, string> {
  const token = typeof window !== "undefined" ? localStorage.getItem("aro_token") : null;
  return { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) };
}
async function apiFetch(path: string) { const r = await fetch(`${API}${path}`, { headers: getAuthHeaders() }); if (!r.ok) throw new Error(await r.text()); return r.json(); }
async function apiPost(path: string) { const r = await fetch(`${API}${path}`, { method: "POST", headers: getAuthHeaders() }); if (!r.ok) throw new Error(await r.text()); return r.json(); }

interface GovernanceRule { id: string; rule_name: string; rule_type: string; threshold: number | null; action: string; enabled: boolean; description: string | null; }
interface BannedEntity { id: string; entity_type: string; entity_name: string; reason: string | null; banned_at: string; }
interface RiskFlag { id: string; partner_id: string; partner_name: string; flag_type: string; severity: string; detail: string | null; created_at: string; }
interface Partner { id: string; name: string; status: string; commission_rate: number | null; total_revenue: number | null; risk_score: number | null; }

export default function AffiliateGovernancePage() {
  const user = useAuthStore((s) => s.user);
  const orgId = user?.organization_id ?? "";
  const [tab, setTab] = useState<"rules" | "banned" | "risk" | "partners">("rules");
  const [rules, setRules] = useState<GovernanceRule[]>([]);
  const [banned, setBanned] = useState<BannedEntity[]>([]);
  const [riskFlags, setRiskFlags] = useState<RiskFlag[]>([]);
  const [partners, setPartners] = useState<Partner[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);

  const fetchAll = () => {
    if (!orgId) return;
    setLoading(true);
    Promise.all([
      apiFetch(`/api/v1/orgs/${orgId}/affiliate/governance-rules`),
      apiFetch(`/api/v1/orgs/${orgId}/affiliate/banned`),
      apiFetch(`/api/v1/orgs/${orgId}/affiliate/risk-flags`),
      apiFetch(`/api/v1/orgs/${orgId}/affiliate/partners`),
    ]).then(([r, b, f, p]) => { setRules(r); setBanned(b); setRiskFlags(f); setPartners(p); }).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(() => { fetchAll(); }, [orgId]);

  const handleRecompute = async () => {
    if (!orgId || recomputing) return;
    setRecomputing(true);
    try {
      await Promise.all([
        apiPost(`/api/v1/orgs/${orgId}/affiliate/governance-rules/recompute`),
        apiPost(`/api/v1/orgs/${orgId}/affiliate/risk-flags/recompute`),
      ]);
      fetchAll();
    } catch { /* silently handled */ } finally { setRecomputing(false); }
  };

  const severityColor: Record<string, string> = { critical: "text-red-400", high: "text-orange-400", medium: "text-yellow-400", low: "text-green-400" };
  const statusColor: Record<string, string> = { active: "text-green-400", suspended: "text-red-400", pending: "text-yellow-400", inactive: "text-gray-500" };

  if (!orgId) return <div className="p-6"><p className="text-gray-500">Loading organization...</p></div>;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Affiliate Governance</h1>
        <button onClick={handleRecompute} disabled={recomputing} className="px-4 py-2 rounded-lg text-sm font-medium bg-cyan-600 hover:bg-cyan-500 text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
          {recomputing ? "Recomputing…" : "Recompute"}
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-xl p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Rules</p>
          <p className="text-2xl font-bold text-white mt-1">{rules.length}</p>
          <p className="text-xs text-gray-500 mt-1">{rules.filter(r => r.enabled).length} active</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Banned</p>
          <p className="text-2xl font-bold text-red-400 mt-1">{banned.length}</p>
          <p className="text-xs text-gray-500 mt-1">entities blocked</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Risk Flags</p>
          <p className="text-2xl font-bold text-orange-400 mt-1">{riskFlags.length}</p>
          <p className="text-xs text-gray-500 mt-1">{riskFlags.filter(f => f.severity === "critical").length} critical</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Partners</p>
          <p className="text-2xl font-bold text-cyan-400 mt-1">{partners.length}</p>
          <p className="text-xs text-gray-500 mt-1">{partners.filter(p => p.status === "active").length} active</p>
        </div>
      </div>

      <div className="flex gap-2">
        {([
          { key: "rules" as const, label: `Rules (${rules.length})` },
          { key: "banned" as const, label: `Banned (${banned.length})` },
          { key: "risk" as const, label: `Risk Flags (${riskFlags.length})` },
          { key: "partners" as const, label: `Partners (${partners.length})` },
        ]).map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} className={`px-4 py-2 rounded-lg text-sm font-medium ${tab === t.key ? "bg-cyan-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>{t.label}</button>
        ))}
      </div>

      {loading ? <p className="text-gray-500">Loading…</p> : (
        <>
          {tab === "rules" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Rule</th><th className="py-2 px-3">Type</th><th className="py-2 px-3">Threshold</th><th className="py-2 px-3">Action</th><th className="py-2 px-3">Status</th><th className="py-2 px-3">Description</th></tr></thead>
              <tbody>{rules.map(r => (
                <tr key={r.id} className="border-b border-gray-800/50 text-gray-300">
                  <td className="py-2 px-3 font-medium text-cyan-400">{r.rule_name}</td>
                  <td className="py-2 px-3 uppercase text-xs">{r.rule_type}</td>
                  <td className="py-2 px-3 font-mono text-xs">{r.threshold ?? "—"}</td>
                  <td className="py-2 px-3 text-amber-400">{r.action}</td>
                  <td className="py-2 px-3">{r.enabled ? <span className="text-green-400 text-xs font-medium">Enabled</span> : <span className="text-gray-500 text-xs">Disabled</span>}</td>
                  <td className="py-2 px-3 text-gray-500 text-xs">{r.description || "—"}</td>
                </tr>
              ))}</tbody>
            </table>{rules.length === 0 && <p className="text-gray-500 mt-4">No governance rules configured. Run recompute to initialize.</p>}</div>
          )}

          {tab === "banned" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Entity</th><th className="py-2 px-3">Type</th><th className="py-2 px-3">Reason</th><th className="py-2 px-3">Banned At</th></tr></thead>
              <tbody>{banned.map(b => (
                <tr key={b.id} className="border-b border-gray-800/50 text-gray-300">
                  <td className="py-2 px-3 font-medium text-red-400">{b.entity_name}</td>
                  <td className="py-2 px-3 uppercase text-xs">{b.entity_type}</td>
                  <td className="py-2 px-3 text-gray-500 text-xs">{b.reason || "—"}</td>
                  <td className="py-2 px-3 text-gray-500 text-xs">{new Date(b.banned_at).toLocaleDateString()}</td>
                </tr>
              ))}</tbody>
            </table>{banned.length === 0 && <p className="text-gray-500 mt-4">No banned entities.</p>}</div>
          )}

          {tab === "risk" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Partner</th><th className="py-2 px-3">Flag Type</th><th className="py-2 px-3">Severity</th><th className="py-2 px-3">Detail</th><th className="py-2 px-3">Created</th></tr></thead>
              <tbody>{riskFlags.map(f => (
                <tr key={f.id} className="border-b border-gray-800/50 text-gray-300">
                  <td className="py-2 px-3 font-medium text-cyan-400">{f.partner_name}</td>
                  <td className="py-2 px-3 uppercase text-xs">{f.flag_type}</td>
                  <td className={`py-2 px-3 font-medium text-xs uppercase ${severityColor[f.severity] || "text-gray-500"}`}>{f.severity}</td>
                  <td className="py-2 px-3 text-gray-500 text-xs">{f.detail || "—"}</td>
                  <td className="py-2 px-3 text-gray-500 text-xs">{new Date(f.created_at).toLocaleDateString()}</td>
                </tr>
              ))}</tbody>
            </table>{riskFlags.length === 0 && <p className="text-gray-500 mt-4">No risk flags detected. Run recompute to scan.</p>}</div>
          )}

          {tab === "partners" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Partner</th><th className="py-2 px-3">Status</th><th className="py-2 px-3">Commission</th><th className="py-2 px-3">Revenue</th><th className="py-2 px-3">Risk Score</th></tr></thead>
              <tbody>{partners.map(p => (
                <tr key={p.id} className="border-b border-gray-800/50 text-gray-300">
                  <td className="py-2 px-3 font-medium text-cyan-400">{p.name}</td>
                  <td className={`py-2 px-3 text-xs font-medium uppercase ${statusColor[p.status] || "text-gray-500"}`}>{p.status}</td>
                  <td className="py-2 px-3 font-mono text-xs">{p.commission_rate != null ? `${(p.commission_rate * 100).toFixed(1)}%` : "—"}</td>
                  <td className="py-2 px-3 font-mono text-xs">{p.total_revenue != null ? `$${p.total_revenue.toLocaleString()}` : "—"}</td>
                  <td className="py-2 px-3">{p.risk_score != null ? (
                    <span className={`font-mono text-xs font-medium ${p.risk_score >= 75 ? "text-red-400" : p.risk_score >= 50 ? "text-orange-400" : p.risk_score >= 25 ? "text-yellow-400" : "text-green-400"}`}>{p.risk_score}</span>
                  ) : <span className="text-gray-500 text-xs">—</span>}</td>
                </tr>
              ))}</tbody>
            </table>{partners.length === 0 && <p className="text-gray-500 mt-4">No affiliate partners found.</p>}</div>
          )}
        </>
      )}
    </div>
  );
}
