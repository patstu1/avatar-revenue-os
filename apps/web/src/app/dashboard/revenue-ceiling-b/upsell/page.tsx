'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { revenueCeilingPhaseBApi } from '@/lib/revenue-ceiling-phase-b-api';
import { TrendingUp, RefreshCw } from 'lucide-react';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Error';
}

export default function UpsellDashboard() {
  const qc = useQueryClient();
  const [brandId, setBrandId] = useState('');

  const { data: brands } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(String(brands[0].id));
  }, [brands, brandId]);

  const upQ = useQuery({
    queryKey: ['rc-b-up', brandId],
    queryFn: () => revenueCeilingPhaseBApi.upsellRecommendations(brandId).then((r) => r.data),
    enabled: Boolean(brandId),
  });

  const recompute = useMutation({
    mutationFn: () => revenueCeilingPhaseBApi.recomputeUpsell(brandId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rc-b-up', brandId] }),
  });

  const selected = useMemo(() => brands?.find((b) => String(b.id) === brandId), [brands, brandId]);

  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <TrendingUp className="text-violet-400" size={28} />
          Upsell / Cross-Sell Dashboard
        </h1>
        <p className="text-gray-400 mt-1 max-w-2xl">
          Pairwise upsell recommendations: best next offer, timing, channel, expected take rate,
          incremental value, and sequencing.
        </p>
      </div>

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          aria-label="Brand for Upsell"
          value={brandId}
          onChange={(e) => setBrandId(e.target.value)}
        >
          {(brands ?? []).map((b) => (
            <option key={b.id} value={String(b.id)}>{b.name}</option>
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
          Recompute
        </button>
      </div>
      {recompute.isError && (
        <div className="card border-red-900/50 text-red-300 text-sm">{errMessage(recompute.error)}</div>
      )}
      {(upQ.data as any[] | undefined)?.map((U: Record<string, unknown>) => (
        <div key={String(U.id)} className="card border border-violet-900/30">
          <p className="text-xs text-gray-500 font-mono">{String(U.opportunity_key)}</p>
          <p className="text-white mt-1">
            Next:{' '}
            {U.best_next_offer && typeof U.best_next_offer === 'object' && U.best_next_offer !== null
              ? String((U.best_next_offer as { name?: string }).name ?? '')
              : '—'}
          </p>
          <p className="text-sm text-gray-400 mt-1">
            {String(U.best_timing)} · {String(U.best_channel)} · take {(Number(U.expected_take_rate) * 100).toFixed(1)}% ·
            +${Number(U.expected_incremental_value).toFixed(0)}
          </p>
          {typeof U.explanation === 'string' && <p className="text-xs text-gray-500 mt-2">{U.explanation}</p>}
        </div>
      ))}
      {!upQ.isLoading && !(upQ.data as any[])?.length && (
        <p className="text-gray-500">No upsell pairs — add at least two offers and recompute.</p>
      )}
    </div>
  );
}
