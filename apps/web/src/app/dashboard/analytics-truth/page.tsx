"use client";
import { useEffect, useState } from "react";
import {
  fetchAnalyticsImports,
  fetchAnalyticsEvents,
  fetchConversionImports,
  fetchConversionEvents,
  recomputeAnalytics,
  recomputeConversions,
} from "@/lib/live-execution-api";
import { brandsApi } from "@/lib/api";

export default function AnalyticsTruthPage() {
  const [imports, setImports] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [convImports, setConvImports] = useState<any[]>([]);
  const [convEvents, setConvEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [brandId, setBrandId] = useState("");
  const [brands, setBrands] = useState<{id: string; name: string}[]>([]);

  async function load() {
    setLoading(true);
    const [ai, ae, ci, ce] = await Promise.all([
      fetchAnalyticsImports(brandId),
      fetchAnalyticsEvents(brandId),
      fetchConversionImports(brandId),
      fetchConversionEvents(brandId),
    ]);
    setImports(ai); setEvents(ae); setConvImports(ci); setConvEvents(ce);
    setLoading(false);
  }

  useEffect(() => {
    brandsApi.list().then((r) => {
      const list = r.data ?? r;
      setBrands(Array.isArray(list) ? list : []);
      if (Array.isArray(list) && list.length > 0) setBrandId(list[0].id);
    }).catch(() => {});
  }, []);

  useEffect(() => { if (brandId) load(); }, [brandId]);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Analytics & Attribution Truth</h1>
      <div className="flex items-center gap-3 mb-4">
        <label className="text-sm text-gray-400">Brand:</label>
        <select aria-label="Select brand" className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white" value={brandId} onChange={e => setBrandId(e.target.value)}>
          {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </div>

      <div className="flex gap-3">
        <button onClick={() => recomputeAnalytics(brandId).then(load)} className="px-4 py-2 bg-blue-600 text-white rounded">
          Reconcile Analytics
        </button>
        <button onClick={() => recomputeConversions(brandId).then(load)} className="px-4 py-2 bg-green-600 text-white rounded">
          Reconcile Conversions
        </button>
      </div>

      {loading ? <p>Loading…</p> : (
        <>
          <section>
            <h2 className="text-lg font-semibold mb-2">Analytics Imports ({imports.length})</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm border">
                <thead className="bg-gray-100"><tr>
                  <th className="p-2 text-left">Source</th><th className="p-2 text-left">Category</th>
                  <th className="p-2 text-left">Imported</th><th className="p-2 text-left">Matched</th>
                  <th className="p-2 text-left">New</th><th className="p-2 text-left">Status</th>
                </tr></thead>
                <tbody>
                  {imports.map((i: any) => (
                    <tr key={i.id} className="border-t">
                      <td className="p-2">{i.source}</td><td className="p-2">{i.source_category}</td>
                      <td className="p-2">{i.events_imported}</td><td className="p-2">{i.events_matched}</td>
                      <td className="p-2">{i.events_new}</td><td className="p-2">{i.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-2">Analytics Events ({events.length})</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm border">
                <thead className="bg-gray-100"><tr>
                  <th className="p-2 text-left">Source</th><th className="p-2 text-left">Type</th>
                  <th className="p-2 text-left">Platform</th><th className="p-2 text-left">Value</th>
                  <th className="p-2 text-left">Truth Level</th>
                </tr></thead>
                <tbody>
                  {events.slice(0, 50).map((e: any) => (
                    <tr key={e.id} className="border-t">
                      <td className="p-2">{e.source}</td><td className="p-2">{e.event_type}</td>
                      <td className="p-2">{e.platform ?? "—"}</td><td className="p-2">{e.metric_value}</td>
                      <td className="p-2">{e.truth_level}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-2">Conversion Imports ({convImports.length})</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm border">
                <thead className="bg-gray-100"><tr>
                  <th className="p-2 text-left">Source</th><th className="p-2 text-left">Category</th>
                  <th className="p-2 text-left">Count</th><th className="p-2 text-left">Revenue</th>
                  <th className="p-2 text-left">Status</th>
                </tr></thead>
                <tbody>
                  {convImports.map((i: any) => (
                    <tr key={i.id} className="border-t">
                      <td className="p-2">{i.source}</td><td className="p-2">{i.source_category}</td>
                      <td className="p-2">{i.conversions_imported}</td><td className="p-2">${i.revenue_imported?.toFixed(2)}</td>
                      <td className="p-2">{i.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-2">Conversion Events ({convEvents.length})</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm border">
                <thead className="bg-gray-100"><tr>
                  <th className="p-2 text-left">Source</th><th className="p-2 text-left">Type</th>
                  <th className="p-2 text-left">Revenue</th><th className="p-2 text-left">Profit</th>
                  <th className="p-2 text-left">Truth Level</th>
                </tr></thead>
                <tbody>
                  {convEvents.slice(0, 50).map((e: any) => (
                    <tr key={e.id} className="border-t">
                      <td className="p-2">{e.source}</td><td className="p-2">{e.conversion_type}</td>
                      <td className="p-2">${e.revenue?.toFixed(2)}</td><td className="p-2">${e.profit?.toFixed(2)}</td>
                      <td className="p-2">{e.truth_level}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
