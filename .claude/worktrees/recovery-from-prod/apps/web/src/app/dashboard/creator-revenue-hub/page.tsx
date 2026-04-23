"use client";

import { useState, useEffect } from "react";
import { fetchCreatorRevenueHub, recomputeCreatorRevenueHub } from "@/lib/creator-revenue-api";

const BRAND_ID = typeof window !== "undefined" ? localStorage.getItem("brandId") || "" : "";

const STATE_COLORS: Record<string, string> = {
  live: "bg-green-100 text-green-800",
  executing: "bg-blue-100 text-blue-800",
  queued: "bg-yellow-100 text-yellow-800",
  recommended: "bg-gray-100 text-gray-700",
  blocked: "bg-red-100 text-red-700",
};

export default function CreatorRevenueHubPage() {
  const [hub, setHub] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (BRAND_ID) fetchCreatorRevenueHub(BRAND_ID).then(setHub).catch(() => {});
  }, []);

  async function handleRecompute() {
    if (!BRAND_ID) return;
    setLoading(true);
    await recomputeCreatorRevenueHub(BRAND_ID);
    const data = await fetchCreatorRevenueHub(BRAND_ID);
    setHub(data);
    setLoading(false);
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Creator Revenue Hub</h1>
        <button onClick={handleRecompute} disabled={loading}
          className="px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50">
          {loading ? "Recomputing…" : "Recompute Hub"}
        </button>
      </div>

      {hub && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className="border rounded p-3 text-center">
              <div className="text-2xl font-bold">${hub.total_expected_value?.toLocaleString()}</div>
              <div className="text-xs text-gray-500">Total Expected Value</div>
            </div>
            <div className="border rounded p-3 text-center">
              <div className="text-2xl font-bold">${hub.total_revenue_to_date?.toLocaleString()}</div>
              <div className="text-xs text-gray-500">Revenue to Date</div>
            </div>
            <div className="border rounded p-3 text-center">
              <div className="text-2xl font-bold text-green-600">{hub.avenues_live ?? 0}</div>
              <div className="text-xs text-gray-500">Live</div>
            </div>
            <div className="border rounded p-3 text-center">
              <div className="text-2xl font-bold text-blue-600">{hub.avenues_executing ?? 0}</div>
              <div className="text-xs text-gray-500">Executing</div>
            </div>
            <div className="border rounded p-3 text-center">
              <div className="text-2xl font-bold text-red-600">{hub.total_blockers ?? 0}</div>
              <div className="text-xs text-gray-500">Total Blockers</div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full text-sm border">
              <thead className="bg-gray-50">
                <tr>
                  <th className="p-3 text-left">Avenue</th>
                  <th className="p-3 text-left">State</th>
                  <th className="p-3 text-right">Actions</th>
                  <th className="p-3 text-right">Blocked</th>
                  <th className="p-3 text-right">Expected Value</th>
                  <th className="p-3 text-right">Confidence</th>
                  <th className="p-3 text-right">Revenue</th>
                  <th className="p-3 text-right">Score</th>
                  <th className="p-3 text-left">Next Action</th>
                </tr>
              </thead>
              <tbody>
                {hub.entries?.map((e: any, i: number) => (
                  <tr key={i} className="border-t hover:bg-gray-50">
                    <td className="p-3 font-medium">{e.avenue_display_name}</td>
                    <td className="p-3">
                      <span className={`text-xs px-2 py-0.5 rounded ${STATE_COLORS[e.truth_state] || "bg-gray-100"}`}>
                        {e.truth_state}
                      </span>
                    </td>
                    <td className="p-3 text-right">{e.total_actions}</td>
                    <td className="p-3 text-right">{e.blocked_actions}</td>
                    <td className="p-3 text-right">${e.total_expected_value?.toLocaleString()}</td>
                    <td className="p-3 text-right">{(e.avg_confidence * 100).toFixed(0)}%</td>
                    <td className="p-3 text-right">${e.revenue_to_date?.toLocaleString()}</td>
                    <td className="p-3 text-right font-mono">{e.hub_score}</td>
                    <td className="p-3 text-xs text-gray-600 max-w-xs truncate">{e.operator_next_action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {hub.event_rollup && hub.event_rollup.event_count > 0 && (
            <div className="border rounded p-4">
              <h3 className="font-semibold mb-2">Revenue Event Rollup</h3>
              <div className="flex gap-6 text-sm">
                <span>Events: <strong>{hub.event_rollup.event_count}</strong></span>
                <span>Revenue: <strong>${hub.event_rollup.total_revenue?.toLocaleString()}</strong></span>
                <span>Cost: <strong>${hub.event_rollup.total_cost?.toLocaleString()}</strong></span>
                <span>Profit: <strong>${hub.event_rollup.total_profit?.toLocaleString()}</strong></span>
              </div>
            </div>
          )}
        </>
      )}

      {!hub && (
        <div className="border rounded p-8 text-center text-gray-400">No hub data. Click Recompute to generate.</div>
      )}
    </div>
  );
}
