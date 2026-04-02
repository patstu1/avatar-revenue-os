"use client";
import { useEffect, useState } from "react";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const orgId = "00000000-0000-0000-0000-000000000001";
async function apiFetch(path: string) { const r = await fetch(`${API}${path}`, { credentials: "include", headers: { "Content-Type": "application/json" } }); if (!r.ok) throw new Error(await r.text()); return r.json(); }

interface Role { id: string; role_name: string; role_level: number; description: string | null; is_system: boolean; }
interface Compliance { id: string; framework: string; control_id: string; control_name: string; status: string; }
interface Audit { id: string; action: string; resource_type: string; detail: string | null; }

export default function EnterpriseSecurityPage() {
  const [tab, setTab] = useState<"roles" | "compliance" | "audit">("roles");
  const [roles, setRoles] = useState<Role[]>([]); const [compliance, setCompliance] = useState<Compliance[]>([]); const [audit, setAudit] = useState<Audit[]>([]); const [loading, setLoading] = useState(true);
  useEffect(() => {
    Promise.all([
      apiFetch(`/api/v1/orgs/${orgId}/security/roles`),
      apiFetch(`/api/v1/orgs/${orgId}/security/compliance`),
      apiFetch(`/api/v1/orgs/${orgId}/security/audit-trail`),
    ]).then(([r, c, a]) => { setRoles(r); setCompliance(c); setAudit(a); }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const statusColor: Record<string, string> = { met: "text-green-400", not_met: "text-red-400", not_assessed: "text-gray-500" };

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Enterprise Security + Compliance</h1>
      <div className="flex gap-2">
        {[{key: "roles" as const, label: `Roles (${roles.length})`}, {key: "compliance" as const, label: `Compliance (${compliance.length})`}, {key: "audit" as const, label: `Audit Trail (${audit.length})`}].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} className={`px-4 py-2 rounded-lg text-sm font-medium ${tab === t.key ? "bg-cyan-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>{t.label}</button>
        ))}
      </div>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <>
          {tab === "roles" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Role</th><th className="py-2 px-3">Level</th><th className="py-2 px-3">System</th><th className="py-2 px-3">Description</th></tr></thead>
              <tbody>{roles.map(r => (
                <tr key={r.id} className="border-b border-gray-800/50 text-gray-300">
                  <td className="py-2 px-3 font-medium text-cyan-400">{r.role_name}</td>
                  <td className="py-2 px-3">{r.role_level}</td>
                  <td className="py-2 px-3">{r.is_system ? <span className="text-green-400 text-xs">Yes</span> : <span className="text-gray-500 text-xs">Custom</span>}</td>
                  <td className="py-2 px-3 text-gray-500">{r.description}</td>
                </tr>
              ))}</tbody>
            </table>{roles.length === 0 && <p className="text-gray-500 mt-4">No roles configured. Run seed.</p>}</div>
          )}
          {tab === "compliance" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Framework</th><th className="py-2 px-3">Control</th><th className="py-2 px-3">Name</th><th className="py-2 px-3">Status</th></tr></thead>
              <tbody>{compliance.map(c => (
                <tr key={c.id} className="border-b border-gray-800/50 text-gray-300">
                  <td className="py-2 px-3 uppercase text-xs text-cyan-400">{c.framework}</td>
                  <td className="py-2 px-3 font-mono text-xs">{c.control_id}</td>
                  <td className="py-2 px-3">{c.control_name}</td>
                  <td className={`py-2 px-3 font-medium ${statusColor[c.status] || "text-gray-500"}`}>{c.status.toUpperCase()}</td>
                </tr>
              ))}</tbody>
            </table>{compliance.length === 0 && <p className="text-gray-500 mt-4">No compliance controls assessed. Run recompute.</p>}</div>
          )}
          {tab === "audit" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Action</th><th className="py-2 px-3">Resource</th><th className="py-2 px-3">Detail</th></tr></thead>
              <tbody>{audit.map(a => (
                <tr key={a.id} className="border-b border-gray-800/50 text-gray-300">
                  <td className="py-2 px-3 text-amber-400">{a.action}</td>
                  <td className="py-2 px-3">{a.resource_type}</td>
                  <td className="py-2 px-3 text-gray-500 text-xs">{a.detail || "—"}</td>
                </tr>
              ))}</tbody>
            </table>{audit.length === 0 && <p className="text-gray-500 mt-4">No audit events yet.</p>}</div>
          )}
        </>
      )}
    </div>
  );
}
