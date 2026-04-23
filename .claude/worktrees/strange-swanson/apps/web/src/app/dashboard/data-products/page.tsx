"use client";

import { useState, useEffect } from "react";
import { fetchDataProducts, recomputeDataProducts } from "@/lib/creator-revenue-api";

const BRAND_ID = typeof window !== "undefined" ? localStorage.getItem("brandId") || "" : "";

export default function DataProductsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (BRAND_ID) fetchDataProducts(BRAND_ID).then(setItems).catch(() => {});
  }, []);

  async function handleRecompute() {
    if (!BRAND_ID) return;
    setLoading(true);
    await recomputeDataProducts(BRAND_ID);
    const data = await fetchDataProducts(BRAND_ID);
    setItems(data);
    setLoading(false);
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Data Products</h1>
        <button onClick={handleRecompute} disabled={loading}
          className="px-4 py-2 bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-50">
          {loading ? "Recomputing…" : "Recompute Data Products"}
        </button>
      </div>
      {items.length === 0 ? (
        <div className="border rounded p-8 text-center text-gray-400">No data product plans yet. Click Recompute.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {items.map((p: any) => (
            <div key={p.id} className="border rounded p-4 space-y-2">
              <div className="flex justify-between items-center">
                <span className="font-semibold">{p.product_type?.replace(/_/g, " ")}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${p.revenue_model === "recurring" ? "bg-green-100 text-green-700" : "bg-blue-100 text-blue-700"}`}>
                  {p.revenue_model}
                </span>
              </div>
              <p className="text-sm">Target: <strong>{p.target_segment}</strong></p>
              <div className="flex gap-4 text-sm">
                <span>Value: <strong>${p.expected_value?.toLocaleString()}</strong></span>
                <span>Band: <strong>{p.price_band}</strong></span>
                <span>Confidence: <strong>{(p.confidence * 100).toFixed(0)}%</strong></span>
              </div>
              <p className="text-xs text-gray-500">{p.explanation}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
