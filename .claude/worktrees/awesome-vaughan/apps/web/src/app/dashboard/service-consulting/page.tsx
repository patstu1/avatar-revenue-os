"use client";

import { useState, useEffect } from "react";
import { fetchServiceConsulting, recomputeServiceConsulting } from "@/lib/creator-revenue-api";

const BRAND_ID = typeof window !== "undefined" ? localStorage.getItem("brandId") || "" : "";

export default function ServiceConsultingPage() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (BRAND_ID) fetchServiceConsulting(BRAND_ID).then(setItems).catch(() => {});
  }, []);

  async function handleRecompute() {
    if (!BRAND_ID) return;
    setLoading(true);
    await recomputeServiceConsulting(BRAND_ID);
    const data = await fetchServiceConsulting(BRAND_ID);
    setItems(data);
    setLoading(false);
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Services / Consulting</h1>
        <button onClick={handleRecompute} disabled={loading}
          className="px-4 py-2 bg-teal-600 text-white rounded hover:bg-teal-700 disabled:opacity-50">
          {loading ? "Recomputing…" : "Recompute Consulting"}
        </button>
      </div>
      {items.length === 0 ? (
        <div className="border rounded p-8 text-center text-gray-400">No consulting plans yet. Click Recompute.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm border">
            <thead className="bg-gray-50">
              <tr>
                <th className="p-3 text-left">Service Type</th>
                <th className="p-3 text-left">Tier</th>
                <th className="p-3 text-left">Target Buyer</th>
                <th className="p-3 text-left">Price Band</th>
                <th className="p-3 text-right">Deal Value</th>
                <th className="p-3 text-right">Confidence</th>
                <th className="p-3 text-left">Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((s: any) => (
                <tr key={s.id} className="border-t hover:bg-gray-50">
                  <td className="p-3 font-medium">{s.service_type?.replace(/_/g, " ")}</td>
                  <td className="p-3">{s.service_tier}</td>
                  <td className="p-3">{s.target_buyer}</td>
                  <td className="p-3">{s.price_band}</td>
                  <td className="p-3 text-right">${s.expected_deal_value?.toLocaleString()}</td>
                  <td className="p-3 text-right">{(s.confidence * 100).toFixed(0)}%</td>
                  <td className="p-3">{s.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
