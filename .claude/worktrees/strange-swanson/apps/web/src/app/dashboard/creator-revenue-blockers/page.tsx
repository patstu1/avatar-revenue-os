"use client";

import { useState, useEffect } from "react";
import { useBrandId } from "@/hooks/useBrandId";
import { fetchCreatorRevenueBlockers, recomputeCreatorRevenueBlockers } from "@/lib/creator-revenue-api";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-900/40 text-red-200 border-red-700/50",
  high: "bg-orange-900/40 text-orange-200 border-orange-700/50",
  medium: "bg-yellow-900/40 text-yellow-200 border-yellow-700/50",
  low: "bg-gray-800 text-gray-300 border-gray-700",
};

export default function CreatorRevenueBlockersPage() {
  const brandId = useBrandId();
  const [items, setItems] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = () => {
    if (!brandId) return;
    setLoading(true);
    fetchCreatorRevenueBlockers(brandId)
      .then((data) => setItems(Array.isArray(data) ? data : []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  };
  useEffect(load, [brandId]);

  const recompute = async () => {
    if (!brandId) return;
    setBusy(true);
    try {
      await recomputeCreatorRevenueBlockers(brandId);
      load();
    } finally {
      setBusy(false);
    }
  };

  if (!brandId) return <div className="p-6 text-gray-500">Loading brand...</div>;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Creator Revenue — Blockers</h1>
          <p className="text-sm text-gray-400">Unified view of all blockers across every revenue avenue.</p>
        </div>
        <button onClick={recompute} disabled={busy} className="px-4 py-2 bg-cyan-600 text-white text-sm rounded-lg hover:bg-cyan-500 disabled:opacity-50 transition-colors">
          {busy ? "Recomputing…" : "Recompute Blockers"}
        </button>
      </div>

      {loading ? (
        <div className="text-gray-500 py-8 text-center">Loading blockers…</div>
      ) : items.length === 0 ? (
        <div className="border border-dashed border-gray-800 rounded-lg p-8 text-center text-gray-500">No active blockers. All avenues are unblocked.</div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-800">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-900/60">
              <tr>
                <th className="p-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Avenue</th>
                <th className="p-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Blocker</th>
                <th className="p-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Severity</th>
                <th className="p-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Description</th>
                <th className="p-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Action Needed</th>
              </tr>
            </thead>
            <tbody>
              {items.map((b: any) => (
                <tr key={b.id} className="border-t border-gray-800 hover:bg-gray-800/40 transition-colors">
                  <td className="p-3 font-medium text-white">{(b.avenue_type ?? "").replace(/_/g, " ")}</td>
                  <td className="p-3 text-gray-300">{(b.blocker_type ?? "").replace(/_/g, " ")}</td>
                  <td className="p-3">
                    <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium capitalize ${SEVERITY_COLORS[b.severity] || "bg-gray-800 text-gray-300 border-gray-700"}`}>
                      {b.severity ?? "—"}
                    </span>
                  </td>
                  <td className="p-3 text-gray-400 max-w-xs">{b.description ?? "—"}</td>
                  <td className="p-3 text-gray-400 max-w-xs">{b.operator_action_needed ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
