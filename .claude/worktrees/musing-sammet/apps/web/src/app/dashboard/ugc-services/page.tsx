"use client";

import { useState, useEffect } from "react";
import { fetchUgcServices, recomputeUgcServices } from "@/lib/creator-revenue-api";

const BRAND_ID = typeof window !== "undefined" ? localStorage.getItem("brandId") || "" : "";

export default function UgcServicesPage() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (BRAND_ID) fetchUgcServices(BRAND_ID).then(setItems).catch(() => {});
  }, []);

  async function handleRecompute() {
    if (!BRAND_ID) return;
    setLoading(true);
    await recomputeUgcServices(BRAND_ID);
    const data = await fetchUgcServices(BRAND_ID);
    setItems(data);
    setLoading(false);
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">UGC / Creative Services</h1>
        <button onClick={handleRecompute} disabled={loading}
          className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50">
          {loading ? "Recomputing…" : "Recompute UGC Services"}
        </button>
      </div>
      {items.length === 0 ? (
        <div className="border rounded p-8 text-center text-gray-400">No UGC service plans yet. Click Recompute.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {items.map((s: any) => (
            <div key={s.id} className="border rounded p-4 space-y-2">
              <div className="flex justify-between">
                <span className="font-semibold">{s.service_type?.replace(/_/g, " ")}</span>
                <span className="text-sm px-2 py-0.5 rounded bg-purple-100 text-purple-700">{s.price_band}</span>
              </div>
              <p className="text-sm text-gray-600">{s.recommended_package}</p>
              <div className="flex gap-4 text-sm">
                <span>Target: <strong>{s.target_segment}</strong></span>
                <span>Value: <strong>${s.expected_value?.toLocaleString()}</strong></span>
                <span>Margin: <strong>${s.expected_margin?.toLocaleString()}</strong></span>
              </div>
              <p className="text-xs text-gray-500">{s.explanation}</p>
              <div className="text-xs text-gray-400">
                Status: {s.status} · Confidence: {(s.confidence * 100).toFixed(0)}%
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
