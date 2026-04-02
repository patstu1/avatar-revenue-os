'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { revenueCeilingPhaseAApi } from '@/lib/revenue-ceiling-phase-a-api';
import { Layers, RefreshCw } from 'lucide-react';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Error';
}

export default function OfferLadderDashboard() {
  const qc = useQueryClient();
  const [brandId, setBrandId] = useState('');

  const { data: brands } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(String(brands[0].id));
  }, [brands, brandId]);

  const laddersQ = useQuery({
    queryKey: ['rc-offer-ladders', brandId],
    queryFn: () => revenueCeilingPhaseAApi.offerLadders(brandId).then((r) => r.data),
    enabled: Boolean(brandId),
  });

  const recompute = useMutation({
    mutationFn: () => revenueCeilingPhaseAApi.recomputeOfferLadders(brandId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rc-offer-ladders', brandId] }),
  });

  const selected = useMemo(() => brands?.find((b) => String(b.id) === brandId), [brands, brandId]);

  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Layers className="text-emerald-400" size={28} />
          Offer Ladder Dashboard
        </h1>
        <p className="text-gray-400 mt-1 max-w-2xl">
          For each opportunity, view the full monetization ladder: top-of-funnel asset, first and second
          monetization steps, upsell / retention / fallback paths, economics, and confidence.
        </p>
      </div>

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          aria-label="Brand for Offer Ladders"
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
          Recompute ladders
        </button>
      </div>
      {recompute.isError && (
        <div className="card border-red-900/50 text-red-300 text-sm">{errMessage(recompute.error)}</div>
      )}
      {laddersQ.isLoading && <p className="text-gray-500">Loading…</p>}
      <div className="grid gap-4 md:grid-cols-2">
        {(laddersQ.data ?? []).map((L) => (
          <div key={L.id} className="card border border-gray-800">
            <p className="text-xs text-gray-500 font-mono truncate">{L.opportunity_key}</p>
            <p className="text-white font-medium mt-1">{L.top_of_funnel_asset.slice(0, 120)}</p>
            <p className="text-sm text-gray-400 mt-2">{L.first_monetization_step}</p>
            <p className="text-xs text-gray-500 mt-2">
              1st ${L.expected_first_conversion_value.toFixed(0)} · downstream ${L.expected_downstream_value.toFixed(0)}{' '}
              · LTV ${L.expected_ltv_contribution.toFixed(0)} · friction {L.friction_level} · conf{' '}
              {(L.confidence * 100).toFixed(0)}%
            </p>
            {L.explanation && <p className="text-xs text-gray-500 mt-2">{L.explanation}</p>}
          </div>
        ))}
      </div>
      {!laddersQ.isLoading && !(laddersQ.data ?? []).length && (
        <p className="text-gray-500">No ladders — run recompute.</p>
      )}
    </div>
  );
}
