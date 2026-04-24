'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { revenueCeilingPhaseBApi } from '@/lib/revenue-ceiling-phase-b-api';
import { Gem, RefreshCw } from 'lucide-react';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Error';
}

export default function HighTicketDashboard() {
  const qc = useQueryClient();
  const [brandId, setBrandId] = useState('');

  const { data: brands } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(String(brands[0].id));
  }, [brands, brandId]);

  const htQ = useQuery({
    queryKey: ['rc-b-ht', brandId],
    queryFn: () => revenueCeilingPhaseBApi.highTicketOpportunities(brandId).then((r) => r.data),
    enabled: Boolean(brandId),
  });

  const recompute = useMutation({
    mutationFn: () => revenueCeilingPhaseBApi.recomputeHighTicket(brandId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rc-b-ht', brandId] }),
  });

  const selected = useMemo(() => brands?.find((b) => String(b.id) === brandId), [brands, brandId]);

  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Gem className="text-violet-400" size={28} />
          High-Ticket Conversion Dashboard
        </h1>
        <p className="text-gray-400 mt-1 max-w-2xl">
          Eligibility scoring, recommended offer paths, CTAs, close-rate proxies, deal values, and profit
          estimates for high-ticket conversion opportunities.
        </p>
      </div>

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          aria-label="Brand for High-Ticket"
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
      <div className="grid gap-4 md:grid-cols-2">
        {(htQ.data as any[] | undefined)?.map((H: Record<string, unknown>) => (
          <div key={String(H.id)} className="card border border-gray-800">
            <p className="text-xs text-gray-500 font-mono truncate">{String(H.opportunity_key)}</p>
            <p className="text-emerald-300/90 text-sm mt-2">
              Eligibility {(Number(H.eligibility_score) * 100).toFixed(0)}% · Close proxy{' '}
              {(Number(H.expected_close_rate_proxy) * 100).toFixed(1)}% · Deal ${Number(H.expected_deal_value).toFixed(0)}{' '}
              · Profit ${Number(H.expected_profit).toFixed(0)}
            </p>
            <p className="text-white text-sm mt-2">{String(H.recommended_cta ?? '')}</p>
            {typeof H.recommended_offer_path === 'object' &&
              H.recommended_offer_path !== null &&
              Array.isArray((H.recommended_offer_path as { steps?: string[] }).steps) &&
              typeof (H.recommended_offer_path as { steps: string[] }).steps[0] === 'string' && (
                <p className="text-xs text-violet-300/80 mt-1">
                  Path: {(H.recommended_offer_path as { steps: string[] }).steps[0]}
                </p>
              )}
            {typeof H.explanation === 'string' && <p className="text-xs text-gray-500 mt-2">{H.explanation}</p>}
          </div>
        ))}
      </div>
      {!htQ.isLoading && !(htQ.data as any[])?.length && (
        <p className="text-gray-500">No rows — add offers and recompute.</p>
      )}
    </div>
  );
}
