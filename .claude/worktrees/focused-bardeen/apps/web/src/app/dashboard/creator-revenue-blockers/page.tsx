"use client";

import { useState, useEffect } from "react";
import { fetchCreatorRevenueBlockers, recomputeCreatorRevenueBlockers } from "@/lib/creator-revenue-api";

const BRAND_ID = typeof window !== "undefined" ? localStorage.getItem("brandId") || "" : "";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-100 text-red-800",
  high: "bg-orange-100 text-orange-800",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-gray-100 text-gray-700",
};

export default function CreatorRevenueBlockersPage() {
  const [items, setItems] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);

  const load = () => {
    if (BRAND_ID) fetchCreatorRevenueBlockers(BRAND_ID).then(setItems).catch(() => {});
  };
  useEffect(load, []);

  const recompute = async () => {
    if (!BRAND_ID) return;
    setBusy(true);
    try { await recomputeCreatorRevenueBlockers(BRAND_ID); load(); } finally { setBusy(false); }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Creator Revenue — Blockers</h1>
          <p className="text-sm text-gray-500">Unified view of all blockers across every revenue avenue.</p>
        </div>
        <button onClick={recompute} disabled={busy} className="px-4 py-2 bg-black text-white text-sm rounded hover:bg-gray-800 disabled:opacity-50">
          {busy ? "Recomputing…" : "Recompute Blockers"}
        </button>
      </div>

      {items.length === 0 ? (
        <div className="border rounded p-8 text-center text-gray-400">No active blockers. Great — all avenues are unblocked.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm border">
            <thead className="bg-gray-50">
              <tr>
                <th className="p-3 text-left">Avenue</th>
                <th className="p-3 text-left">Blocker</th>
                <th className="p-3 text-left">Severity</th>
                <th className="p-3 text-left">Description</th>
                <th className="p-3 text-left">Action Needed</th>
              </tr>
            </thead>
            <tbody>
              {items.map((b: any) => (
                <tr key={b.id} className="border-t hover:bg-gray-50">
                  <td className="p-3 font-medium">{b.avenue_type?.replace(/_/g, " ")}</td>
                  <td className="p-3">{b.blocker_type?.replace(/_/g, " ")}</td>
                  <td className="p-3">
                    <span className={`text-xs px-2 py-0.5 rounded ${SEVERITY_COLORS[b.severity] || "bg-gray-100"}`}>
                      {b.severity}
                    </span>
                  </td>
                  <td className="p-3 text-gray-600 max-w-xs">{b.description}</td>
                  <td className="p-3 text-gray-600 max-w-xs">{b.operator_action_needed}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
