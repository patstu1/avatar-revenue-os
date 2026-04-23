'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { revenueCeilingPhaseCApi } from '@/lib/revenue-ceiling-phase-c-api';
import { Megaphone, RefreshCw } from 'lucide-react';

type Brand = { id: string; name: string };
type PromoFilter = 'all' | 'eligible' | 'not-eligible';

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Error';
}

function pct(v: number) {
  return `${(v * 100).toFixed(1)}%`;
}

export default function PaidPromotionDashboard() {
  const qc = useQueryClient();
  const [brandId, setBrandId] = useState('');
  const [promoFilter, setPromoFilter] = useState<PromoFilter>('all');
  const [expandedPromo, setExpandedPromo] = useState<string | null>(null);

  const { data: brands } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(String(brands[0].id));
  }, [brands, brandId]);

  const ppQ = useQuery({
    queryKey: ['rc-c-promo', brandId],
    queryFn: () => revenueCeilingPhaseCApi.paidPromotionCandidates(brandId).then((r) => r.data),
    enabled: Boolean(brandId),
  });

  const recompute = useMutation({
    mutationFn: () => revenueCeilingPhaseCApi.recomputePaidPromotionCandidates(brandId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rc-c-promo', brandId] }),
  });

  const selected = useMemo(() => brands?.find((b) => String(b.id) === brandId), [brands, brandId]);

  const promoData = ppQ.data as any[] | undefined;
  const filteredPromo = promoData?.filter((p: any) => {
    if (promoFilter === 'eligible') return p.is_eligible === true;
    if (promoFilter === 'not-eligible') return p.is_eligible === false;
    return true;
  });

  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Megaphone className="text-violet-400" size={28} />
          Paid Promotion Gate Dashboard
        </h1>
        <p className="text-gray-400 mt-1 max-w-2xl">
          Strict four-condition organic-winner gate — paid promotion is only allowed when
          organic winner evidence is strong across impressions, engagement, revenue, and ROI/age.
        </p>
      </div>

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          aria-label="Brand for Paid Promotion Gate"
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
          Refresh Gate
        </button>
      </div>
      {recompute.isError && (
        <div className="card border-red-900/50 text-red-300 text-sm">{errMessage(recompute.error)}</div>
      )}

      {/* Filter buttons */}
      <div className="flex gap-2">
        {([['all', 'All'], ['eligible', 'Eligible'], ['not-eligible', 'Not Eligible']] as const).map(([f, label]) => (
          <button
            key={f}
            type="button"
            onClick={() => setPromoFilter(f)}
            className={`px-3 py-1.5 rounded text-xs border ${
              promoFilter === f
                ? 'bg-violet-900/40 text-violet-200 border-violet-800'
                : 'text-gray-400 hover:text-white border-gray-800'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {filteredPromo && filteredPromo.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left text-gray-400">
            <thead>
              <tr className="border-b border-gray-800 text-gray-500 text-xs">
                <th className="py-2 pr-4">Content Title</th>
                <th className="py-2 pr-4">Eligible</th>
                <th className="py-2 pr-4">Confidence</th>
                <th className="py-2">Gate Reason</th>
              </tr>
            </thead>
            <tbody>
              {filteredPromo.map((P: Record<string, unknown>) => {
                const rowId = String(P.id ?? P.content_item_id ?? '');
                const isExpanded = expandedPromo === rowId;
                return (
                  <React.Fragment key={rowId}>
                    <tr
                      className="border-b border-gray-900 cursor-pointer hover:bg-gray-800/30 transition-colors"
                      onClick={() => setExpandedPromo(isExpanded ? null : rowId)}
                    >
                      <td
                        className="py-2 pr-4 text-gray-200 text-xs max-w-[200px] truncate"
                        title={P.content_title ? String(P.content_title) : String(P.content_item_id)}
                      >
                        {P.content_title ? String(P.content_title) : `${String(P.content_item_id).slice(0, 10)}…`}
                      </td>
                      <td className="py-2 pr-4">
                        {P.is_eligible ? (
                          <span className="text-emerald-400 font-bold text-sm">✓</span>
                        ) : (
                          <span className="text-red-400 font-bold text-sm">✗</span>
                        )}
                      </td>
                      <td className="py-2 pr-4 text-xs">{pct(Number(P.confidence ?? 0))}</td>
                      <td className="py-2 text-xs text-gray-500">{String(P.gate_reason ?? '—')}</td>
                    </tr>
                    {isExpanded && P.organic_winner_evidence != null && (
                      <tr className="bg-gray-900/60">
                        <td colSpan={4} className="py-3 px-4">
                          <p className="text-[11px] text-gray-500 font-mono whitespace-pre-wrap break-all">
                            {String(JSON.stringify(P.organic_winner_evidence, null, 2))}
                          </p>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-gray-500">
          {ppQ.isLoading ? 'Loading…' : 'No paid promotion candidates — recompute to generate.'}
        </p>
      )}
    </div>
  );
}
