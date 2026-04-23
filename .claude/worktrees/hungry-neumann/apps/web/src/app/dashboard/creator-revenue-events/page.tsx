"use client";

import { useState, useEffect } from "react";
import { fetchCreatorRevenueEvents } from "@/lib/creator-revenue-api";

const BRAND_ID = typeof window !== "undefined" ? localStorage.getItem("brandId") || "" : "";

export default function CreatorRevenueEventsPage() {
  const [items, setItems] = useState<any[]>([]);

  useEffect(() => {
    if (BRAND_ID) fetchCreatorRevenueEvents(BRAND_ID).then(setItems).catch(() => {});
  }, []);

  const totalRevenue = items.reduce((s: number, e: any) => s + (e.revenue || 0), 0);
  const totalProfit = items.reduce((s: number, e: any) => s + (e.profit || 0), 0);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Creator Revenue — Events</h1>
      <p className="text-sm text-gray-500">All revenue events across every creator revenue avenue.</p>

      {items.length > 0 && (
        <div className="flex gap-6 text-sm border rounded p-3">
          <span>Total Revenue: <strong>${totalRevenue.toLocaleString()}</strong></span>
          <span>Total Profit: <strong>${totalProfit.toLocaleString()}</strong></span>
          <span>Events: <strong>{items.length}</strong></span>
        </div>
      )}

      {items.length === 0 ? (
        <div className="border rounded p-8 text-center text-gray-400">No revenue events recorded yet.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm border">
            <thead className="bg-gray-50">
              <tr>
                <th className="p-3 text-left">Avenue</th>
                <th className="p-3 text-left">Event Type</th>
                <th className="p-3 text-left">Client</th>
                <th className="p-3 text-right">Revenue</th>
                <th className="p-3 text-right">Cost</th>
                <th className="p-3 text-right">Profit</th>
                <th className="p-3 text-left">Date</th>
              </tr>
            </thead>
            <tbody>
              {items.map((e: any) => (
                <tr key={e.id} className="border-t hover:bg-gray-50">
                  <td className="p-3 font-medium">{e.avenue_type?.replace(/_/g, " ")}</td>
                  <td className="p-3">{e.event_type?.replace(/_/g, " ")}</td>
                  <td className="p-3">{e.client_name || "—"}</td>
                  <td className="p-3 text-right">${e.revenue?.toLocaleString()}</td>
                  <td className="p-3 text-right">${e.cost?.toLocaleString()}</td>
                  <td className="p-3 text-right font-semibold">${e.profit?.toLocaleString()}</td>
                  <td className="p-3 text-xs text-gray-500">{e.created_at ? new Date(e.created_at).toLocaleDateString() : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
