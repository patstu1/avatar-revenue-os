"use client";

import { useState, useEffect } from "react";
import { fetchOwnedAffiliateProgram, recomputeOwnedAffiliateProgram } from "@/lib/creator-revenue-api";

const BRAND_ID = typeof window !== "undefined" ? localStorage.getItem("brandId") || "" : "";

export default function OwnedAffiliateProgramPage() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (BRAND_ID) fetchOwnedAffiliateProgram(BRAND_ID).then(setItems).catch(() => {});
  }, []);

  async function handleRecompute() {
    if (!BRAND_ID) return;
    setLoading(true);
    await recomputeOwnedAffiliateProgram(BRAND_ID);
    const data = await fetchOwnedAffiliateProgram(BRAND_ID);
    setItems(data);
    setLoading(false);
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Owned Affiliate Program</h1>
        <button onClick={handleRecompute} disabled={loading}
          className="px-4 py-2 bg-teal-600 text-white rounded hover:bg-teal-700 disabled:opacity-50">
          {loading ? "Recomputing…" : "Recompute Affiliate Program"}
        </button>
      </div>
      {items.length === 0 ? (
        <div className="border rounded p-8 text-center text-gray-400">No affiliate program plans yet. Click Recompute.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {items.map((a: any) => (
            <div key={a.id} className="border rounded p-4 space-y-2">
              <div className="flex justify-between items-center">
                <span className="font-semibold">{a.program_type?.replace(/_/g, " ")}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  a.truth_label === "blocked" ? "bg-red-100 text-red-700" :
                  a.truth_label === "queued" ? "bg-yellow-100 text-yellow-700" :
                  "bg-green-100 text-green-700"
                }`}>{a.truth_label}</span>
              </div>
              <p className="text-sm">Partners: <strong>{a.target_partner_type}</strong> · Tier: <strong>{a.partner_tier}</strong></p>
              <p className="text-sm">Incentive: <strong>{a.incentive_model}</strong></p>
              <div className="flex gap-4 text-sm">
                <span>Value: <strong>${a.expected_value?.toLocaleString()}</strong></span>
                <span>Confidence: <strong>{(a.confidence * 100).toFixed(0)}%</strong></span>
              </div>
              <p className="text-xs text-gray-500">{a.explanation}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
