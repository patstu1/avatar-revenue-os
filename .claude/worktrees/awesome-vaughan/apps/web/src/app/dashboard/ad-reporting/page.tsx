'use client';

import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { lec2Api } from '@/lib/live-execution-phase2-api';
import { Megaphone, RefreshCw } from 'lucide-react';

type Brand = { id: string; name: string };

type AdImportRow = {
  id: string;
  ad_platform: string;
  spend_imported: number;
  conversions_imported: number;
  credential_status: string;
};

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

function asList<T>(data: unknown): T[] {
  return Array.isArray(data) ? (data as T[]) : [];
}

export default function AdReportingPage() {
  const qc = useQueryClient();
  const [brandId, setBrandId] = useState('');

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(String(brands[0].id));
  }, [brands, brandId]);

  const { data: importsRaw, isLoading } = useQuery({
    queryKey: ['lec2-ad-imports', brandId],
    queryFn: () => lec2Api.adImports(brandId).then((r) => r.data),
    enabled: Boolean(brandId),
  });

  const runMut = useMutation({
    mutationFn: () => lec2Api.runAdImport(brandId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['lec2-ad-imports', brandId] }),
  });

  const rows = asList<AdImportRow>(importsRaw);

  if (brandsLoading) {
    return <div className="card py-12 text-center text-gray-500">Loading…</div>;
  }
  if (brandsError) {
    return <div className="card border-red-900/50 text-red-300 py-8 text-center">{errMessage(brandsErr)}</div>;
  }
  if (!brands?.length) {
    return <div className="card text-center py-12 text-gray-500">Create a brand to use ad reporting imports.</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Megaphone className="text-brand-500" size={28} aria-hidden />
            Ad Reporting Imports
          </h1>
          <p className="text-gray-400 mt-1">Spend and conversion data from ad platforms.</p>
        </div>
        <button
          type="button"
          className="btn-primary flex items-center gap-2 disabled:opacity-50 shrink-0"
          disabled={!brandId || runMut.isPending}
          onClick={() => runMut.mutate()}
        >
          <RefreshCw size={16} className={runMut.isPending ? 'animate-spin' : ''} />
          Run import
        </button>
      </div>

      {runMut.isError && (
        <div className="card border-amber-900/50 text-amber-200 text-sm">{errMessage(runMut.error)}</div>
      )}
      {runMut.isSuccess && (
        <div className="card border-emerald-900/50 text-emerald-300 text-sm">Import run complete.</div>
      )}

      <div className="card max-w-xl">
        <label className="stat-label block mb-2 text-gray-400 text-xs font-medium uppercase tracking-wider">Brand</label>
        <select className="input-field w-full" value={brandId} onChange={(e) => setBrandId(e.target.value)} aria-label="Select brand">
          {brands.map((b) => (
            <option key={b.id} value={String(b.id)}>
              {b.name}
            </option>
          ))}
        </select>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-3">Ad imports</h2>
        {isLoading ? (
          <p className="text-gray-500">Loading…</p>
        ) : rows.length === 0 ? (
          <p className="text-gray-500">No ad import runs yet. Run import to add rows.</p>
        ) : (
          <div className="overflow-x-auto border border-gray-800 rounded-lg">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-left text-gray-400">
                  <th className="p-3 font-medium">Ad platform</th>
                  <th className="p-3 font-medium">Spend imported</th>
                  <th className="p-3 font-medium">Conversions imported</th>
                  <th className="p-3 font-medium">Credential status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-b border-gray-800/80 text-gray-300">
                    <td className="p-3 text-white">{row.ad_platform}</td>
                    <td className="p-3">{row.spend_imported}</td>
                    <td className="p-3">{row.conversions_imported}</td>
                    <td className="p-3 text-gray-400">{row.credential_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
