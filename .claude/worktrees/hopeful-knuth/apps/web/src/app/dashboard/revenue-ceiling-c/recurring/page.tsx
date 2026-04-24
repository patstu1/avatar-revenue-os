'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { revenueCeilingPhaseCApi } from '@/lib/revenue-ceiling-phase-c-api';
import { Repeat, RefreshCw } from 'lucide-react';

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

export default function RecurringRevenueDashboard() {
  const qc = useQueryClient();
  const [brandId, setBrandId] = useState('');

  const { data: brands } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(String(brands[0].id));
  }, [brands, brandId]);

  const rrQ = useQuery({
    queryKey: ['rc-c-recurring', brandId],
    queryFn: () => revenueCeilingPhaseCApi.recurringRevenue(brandId).then((r) => r.data),
    enabled: Boolean(brandId),
  });

  const recompute = useMutation({
    mutationFn: () => revenueCeilingPhaseCApi.recomputeRecurringRevenue(brandId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rc-c-recurring', brandId] }),
  });

  const selected = useMemo(() => brands?.find((b) => String(b.id) === brandId), [brands, brandId]);

  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Repeat className="text-violet-400" size={28} />
          Recurring Revenue Dashboard
        </h1>
        <p className="text-gray-400 mt-1 max-w-2xl">
          Subscription potential scoring, best recurring offer type, audience fit, churn risk proxy,
          and projected monthly/annual recurring values.
        </p>
      </div>

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          aria-label="Brand for Recurring Revenue"
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

      {(rrQ.data as any[] | undefined)?.[0] ? (
        (() => {
          const R = (rrQ.data as any[])[0] as Record<string, unknown>;
          const churnRisk = Number(R.churn_risk_proxy ?? 0);
          return (
            <div className="card border border-gray-800 space-y-4">
              <div className="flex flex-wrap gap-6 items-start">
                <div>
                  <p className="stat-label">Recurring Potential</p>
                  <p className="text-3xl font-bold text-violet-300">
                    {pct(Number(R.recurring_potential_score ?? 0))}
                  </p>
                </div>
                <div>
                  <p className="stat-label">Audience Fit</p>
                  <p className="text-2xl font-semibold text-emerald-300">
                    {pct(Number(R.audience_fit ?? 0))}
                  </p>
                </div>
                <div>
                  <p className="stat-label">Churn Risk</p>
                  <p className={`text-2xl font-semibold ${churnRisk > 0.5 ? 'text-red-400' : 'text-gray-300'}`}>
                    {pct(churnRisk)}
                  </p>
                </div>
                {typeof R.best_recurring_offer_type === 'string' && (
                  <div className="ml-auto pt-1">
                    <span className="badge-yellow text-xs">{R.best_recurring_offer_type}</span>
                  </div>
                )}
              </div>

              <div className="flex flex-wrap gap-8 border-t border-gray-800 pt-4">
                <div>
                  <p className="stat-label">Expected Monthly Value</p>
                  <p className="text-white font-medium text-lg">
                    ${Number(R.expected_monthly_value ?? 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}
                  </p>
                </div>
                <div>
                  <p className="stat-label">Expected Annual Value</p>
                  <p className="text-white font-medium text-lg">
                    ${Number(R.expected_annual_value ?? 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}
                  </p>
                </div>
                <div>
                  <p className="stat-label">Confidence</p>
                  <p className="text-gray-300 text-lg">{pct(Number(R.confidence ?? 0))}</p>
                </div>
              </div>

              {typeof R.explanation === 'string' && (
                <p className="text-xs text-gray-500 border-t border-gray-800 pt-3">{R.explanation}</p>
              )}
            </div>
          );
        })()
      ) : (
        !rrQ.isLoading && <p className="text-gray-500">No data — recompute to generate.</p>
      )}
    </div>
  );
}
