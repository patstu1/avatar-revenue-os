"use client";
import { useEffect, useState } from "react";
const API = process.env.NEXT_PUBLIC_API_URL ?? "https://app.nvironments.com";
const orgId = "00000000-0000-0000-0000-000000000001";
async function apiFetch(path: string) { const r = await fetch(`${API}${path}`, { credentials: "include", headers: { "Content-Type": "application/json" } }); if (!r.ok) throw new Error(await r.text()); return r.json(); }

interface Connector { id: string; connector_name: string; connector_type: string; status: string; last_sync_status: string | null; }
interface Cluster { id: string; cluster_type: string; cluster_label: string; signal_count: number; avg_sentiment: number; recommended_action: string | null; }
interface Blocker { id: string; blocker_type: string; description: string; severity: string; }

export default function IntegrationsPage() {
  const [tab, setTab] = useState<"connectors" | "clusters" | "blockers">("connectors");
  const [connectors, setConnectors] = useState<Connector[]>([]); const [clusters, setClusters] = useState<Cluster[]>([]); const [blockers, setBlockers] = useState<Blocker[]>([]); const [loading, setLoading] = useState(true);
  useEffect(() => { Promise.all([apiFetch(`/api/v1/orgs/${orgId}/integrations/connectors`), apiFetch(`/api/v1/orgs/${orgId}/integrations/clusters`), apiFetch(`/api/v1/orgs/${orgId}/integrations/blockers`)]).then(([c, cl, b]) => { setConnectors(c); setClusters(cl); setBlockers(b); }).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Integrations + Listening</h1>
      <div className="flex gap-2">
        {[{key: "connectors" as const, label: `Connectors (${connectors.length})`}, {key: "clusters" as const, label: `Signal Clusters (${clusters.length})`}, {key: "blockers" as const, label: `Blockers (${blockers.length})`}].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} className={`px-4 py-2 rounded-lg text-sm font-medium ${tab === t.key ? "bg-cyan-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>{t.label}</button>
        ))}
      </div>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <>
          {tab === "connectors" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Name</th><th className="py-2 px-3">Type</th><th className="py-2 px-3">Status</th><th className="py-2 px-3">Last Sync</th></tr></thead>
              <tbody>{connectors.map(c => (
                <tr key={c.id} className="border-b border-gray-800/50 text-gray-300">
                  <td className="py-2 px-3 font-medium">{c.connector_name}</td>
                  <td className="py-2 px-3 text-cyan-400 text-xs">{c.connector_type}</td>
                  <td className="py-2 px-3">{c.status}</td>
                  <td className="py-2 px-3">{c.last_sync_status || "—"}</td>
                </tr>
              ))}</tbody>
            </table>{connectors.length === 0 && <p className="text-gray-500 mt-4">No connectors configured.</p>}</div>
          )}
          {tab === "clusters" && (
            <div className="grid gap-4 md:grid-cols-2">{clusters.map(c => (
              <div key={c.id} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <div className="flex justify-between items-center mb-2"><span className="text-cyan-400 text-xs">{c.cluster_type}</span><span className="text-gray-500 text-xs">{c.signal_count} signals</span></div>
                <p className="text-white font-medium">{c.cluster_label}</p>
                {c.recommended_action && <p className="text-green-400 text-xs mt-2">{c.recommended_action}</p>}
              </div>
            ))}{clusters.length === 0 && <p className="text-gray-500 col-span-2">No signal clusters yet.</p>}</div>
          )}
          {tab === "blockers" && (
            <div className="space-y-3">{blockers.map(b => (
              <div key={b.id} className="bg-red-950 border border-red-800 rounded-lg p-4">
                <span className="text-red-300 font-medium">{b.blocker_type}</span>
                <p className="text-gray-400 text-sm mt-1">{b.description}</p>
              </div>
            ))}{blockers.length === 0 && <p className="text-gray-500">No integration blockers.</p>}</div>
          )}
        </>
      )}
    </div>
  );
}
