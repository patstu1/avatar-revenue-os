'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { copilotApi } from '@/lib/copilot-api';
import { AlertTriangle, ClipboardCheck } from 'lucide-react';

type Brand = { id: string; name: string };

type OperatorAction = {
  id: string;
  urgency: string;
  title: string;
  description: string;
  source_module: string;
  truth_boundary?: { status: string };
};

function urgencyBadge(urgency: string) {
  const u = String(urgency).toLowerCase();
  if (u === 'critical') return 'bg-red-900/40 text-red-200 border-red-700/50';
  if (u === 'high') return 'bg-orange-900/40 text-orange-200 border-orange-700/50';
  if (u === 'medium') return 'bg-amber-900/40 text-amber-200 border-amber-700/50';
  if (u === 'low') return 'bg-emerald-900/40 text-emerald-200 border-emerald-700/50';
  return 'bg-gray-800 text-gray-300 border-gray-700';
}

function truthBadge(status: string) {
  const s = String(status).toLowerCase();
  if (s === 'live') return 'bg-emerald-900/40 text-emerald-200 border-emerald-700/50';
  if (s === 'blocked') return 'bg-red-900/40 text-red-200 border-red-700/50';
  if (s === 'recommendation_only') return 'bg-amber-900/40 text-amber-200 border-amber-700/50';
  return 'bg-gray-800 text-gray-300 border-gray-700';
}

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

export default function CopilotActionsPage() {
  const [selectedBrandId, setSelectedBrandId] = useState('');

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) setSelectedBrandId(String(brands[0].id));
  }, [brands, selectedBrandId]);

  const actionsQ = useQuery({
    queryKey: ['copilot-actions', selectedBrandId],
    queryFn: () => copilotApi.operatorActions(selectedBrandId).then((r) => r.data as OperatorAction[]),
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
        Create a brand to view Operator Actions.
      </div>
    );
  }

  return (
    <div className="space-y-6 rounded-xl border border-gray-800 bg-gray-900 p-6 md:p-8 text-white">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2 text-white">
          <ClipboardCheck className="text-brand-300" size={28} />
          Operator Actions
        </h1>
        <p className="text-gray-400 mt-1 text-sm">All pending operator actions aggregated from system modules.</p>
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

      {actionsQ.isLoading && <div className="py-16 text-center text-brand-300">Loading actions…</div>}
      {actionsQ.isError && (
        <div className="rounded-lg border border-red-900/50 p-6 text-red-300 flex gap-2">
          <AlertTriangle size={20} />
          {errMessage(actionsQ.error)}
        </div>
      )}
      {!actionsQ.isLoading && !actionsQ.isError && !(actionsQ.data?.length ?? 0) && (
        <div className="py-16 text-center text-gray-500 border border-dashed border-gray-800 rounded-lg">
          No operator actions pending.
        </div>
      )}

      {actionsQ.data && actionsQ.data.length > 0 && (
        <div className="rounded-lg border border-gray-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-950/50">
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Urgency</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Title</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 hidden md:table-cell">Description</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Source</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Truth</th>
              </tr>
            </thead>
            <tbody>
              {actionsQ.data.map((a) => (
                <tr key={a.id} className="border-t border-gray-800 hover:bg-gray-800/40 transition-colors">
                  <td className="px-4 py-3">
                    <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium capitalize ${urgencyBadge(a.urgency)}`}>
                      {a.urgency}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-medium text-white">{a.title}</td>
                  <td className="px-4 py-3 text-gray-400 hidden md:table-cell max-w-md truncate">{a.description}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex rounded-md border border-gray-700 bg-gray-800 px-2 py-0.5 text-xs text-gray-300 font-mono">
                      {a.source_module}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {a.truth_boundary?.status ? (
                      <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${truthBadge(a.truth_boundary.status)}`}>
                        {a.truth_boundary.status}
                      </span>
                    ) : (
                      <span className="text-gray-600">—</span>
                    )}
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
