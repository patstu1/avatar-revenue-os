'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { copilotApi } from '@/lib/copilot-api';
import {
  AlertTriangle,
  CheckCircle,
  ShieldCheck,
  XCircle,
} from 'lucide-react';

type Brand = { id: string; name: string };

type ProviderReadiness = {
  provider_key: string;
  display_name?: string;
  is_ready: boolean;
  credential_status: string;
  missing_keys: string[];
  integration_status: string;
  truth_boundary?: { status: string };
};

function credBadge(status: string) {
  const s = String(status).toLowerCase();
  if (s === 'configured') return 'bg-emerald-900/40 text-emerald-200 border-emerald-700/50';
  if (s === 'partial') return 'bg-amber-900/40 text-amber-200 border-amber-700/50';
  if (s === 'not_configured' || s === 'blocked_by_credentials') return 'bg-red-900/40 text-red-200 border-red-700/50';
  return 'bg-gray-800 text-gray-300 border-gray-700';
}

function truthBadge(status: string) {
  const s = String(status).toLowerCase();
  if (s === 'live') return 'bg-emerald-900/40 text-emerald-200 border-emerald-700/50';
  if (s === 'blocked') return 'bg-red-900/40 text-red-200 border-red-700/50';
  if (s === 'configured_missing_credentials') return 'bg-orange-900/40 text-orange-200 border-orange-700/50';
  if (s === 'architecturally_present') return 'bg-violet-900/40 text-violet-200 border-violet-700/50';
  return 'bg-gray-800 text-gray-300 border-gray-700';
}

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

export default function CopilotReadinessPage() {
  const [selectedBrandId, setSelectedBrandId] = useState('');

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) setSelectedBrandId(String(brands[0].id));
  }, [brands, selectedBrandId]);

  const readinessQ = useQuery({
    queryKey: ['copilot-readiness', selectedBrandId],
    queryFn: () => copilotApi.providerReadiness(selectedBrandId).then((r) => r.data as ProviderReadiness[]),
    enabled: Boolean(selectedBrandId),
  });

  if (brandsLoading) {
    return (
      <div className="min-h-[60vh] rounded-xl border border-gray-800 bg-gray-900 p-8 text-white">
        <div className="h-8 w-80 bg-gray-800 rounded animate-pulse mb-6" />
        <div className="h-40 bg-gray-800/80 rounded animate-pulse" />
        <p className="text-center text-brand-300 mt-8">Loading…</p>
      </div>
    );
  }

  if (brandsError) {
    return (
      <div className="rounded-xl border border-red-900/50 bg-gray-900 p-8 text-red-300 flex items-center gap-2">
        <AlertTriangle size={20} />
        {errMessage(brandsErr)}
      </div>
    );
  }

  if (!brands?.length) {
    return (
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-12 text-center text-gray-400">
        Create a brand to view Provider Readiness.
      </div>
    );
  }

  const ready = readinessQ.data?.filter((r) => r.is_ready) ?? [];
  const notReady = readinessQ.data?.filter((r) => !r.is_ready) ?? [];

  return (
    <div className="space-y-6 rounded-xl border border-gray-800 bg-gray-900 p-6 md:p-8 text-white">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2 text-white">
          <ShieldCheck className="text-brand-300" size={28} />
          Provider Readiness
        </h1>
        <p className="text-gray-400 mt-1 text-sm">Per-provider readiness status with credential and truth boundary checks.</p>
      </div>

      <div className="max-w-xl rounded-lg border border-gray-800 bg-gray-950/50 p-4">
        <label className="block text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">Brand</label>
        <select
          aria-label="Select brand"
          className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 outline-none"
          value={selectedBrandId}
          onChange={(e) => setSelectedBrandId(e.target.value)}
        >
          {brands.map((b) => (
            <option key={b.id} value={String(b.id)}>{b.name}</option>
          ))}
        </select>
      </div>

      {readinessQ.isLoading && <div className="py-16 text-center text-brand-300">Loading readiness…</div>}
      {readinessQ.isError && (
        <div className="rounded-lg border border-red-900/50 p-6 text-red-300 flex gap-2">
          <AlertTriangle size={20} />
          {errMessage(readinessQ.error)}
        </div>
      )}
      {!readinessQ.isLoading && !readinessQ.isError && !(readinessQ.data?.length ?? 0) && (
        <div className="py-16 text-center text-gray-500 border border-dashed border-gray-800 rounded-lg">
          No readiness data available.
        </div>
      )}

      {readinessQ.data && readinessQ.data.length > 0 && (
        <>
          {readinessQ.data.length > 0 && (
            <div className="flex gap-4">
              <div className="rounded-xl border border-gray-800 bg-gray-950/40 px-4 py-3 flex items-center gap-2">
                <CheckCircle size={16} className="text-emerald-400" />
                <span className="text-sm text-gray-300">
                  <strong className="text-emerald-300">{ready.length}</strong> ready
                </span>
              </div>
              <div className="rounded-xl border border-gray-800 bg-gray-950/40 px-4 py-3 flex items-center gap-2">
                <XCircle size={16} className="text-red-400" />
                <span className="text-sm text-gray-300">
                  <strong className="text-red-300">{notReady.length}</strong> not ready
                </span>
              </div>
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {readinessQ.data.map((r) => (
              <div
                key={r.provider_key}
                className={`rounded-xl border p-4 space-y-3 ${
                  r.is_ready
                    ? 'border-emerald-900/40 bg-emerald-950/10'
                    : 'border-red-900/40 bg-red-950/10'
                }`}
              >
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-white text-sm">
                    {r.display_name || r.provider_key}
                  </h3>
                  {r.is_ready ? (
                    <CheckCircle size={18} className="text-emerald-400 shrink-0" />
                  ) : (
                    <XCircle size={18} className="text-red-400 shrink-0" />
                  )}
                </div>
                <p className="font-mono text-xs text-gray-500">{r.provider_key}</p>
                <div className="flex flex-wrap gap-2">
                  <span className={`inline-flex rounded-md border px-2 py-0.5 text-[10px] font-medium ${credBadge(r.credential_status)}`}>
                    {r.credential_status?.replace(/_/g, ' ')}
                  </span>
                  {r.truth_boundary?.status && (
                    <span className={`inline-flex rounded-md border px-2 py-0.5 text-[10px] font-medium ${truthBadge(r.truth_boundary.status)}`}>
                      {r.truth_boundary.status?.replace(/_/g, ' ')}
                    </span>
                  )}
                </div>
                {r.missing_keys?.length > 0 && (
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-500 mb-1">Missing Keys</p>
                    <div className="flex flex-wrap gap-1">
                      {r.missing_keys.map((k) => (
                        <span key={k} className="inline-flex rounded border border-red-900/40 bg-red-950/30 px-1.5 py-0.5 font-mono text-[10px] text-red-300">
                          {k}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
