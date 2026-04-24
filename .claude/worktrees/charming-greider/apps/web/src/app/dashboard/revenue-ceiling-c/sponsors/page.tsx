'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { revenueCeilingPhaseCApi } from '@/lib/revenue-ceiling-phase-c-api';
import { Handshake, RefreshCw } from 'lucide-react';

type Brand = { id: string; name: string };

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

export default function SponsorInventoryDashboard() {
  const qc = useQueryClient();
  const [brandId, setBrandId] = useState('');

  const { data: brands } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(String(brands[0].id));
  }, [brands, brandId]);

  const siQ = useQuery({
    queryKey: ['rc-c-sponsor-inv', brandId],
    queryFn: () => revenueCeilingPhaseCApi.sponsorInventory(brandId).then((r) => r.data),
    enabled: Boolean(brandId),
  });
  const spQ = useQuery({
    queryKey: ['rc-c-sponsor-pkg', brandId],
    queryFn: () => revenueCeilingPhaseCApi.sponsorPackageRecommendations(brandId).then((r) => r.data),
    enabled: Boolean(brandId),
  });

  const recompute = useMutation({
    mutationFn: () => revenueCeilingPhaseCApi.recomputeSponsorInventory(brandId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rc-c-sponsor-inv', brandId] });
      qc.invalidateQueries({ queryKey: ['rc-c-sponsor-pkg', brandId] });
    },
  });

  const selected = useMemo(() => brands?.find((b) => String(b.id) === brandId), [brands, brandId]);

  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Handshake className="text-violet-400" size={28} />
          Sponsor Inventory Dashboard
        </h1>
        <p className="text-gray-400 mt-1 max-w-2xl">
          Per-content sponsor fit scoring, estimated package pricing, sponsor categories,
          and brand-level package recommendations with deliverables.
        </p>
      </div>

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          aria-label="Brand for Sponsor Inventory"
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

      {/* Inventory grid */}
      <div className="grid gap-4 md:grid-cols-2">
        {(siQ.data as any[] | undefined)?.map((S: Record<string, unknown>) => (
          <div key={String(S.id)} className="card border border-gray-800">
            <div className="flex items-start justify-between gap-2">
              <p className="text-white font-medium text-sm truncate">
                {S.content_title ? String(S.content_title) : `${String(S.content_item_id).slice(0, 14)}…`}
              </p>
              <span className="badge-yellow text-[10px] shrink-0">{String(S.sponsor_category)}</span>
            </div>
            <div className="flex gap-4 mt-2 text-sm text-gray-400">
              <span>Fit {pct(Number(S.sponsor_fit_score ?? 0))}</span>
              <span>${Number(S.estimated_package_price ?? 0).toFixed(0)}</span>
              <span>Conf {pct(Number(S.confidence ?? 0))}</span>
            </div>
            {typeof S.explanation === 'string' && (
              <p className="text-xs text-gray-500 mt-2">{S.explanation}</p>
            )}
          </div>
        ))}
      </div>
      {!siQ.isLoading && !(siQ.data as any[])?.length && (
        <p className="text-gray-500">No sponsor inventory — add content items and recompute.</p>
      )}

      {/* Package Recommendations */}
      {spQ.data && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">
            Package Recommendation
          </h2>
          {(Array.isArray(spQ.data) ? spQ.data : [spQ.data]).map((P: any, i: number) => {
            const pkg = P.recommended_package as Record<string, unknown> | null | undefined;
            return (
              <div key={i} className="card border border-violet-900/30 space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-white font-medium">
                    {String((pkg as any)?.name ?? P.sponsor_category ?? '—')}
                  </p>
                  <span className="badge-yellow text-[10px] shrink-0">{String(P.sponsor_category ?? '—')}</span>
                </div>
                <p className="text-sm text-gray-400">
                  Fit {pct(Number(P.sponsor_fit_score ?? 0))} · ${Number(P.estimated_package_price ?? 0).toFixed(0)} · Conf {pct(Number(P.confidence ?? 0))}
                </p>
                {typeof P.explanation === 'string' && (
                  <p className="text-xs text-gray-500">{P.explanation}</p>
                )}
                {pkg && (
                  <div className="border-t border-gray-800 pt-2 text-xs text-gray-500 space-y-1">
                    {Array.isArray(pkg.deliverables) && (
                      <p>
                        <span className="text-gray-400 font-medium">Deliverables: </span>
                        {(pkg.deliverables as string[]).join(', ')}
                      </p>
                    )}
                    {pkg.duration_weeks != null && (
                      <p>
                        <span className="text-gray-400 font-medium">Duration: </span>
                        {String(pkg.duration_weeks)} weeks
                      </p>
                    )}
                    {pkg.exclusivity != null && (
                      <p>
                        <span className="text-gray-400 font-medium">Exclusivity: </span>
                        {String(pkg.exclusivity)}
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
