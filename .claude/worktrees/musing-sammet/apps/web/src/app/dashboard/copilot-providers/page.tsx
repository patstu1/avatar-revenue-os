'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { copilotApi } from '@/lib/copilot-api';
import {
  AlertTriangle,
  CheckCircle,
  Server,
  XCircle,
} from 'lucide-react';

type Brand = { id: string; name: string };

type Provider = {
  provider_key: string;
  display_name: string;
  category: string;
  provider_type: string;
  credential_status: string;
  integration_status: string;
  effective_status: string;
};

type ProviderReadiness = {
  provider_key: string;
  is_ready: boolean;
  missing_keys: string[];
  integration_status: string;
};

function statusBadge(status: string) {
  const s = String(status).toLowerCase();
  if (s === 'configured' || s === 'live') return 'bg-emerald-900/40 text-emerald-200 border-emerald-700/50';
  if (s === 'partial') return 'bg-amber-900/40 text-amber-200 border-amber-700/50';
  if (s === 'not_configured' || s === 'blocked_by_credentials') return 'bg-red-900/40 text-red-200 border-red-700/50';
  return 'bg-gray-800 text-gray-300 border-gray-700';
}

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

export default function CopilotProvidersPage() {
  const [selectedBrandId, setSelectedBrandId] = useState('');

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) setSelectedBrandId(String(brands[0].id));
  }, [brands, selectedBrandId]);

  const providersQ = useQuery({
    queryKey: ['copilot-providers', selectedBrandId],
    queryFn: () => copilotApi.providers(selectedBrandId).then((r) => r.data as Provider[]),
    enabled: Boolean(selectedBrandId),
  });

  const readinessQ = useQuery({
    queryKey: ['copilot-provider-readiness', selectedBrandId],
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
        Create a brand to view Provider Stack.
      </div>
    );
  }

  return (
    <div className="space-y-6 rounded-xl border border-gray-800 bg-gray-900 p-6 md:p-8 text-white">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2 text-white">
          <Server className="text-brand-300" size={28} />
          Provider Stack
        </h1>
        <p className="text-gray-400 mt-1 text-sm">Full provider inventory and readiness from the copilot perspective.</p>
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

      {/* Provider Summary */}
      <section>
        <h2 className="text-lg font-semibold text-white mb-4">Provider Summary</h2>
        {providersQ.isLoading && <div className="py-12 text-center text-brand-300">Loading providers…</div>}
        {providersQ.isError && (
          <div className="rounded-lg border border-red-900/50 p-6 text-red-300 flex gap-2">
            <AlertTriangle size={20} />
            {errMessage(providersQ.error)}
          </div>
        )}
        {!providersQ.isLoading && !providersQ.isError && !(providersQ.data?.length ?? 0) && (
          <div className="py-12 text-center text-gray-500 border border-dashed border-gray-800 rounded-lg">
            No providers found.
          </div>
        )}
        {providersQ.data && providersQ.data.length > 0 && (
          <div className="rounded-lg border border-gray-800 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 bg-gray-950/50">
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Provider Key</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Name</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Category</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Type</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Credentials</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Integration</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Effective</th>
                </tr>
              </thead>
              <tbody>
                {providersQ.data.map((p) => (
                  <tr key={p.provider_key} className="border-t border-gray-800 hover:bg-gray-800/40 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-gray-300">{p.provider_key}</td>
                    <td className="px-4 py-3 font-medium text-white">{p.display_name}</td>
                    <td className="px-4 py-3 text-gray-400">{p.category?.replace(/_/g, ' ')}</td>
                    <td className="px-4 py-3 text-gray-400">{p.provider_type}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${statusBadge(p.credential_status)}`}>
                        {p.credential_status?.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${statusBadge(p.integration_status)}`}>
                        {p.integration_status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${statusBadge(p.effective_status)}`}>
                        {p.effective_status?.replace(/_/g, ' ')}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Provider Readiness */}
      <section>
        <h2 className="text-lg font-semibold text-white mb-4">Provider Readiness</h2>
        {readinessQ.isLoading && <div className="py-12 text-center text-brand-300">Loading readiness…</div>}
        {readinessQ.isError && (
          <div className="rounded-lg border border-red-900/50 p-6 text-red-300 flex gap-2">
            <AlertTriangle size={20} />
            {errMessage(readinessQ.error)}
          </div>
        )}
        {!readinessQ.isLoading && !readinessQ.isError && !(readinessQ.data?.length ?? 0) && (
          <div className="py-12 text-center text-gray-500 border border-dashed border-gray-800 rounded-lg">
            No readiness data available.
          </div>
        )}
        {readinessQ.data && readinessQ.data.length > 0 && (
          <div className="rounded-lg border border-gray-800 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 bg-gray-950/50">
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Provider Key</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Ready</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Missing Keys</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Integration</th>
                </tr>
              </thead>
              <tbody>
                {readinessQ.data.map((r) => (
                  <tr key={r.provider_key} className="border-t border-gray-800 hover:bg-gray-800/40 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-gray-300">{r.provider_key}</td>
                    <td className="px-4 py-3">
                      {r.is_ready ? (
                        <CheckCircle size={16} className="text-emerald-400" />
                      ) : (
                        <XCircle size={16} className="text-red-400" />
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {r.missing_keys?.length ? (
                        <span className="font-mono text-xs text-red-300">{r.missing_keys.join(', ')}</span>
                      ) : (
                        <span className="text-gray-600">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${statusBadge(r.integration_status)}`}>
                        {r.integration_status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
