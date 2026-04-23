"use client";

import { useState, useEffect } from "react";
import { fetchCreatorRevenueTruth } from "@/lib/creator-revenue-api";

const BRAND_ID = typeof window !== "undefined" ? localStorage.getItem("brandId") || "" : "";

const STATE_COLORS: Record<string, string> = {
  live: "bg-green-100 text-green-800",
  executing: "bg-blue-100 text-blue-800",
  queued: "bg-yellow-100 text-yellow-800",
  recommended: "bg-gray-100 text-gray-700",
  blocked: "bg-red-100 text-red-700",
};

export default function CreatorRevenueTruthPage() {
  const [items, setItems] = useState<any[]>([]);

  useEffect(() => {
    if (BRAND_ID) fetchCreatorRevenueTruth(BRAND_ID).then(setItems).catch(() => {});
  }, []);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Creator Revenue — Execution Truth</h1>
      <p className="text-sm text-gray-500">Per-avenue truth state snapshot. Recompute via the Hub to refresh.</p>

      {items.length === 0 ? (
        <div className="border rounded p-8 text-center text-gray-400">No truth data. Recompute the Hub first.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((t: any) => (
            <div key={t.id} className="border rounded p-4 space-y-2">
              <div className="flex justify-between items-center">
                <span className="font-semibold">{t.avenue_type?.replace(/_/g, " ")}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${STATE_COLORS[t.truth_state] || "bg-gray-100"}`}>
                  {t.truth_state}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>Actions: <strong>{t.total_actions}</strong></div>
                <div>Blocked: <strong>{t.blocked_actions}</strong></div>
                <div>Value: <strong>${t.total_expected_value?.toLocaleString()}</strong></div>
                <div>Revenue: <strong>${t.revenue_to_date?.toLocaleString()}</strong></div>
                <div>Confidence: <strong>{(t.avg_confidence * 100).toFixed(0)}%</strong></div>
                <div>Blockers: <strong>{t.blocker_count}</strong></div>
              </div>
              {t.operator_next_action && (
                <p className="text-xs text-gray-500 border-t pt-2">{t.operator_next_action}</p>
              )}
              {t.missing_integrations?.length > 0 && (
                <div className="text-xs text-orange-600">Missing: {t.missing_integrations.join(", ")}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
