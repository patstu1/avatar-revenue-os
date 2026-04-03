"use client";
import { useEffect, useState } from "react";
import { useAuthStore } from "@/lib/store";
import { apiFetch } from "@/lib/api";

interface WFDef { id: string; workflow_name: string; workflow_type: string; scope_type: string; }
interface WFInst { id: string; resource_type: string; current_step_order: number; status: string; }

const statusColor: Record<string, string> = { in_progress: "bg-amber-900 text-amber-300", completed: "bg-green-900 text-green-300", rejected: "bg-red-900 text-red-300" };

export default function WorkflowsPage() {
  const user = useAuthStore((s) => s.user);
  const orgId = user?.organization_id ?? "";
  const [tab, setTab] = useState<"definitions" | "instances">("instances");
  const [defs, setDefs] = useState<WFDef[]>([]); const [insts, setInsts] = useState<WFInst[]>([]); const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!orgId) return;
    Promise.all([apiFetch<any>(`/api/v1/orgs/${orgId}/workflows`), apiFetch<any>(`/api/v1/orgs/${orgId}/workflow-instances`)])
      .then(([d, i]) => { setDefs(d); setInsts(i); }).catch(() => {}).finally(() => setLoading(false));
  }, [orgId]);

  if (!orgId) return <div className="p-6"><p className="text-gray-500">Loading organization...</p></div>;

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Enterprise Workflow Center</h1>
      <div className="flex gap-2">
        {[{key: "instances" as const, label: `Active Instances (${insts.length})`}, {key: "definitions" as const, label: `Definitions (${defs.length})`}].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} className={`px-4 py-2 rounded-lg text-sm font-medium ${tab === t.key ? "bg-cyan-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>{t.label}</button>
        ))}
      </div>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <>
          {tab === "instances" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Resource</th><th className="py-2 px-3">Step</th><th className="py-2 px-3">Status</th></tr></thead>
              <tbody>{insts.map(i => (
                <tr key={i.id} className="border-b border-gray-800/50 text-gray-300">
                  <td className="py-2 px-3">{i.resource_type}</td>
                  <td className="py-2 px-3 font-medium">Step {i.current_step_order}</td>
                  <td className="py-2 px-3"><span className={`px-2 py-0.5 rounded text-xs ${statusColor[i.status] || "bg-gray-700 text-gray-400"}`}>{i.status}</span></td>
                </tr>
              ))}</tbody>
            </table>{insts.length === 0 && <p className="text-gray-500 mt-4">No active workflow instances.</p>}</div>
          )}
          {tab === "definitions" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Name</th><th className="py-2 px-3">Type</th><th className="py-2 px-3">Scope</th></tr></thead>
              <tbody>{defs.map(d => (
                <tr key={d.id} className="border-b border-gray-800/50 text-gray-300">
                  <td className="py-2 px-3 font-medium">{d.workflow_name}</td>
                  <td className="py-2 px-3 text-cyan-400 text-xs">{d.workflow_type}</td>
                  <td className="py-2 px-3">{d.scope_type}</td>
                </tr>
              ))}</tbody>
            </table>{defs.length === 0 && <p className="text-gray-500 mt-4">No workflows defined. Create from a template.</p>}</div>
          )}
        </>
      )}
    </div>
  );
}
