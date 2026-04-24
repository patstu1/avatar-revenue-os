"use client";

import { useState, useEffect } from "react";
import { fetchLiveEvents, recomputeLiveEvents } from "@/lib/creator-revenue-api";

const BRAND_ID = typeof window !== "undefined" ? localStorage.getItem("brandId") || "" : "";

export default function LiveEventsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (BRAND_ID) fetchLiveEvents(BRAND_ID).then(setItems).catch(() => {});
  }, []);

  async function handleRecompute() {
    if (!BRAND_ID) return;
    setLoading(true);
    await recomputeLiveEvents(BRAND_ID);
    const data = await fetchLiveEvents(BRAND_ID);
    setItems(data);
    setLoading(false);
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Live Events</h1>
        <button onClick={handleRecompute} disabled={loading}
          className="px-4 py-2 bg-pink-600 text-white rounded hover:bg-pink-700 disabled:opacity-50">
          {loading ? "Recomputing…" : "Recompute Live Events"}
        </button>
      </div>
      {items.length === 0 ? (
        <div className="border rounded p-8 text-center text-gray-400">No live event plans yet. Click Recompute.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm border">
            <thead className="bg-gray-50">
              <tr>
                <th className="p-3 text-left">Event Type</th>
                <th className="p-3 text-left">Audience</th>
                <th className="p-3 text-left">Ticket</th>
                <th className="p-3 text-left">Band</th>
                <th className="p-3 text-right">Value</th>
                <th className="p-3 text-right">Confidence</th>
                <th className="p-3 text-left">Truth</th>
              </tr>
            </thead>
            <tbody>
              {items.map((e: any) => (
                <tr key={e.id} className="border-t hover:bg-gray-50">
                  <td className="p-3 font-medium">{e.event_type?.replace(/_/g, " ")}</td>
                  <td className="p-3">{e.audience_segment}</td>
                  <td className="p-3">{e.ticket_model}</td>
                  <td className="p-3">{e.price_band}</td>
                  <td className="p-3 text-right">${e.expected_value?.toLocaleString()}</td>
                  <td className="p-3 text-right">{(e.confidence * 100).toFixed(0)}%</td>
                  <td className="p-3">
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      e.truth_label === "blocked" ? "bg-red-100 text-red-700" :
                      e.truth_label === "queued" ? "bg-yellow-100 text-yellow-700" :
                      "bg-green-100 text-green-700"
                    }`}>{e.truth_label}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
