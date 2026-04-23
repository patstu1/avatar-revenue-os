'use client';

import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { lec2Api } from '@/lib/live-execution-phase2-api';
import { RefreshCw, Zap } from 'lucide-react';

type Brand = { id: string; name: string };

type TriggerRow = {
  id: string;
  trigger_source: string;
  action_type: string;
  status: string;
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

export default function SequenceTriggersPage() {
  const qc = useQueryClient();
  const [brandId, setBrandId] = useState('');

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(String(brands[0].id));
  }, [brands, brandId]);

  const { data: triggersRaw, isLoading } = useQuery({
    queryKey: ['lec2-sequence-triggers', brandId],
    queryFn: () => lec2Api.sequenceTriggers(brandId).then((r) => r.data),
    enabled: Boolean(brandId),
  });

  const processMut = useMutation({
    mutationFn: () => lec2Api.processSequenceTriggers(brandId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['lec2-sequence-triggers', brandId] }),
  });

  const rows = asList<TriggerRow>(triggersRaw);

  if (brandsLoading) {
    return <div className="card py-12 text-center text-gray-500">Loading…</div>;
  }
  if (brandsError) {
    return <div className="card border-red-900/50 text-red-300 py-8 text-center">{errMessage(brandsErr)}</div>;
  }
  if (!brands?.length) {
    return <div className="card text-center py-12 text-gray-500">Create a brand to view sequence triggers.</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Zap className="text-brand-500" size={28} aria-hidden />
            Sequence Triggers
          </h1>
          <p className="text-gray-400 mt-1">Automation actions fired from funnel and lifecycle signals.</p>
        </div>
        <button
          type="button"
          className="btn-primary flex items-center gap-2 disabled:opacity-50 shrink-0"
          disabled={!brandId || processMut.isPending}
          onClick={() => processMut.mutate()}
        >
          <RefreshCw size={16} className={processMut.isPending ? 'animate-spin' : ''} />
          Process triggers
        </button>
      </div>

      {processMut.isError && (
        <div className="card border-amber-900/50 text-amber-200 text-sm">{errMessage(processMut.error)}</div>
      )}
      {processMut.isSuccess && (
        <div className="card border-emerald-900/50 text-emerald-300 text-sm">Process run complete.</div>
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
        <h2 className="text-lg font-semibold text-white mb-3">Trigger actions</h2>
        {isLoading ? (
          <p className="text-gray-500">Loading…</p>
        ) : rows.length === 0 ? (
          <p className="text-gray-500">No sequence trigger actions for this brand yet.</p>
        ) : (
          <div className="overflow-x-auto border border-gray-800 rounded-lg">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-left text-gray-400">
                  <th className="p-3 font-medium">Trigger source</th>
                  <th className="p-3 font-medium">Action type</th>
                  <th className="p-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-b border-gray-800/80 text-gray-300">
                    <td className="p-3 text-white">{row.trigger_source}</td>
                    <td className="p-3">{row.action_type}</td>
                    <td className="p-3 text-gray-400">{row.status}</td>
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
