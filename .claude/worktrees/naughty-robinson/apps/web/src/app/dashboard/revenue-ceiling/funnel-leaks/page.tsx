'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { revenueCeilingPhaseAApi } from '@/lib/revenue-ceiling-phase-a-api';
import { AlertTriangle, BarChart3, RefreshCw } from 'lucide-react';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Error';
}

export default function FunnelLeakDashboard() {
  const qc = useQueryClient();
  const [brandId, setBrandId] = useState('');

  const { data: brands } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(String(brands[0].id));
  }, [brands, brandId]);

  const metricsQ = useQuery({
    queryKey: ['rc-funnel-metrics', brandId],
    queryFn: () => revenueCeilingPhaseAApi.funnelStageMetrics(brandId).then((r) => r.data),
    enabled: Boolean(brandId),
  });
  const leaksQ = useQuery({
    queryKey: ['rc-funnel-leaks', brandId],
    queryFn: () => revenueCeilingPhaseAApi.funnelLeaks(brandId).then((r) => r.data),
    enabled: Boolean(brandId),
  });

  const recompute = useMutation({
    mutationFn: () => revenueCeilingPhaseAApi.recomputeFunnelLeaks(brandId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rc-funnel-leaks', brandId] });
      qc.invalidateQueries({ queryKey: ['rc-funnel-metrics', brandId] });
    },
  });

  const selected = useMemo(() => brands?.find((b) => String(b.id) === brandId), [brands, brandId]);

  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <AlertTriangle className="text-amber-400" size={28} />
          Funnel Leak Dashboard
        </h1>
        <p className="text-gray-400 mt-1 max-w-2xl">
          Post-click funnel stage metrics (click → repeat purchase) and leak detection — severity, suspected
          cause, recommended fix, expected upside, confidence, and urgency.
        </p>
      </div>

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          aria-label="Brand for Funnel Leaks"
          value={brandId}
          onChange={(e) => setBrandId(e.target.value)}
        >
          {(brands ?? []).map((b) => (
            <option key={b.id} value={String(b.id)}>
              {b.name}
            </option>
          ))}
        </select>
        {selected && <p className="text-sm text-gray-500 mt-2">{selected.name}</p>}
      </div>

      <div className="flex justify-end">
        <button
          type="button"
          disabled={!brandId || recompute.isPending}
          onClick={() => recompute.mutate()}
          className="btn-primary flex items-center gap-2 disabled:opacity-50"
        >
          <RefreshCw size={16} className={recompute.isPending ? 'animate-spin' : ''} />
          Recompute funnel metrics &amp; leaks
        </button>
      </div>
      {recompute.isError && (
        <div className="card border-red-900/50 text-red-300 text-sm">{errMessage(recompute.error)}</div>
      )}

      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <BarChart3 size={16} className="text-brand-500" />
          Stage metrics
        </h3>
        <div className="flex flex-wrap gap-2">
          {(metricsQ.data ?? []).map((m) => (
            <span
              key={m.id}
              className="text-xs px-2 py-1 rounded bg-gray-800 text-gray-300 border border-gray-700"
            >
              {m.stage}: {(m.metric_value * 100).toFixed(2)}%
            </span>
          ))}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {(leaksQ.data ?? []).map((L) => (
          <div key={L.id} className="card border border-amber-900/30 bg-amber-950/10">
            <span className="badge-yellow text-[10px]">{L.leak_type}</span>
            <p className="text-white font-medium mt-2">{L.affected_funnel_stage}</p>
            <p className="text-sm text-gray-400 mt-1">{L.suspected_cause}</p>
            <p className="text-sm text-emerald-300/90 mt-2">Fix: {L.recommended_fix}</p>
            <p className="text-xs text-gray-500 mt-2">
              Upside ${L.expected_upside.toFixed(0)} · urgency {L.urgency.toFixed(0)} · conf{' '}
              {(L.confidence * 100).toFixed(0)}%
            </p>
          </div>
        ))}
      </div>
      {!leaksQ.isLoading && !(leaksQ.data ?? []).length && (
        <p className="text-gray-500">No leaks — run recompute.</p>
      )}
    </div>
  );
}
