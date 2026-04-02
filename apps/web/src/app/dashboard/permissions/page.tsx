"use client";
import { useEffect, useState } from "react";
const API = process.env.NEXT_PUBLIC_API_URL ?? "https://app.nvironments.com";
const orgId = "00000000-0000-0000-0000-000000000001";
async function apiFetch(path: string) { const r = await fetch(`${API}${path}`, { credentials: "include", headers: { "Content-Type": "application/json" } }); if (!r.ok) throw new Error(await r.text()); return r.json(); }

interface MatrixEntry { id: string; action_class: string; autonomy_mode: string; approval_role: string | null; override_allowed: boolean; override_role: string | null; explanation: string | null; }

const modeColor: Record<string, string> = { fully_autonomous: "bg-green-900 text-green-300", autonomous_notify: "bg-cyan-900 text-cyan-300", guarded_approval: "bg-yellow-900 text-yellow-300", manual_only: "bg-red-900 text-red-300" };

export default function PermissionsPage() {
  const [matrix, setMatrix] = useState<MatrixEntry[]>([]); const [loading, setLoading] = useState(true);
  useEffect(() => { apiFetch(`/api/v1/orgs/${orgId}/permissions/matrix`).then(setMatrix).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Operator Permission Matrix</h1>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <div className="overflow-x-auto"><table className="w-full text-sm text-left">
          <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Action Class</th><th className="py-2 px-3">Autonomy Mode</th><th className="py-2 px-3">Approval Role</th><th className="py-2 px-3">Override</th><th className="py-2 px-3">Override Role</th></tr></thead>
          <tbody>{matrix.map(m => (
            <tr key={m.id} className="border-b border-gray-800/50 text-gray-300">
              <td className="py-2 px-3 font-medium">{m.action_class}</td>
              <td className="py-2 px-3"><span className={`px-2 py-0.5 rounded text-xs ${modeColor[m.autonomy_mode] || "bg-gray-700 text-gray-400"}`}>{m.autonomy_mode}</span></td>
              <td className="py-2 px-3">{m.approval_role || "—"}</td>
              <td className="py-2 px-3">{m.override_allowed ? <span className="text-green-400 text-xs">Yes</span> : <span className="text-red-400 text-xs">No</span>}</td>
              <td className="py-2 px-3 text-xs text-gray-500">{m.override_role || "—"}</td>
            </tr>
          ))}</tbody>
        </table>{matrix.length === 0 && <p className="text-gray-500 mt-4">No permission matrix configured. Run seed.</p>}</div>
      )}
    </div>
  );
}
