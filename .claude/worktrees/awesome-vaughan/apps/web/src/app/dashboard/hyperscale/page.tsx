"use client";
import { useEffect, useState } from "react";
import { useAuthStore } from "@/lib/store";
import { apiFetch } from "@/lib/api";

interface Cap { id: string; total_queued: number; total_running: number; throughput_per_hour: number; burst_active: boolean; degraded: boolean; health_status: string; }
interface Health { id: string; health_status: string; queue_depth_total: number; ceiling_utilization_pct: number; burst_count_24h: number; degradation_count_24h: number; recommendation: string | null; }

const hColor: Record<string, string> = { healthy: "text-cyan-400", busy: "text-yellow-400", degraded: "text-pink-400", critical: "text-red-400" };

export default function HyperscalePage() {
  const user = useAuthStore((s) => s.user);
  const orgId = user?.organization_id ?? "";
  const [caps, setCaps] = useState<Cap[]>([]); const [health, setHealth] = useState<Health[]>([]); const [loading, setLoading] = useState(true);
  useEffect(() => { if (!orgId) return; Promise.all([apiFetch<any>(`/api/v1/orgs/${orgId}/scale/capacity`), apiFetch<any>(`/api/v1/orgs/${orgId}/scale/health`)]).then(([c, h]) => { setCaps(Array.isArray(c) ? c : []); setHealth(Array.isArray(h) ? h : []); }).catch(() => {}).finally(() => setLoading(false)); }, [orgId]);
  const latest = health[0]; const latestCap = caps[0];

  if (!orgId) return <div className="p-6"><p className="text-gray-500">Loading organization...</p></div>;

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Hyper-Scale Execution</h1>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <>
          {latest && (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {[
                { label: "STATUS", value: String(latest.health_status ?? "unknown").toUpperCase(), color: hColor[latest.health_status] || "text-gray-400" },
                { label: "QUEUE DEPTH", value: latest.queue_depth_total ?? 0 },
                { label: "CEILING %", value: `${Number(latest.ceiling_utilization_pct ?? 0).toFixed(0)}%` },
                { label: "BURSTS 24H", value: latest.burst_count_24h ?? 0, color: (latest.burst_count_24h ?? 0) > 0 ? "text-pink-400" : undefined },
                { label: "DEGRADES 24H", value: latest.degradation_count_24h ?? 0, color: (latest.degradation_count_24h ?? 0) > 0 ? "text-red-400" : undefined },
              ].map((s, i) => (
                <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                  <p className="text-[10px] text-gray-500 font-mono">{s.label}</p>
                  <p className={`text-xl font-black mt-1 ${s.color || "text-white"}`}>{s.value}</p>
                </div>
              ))}
            </div>
          )}
          {latest?.recommendation && <div className="bg-gray-900 border border-cyan-900/30 rounded-xl p-4"><p className="text-cyan-400 text-sm">{latest.recommendation}</p></div>}
          {latestCap && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-4"><p className="text-[10px] text-gray-500 font-mono">QUEUED</p><p className="text-xl font-bold text-white">{latestCap.total_queued}</p></div>
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-4"><p className="text-[10px] text-gray-500 font-mono">RUNNING</p><p className="text-xl font-bold text-cyan-400">{latestCap.total_running}</p></div>
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-4"><p className="text-[10px] text-gray-500 font-mono">THROUGHPUT/HR</p><p className="text-xl font-bold text-white">{Number(latestCap.throughput_per_hour ?? 0).toFixed(0)}</p></div>
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-4"><p className="text-[10px] text-gray-500 font-mono">BURST</p><p className={`text-xl font-bold ${latestCap.burst_active ? "text-pink-400 animate-pulse" : "text-green-400"}`}>{latestCap.burst_active ? "ACTIVE" : "CLEAR"}</p></div>
            </div>
          )}
          {caps.length === 0 && health.length === 0 && <p className="text-gray-500">No scale data yet. Run recompute.</p>}
        </>
      )}
    </div>
  );
}
