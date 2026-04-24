"use client";

import { useState, useEffect } from "react";
import { fetchMerch, recomputeMerch } from "@/lib/creator-revenue-api";

const BRAND_ID = typeof window !== "undefined" ? localStorage.getItem("brandId") || "" : "";

export default function MerchPage() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (BRAND_ID) fetchMerch(BRAND_ID).then(setItems).catch(() => {});
  }, []);

  async function handleRecompute() {
    if (!BRAND_ID) return;
    setLoading(true);
    await recomputeMerch(BRAND_ID);
    const data = await fetchMerch(BRAND_ID);
    setItems(data);
    setLoading(false);
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Merch / Physical Products</h1>
        <button onClick={handleRecompute} disabled={loading}
          className="px-4 py-2 bg-orange-600 text-white rounded hover:bg-orange-700 disabled:opacity-50">
          {loading ? "Recomputing…" : "Recompute Merch"}
        </button>
      </div>
      {items.length === 0 ? (
        <div className="border rounded p-8 text-center text-gray-400">No merch plans yet. Click Recompute.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {items.map((m: any) => (
            <div key={m.id} className="border rounded p-4 space-y-2">
              <div className="flex justify-between items-center">
                <span className="font-semibold">{m.product_class?.replace(/_/g, " ")}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  m.truth_label === "blocked" ? "bg-red-100 text-red-700" :
                  m.truth_label === "queued" ? "bg-yellow-100 text-yellow-700" :
                  "bg-green-100 text-green-700"
                }`}>{m.truth_label}</span>
              </div>
              <p className="text-sm">Segment: <strong>{m.target_segment}</strong> · Band: <strong>{m.price_band}</strong></p>
              <div className="flex gap-4 text-sm">
                <span>Value: <strong>${m.expected_value?.toLocaleString()}</strong></span>
                <span>Confidence: <strong>{(m.confidence * 100).toFixed(0)}%</strong></span>
              </div>
              <p className="text-xs text-gray-500">{m.explanation}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
