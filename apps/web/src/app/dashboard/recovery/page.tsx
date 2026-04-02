"use client";
import { useEffect, useState } from "react";
const API = process.env.NEXT_PUBLIC_API_URL ?? "https://app.nvironments.com";
const orgId = "00000000-0000-0000-0000-000000000001";
async function apiFetch(path: string) { const r = await fetch(`${API}${path}`, { credentials: "include", headers: { "Content-Type": "application/json" } }); if (!r.ok) throw new Error(await r.text()); return r.json(); }

interface Incident { id: string; incident_type: string; severity: string; affected_scope: string; detail: string; auto_recoverable: boolean; recovery_status: string; }

const sevColor: Record<string, string> = { critical: "bg-red-900 text-red-300 border-red-700", high: "bg-orange-900 text-orange-300 border-orange-700", medium: "bg-yellow-900 text-yellow-300 border-yellow-700" };
const statusColor: Record<string, string> = { auto_recovering: "text-cyan-400", escalated: "text-red-400", pending_review: "text-yellow-400", resolved: "text-green-400", open: "text-gray-400" };

export default function RecoveryPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]); const [loading, setLoading] = useState(true);
  useEffect(() => { apiFetch(`/api/v1/orgs/${orgId}/recovery/incidents`).then(setIncidents).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Recovery / Rollback Engine</h1>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <div className="space-y-3">
          {incidents.map(i => (
            <div key={i.id} className={`border rounded-lg p-4 ${sevColor[i.severity] || "bg-gray-900 border-gray-800"}`}>
              <div className="flex justify-between items-center mb-2">
                <div className="flex items-center gap-2"><span className="text-xs font-bold uppercase">{i.incident_type}</span><span className="text-xs opacity-70">({i.affected_scope})</span></div>
                <span className={`text-xs font-bold ${statusColor[i.recovery_status] || "text-gray-400"}`}>{i.recovery_status.toUpperCase()}</span>
              </div>
              <p className="text-sm">{i.detail}</p>
              <div className="mt-2 flex gap-3 text-xs opacity-70">
                <span>Auto: {i.auto_recoverable ? "Yes" : "No"}</span><span>Severity: {i.severity}</span>
              </div>
            </div>
          ))}
          {incidents.length === 0 && <p className="text-gray-500">No active recovery incidents. System healthy.</p>}
        </div>
      )}
    </div>
  );
}
