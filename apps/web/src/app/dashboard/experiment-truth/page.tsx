"use client";
import { useEffect, useState } from "react";
import {
  fetchExperimentImports,
  fetchExperimentLiveResults,
  recomputeExperimentTruth,
} from "@/lib/live-execution-api";
import { brandsApi } from "@/lib/api";

export default function ExperimentTruthPage() {
  const [imports, setImports] = useState<any[]>([]);
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [brandId, setBrandId] = useState("");
  const [brands, setBrands] = useState<{id: string; name: string}[]>([]);

  async function load() {
    setLoading(true);
    const [imp, res] = await Promise.all([
      fetchExperimentImports(brandId),
      fetchExperimentLiveResults(brandId),
    ]);
    setImports(imp); setResults(res);
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
      <h1 className="text-2xl font-bold">Experiment Truth</h1>
      <div className="flex items-center gap-3 mb-4">
        <label className="text-sm text-gray-400">Brand:</label>
        <select aria-label="Select brand" className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white" value={brandId} onChange={e => setBrandId(e.target.value)}>
          {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </div>

      <button onClick={() => recomputeExperimentTruth(brandId).then(load)} className="px-4 py-2 bg-purple-600 text-white rounded">
        Reconcile Experiment Truth
      </button>

      {loading ? <p>Loading…</p> : (
        <>
          <section>
            <h2 className="text-lg font-semibold mb-2">Observation Imports ({imports.length})</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm border">
                <thead className="bg-gray-100"><tr>
                  <th className="p-2 text-left">Source</th><th className="p-2 text-left">Imported</th>
                  <th className="p-2 text-left">Matched</th><th className="p-2 text-left">Status</th>
                </tr></thead>
                <tbody>
                  {imports.map((i: any) => (
                    <tr key={i.id} className="border-t">
                      <td className="p-2">{i.source}</td><td className="p-2">{i.observations_imported}</td>
                      <td className="p-2">{i.observations_matched}</td><td className="p-2">{i.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-2">Live Results ({results.length})</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm border">
                <thead className="bg-gray-100"><tr>
                  <th className="p-2 text-left">Source</th><th className="p-2 text-left">Type</th>
                  <th className="p-2 text-left">Metric</th><th className="p-2 text-left">Value</th>
                  <th className="p-2 text-left">Sample</th><th className="p-2 text-left">Confidence</th>
                  <th className="p-2 text-left">Truth Level</th><th className="p-2 text-left">Previous</th>
                </tr></thead>
                <tbody>
                  {results.slice(0, 50).map((r: any) => (
                    <tr key={r.id} className="border-t">
                      <td className="p-2">{r.source}</td><td className="p-2">{r.observation_type}</td>
                      <td className="p-2">{r.metric_name}</td><td className="p-2">{r.metric_value}</td>
                      <td className="p-2">{r.sample_size}</td><td className="p-2">{r.confidence}</td>
                      <td className="p-2">{r.truth_level}</td><td className="p-2">{r.previous_truth_level ?? "—"}</td>
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
