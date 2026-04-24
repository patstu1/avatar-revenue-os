'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { revenueCeilingPhaseBApi } from '@/lib/revenue-ceiling-phase-b-api';
import { Package, RefreshCw } from 'lucide-react';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Error';
}

export default function ProductizationDashboard() {
  const qc = useQueryClient();
  const [brandId, setBrandId] = useState('');

  const { data: brands } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(String(brands[0].id));
  }, [brands, brandId]);

  const poQ = useQuery({
    queryKey: ['rc-b-po', brandId],
    queryFn: () => revenueCeilingPhaseBApi.productOpportunities(brandId).then((r) => r.data),
    enabled: Boolean(brandId),
  });

  const recompute = useMutation({
    mutationFn: () => revenueCeilingPhaseBApi.recomputeProductOpportunities(brandId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rc-b-po', brandId] }),
  });

  const selected = useMemo(() => brands?.find((b) => String(b.id) === brandId), [brands, brandId]);

  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Package className="text-violet-400" size={28} />
          Productization Opportunities Dashboard
        </h1>
        <p className="text-gray-400 mt-1 max-w-2xl">
          Product recommendations derived from niche and audience — type, price range, launch value,
          recurring potential, build complexity, and confidence.
        </p>
      </div>

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          aria-label="Brand for Productization"
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
      <div className="grid gap-3 md:grid-cols-2">
        {(poQ.data as any[] | undefined)?.map((P: Record<string, unknown>) => (
          <div key={String(P.id)} className="card border border-gray-800 text-sm">
            <span className="badge-yellow text-[10px]">{String(P.product_type)}</span>
            <p className="text-white font-medium mt-2">{String(P.product_recommendation)}</p>
            <p className="text-gray-500 text-xs mt-1">
              ${Number(P.price_range_min)}–${Number(P.price_range_max)} · Launch ${Number(P.expected_launch_value).toFixed(0)}
              {P.expected_recurring_value != null
                ? ` · MRR ${Number(P.expected_recurring_value).toFixed(0)}`
                : ''}{' '}
              · {String(P.build_complexity)}
            </p>
            {typeof P.explanation === 'string' && <p className="text-xs text-gray-500 mt-2">{P.explanation}</p>}
          </div>
        ))}
      </div>
      {!poQ.isLoading && !(poQ.data as any[])?.length && (
        <p className="text-gray-500">No product opportunities — run recompute.</p>
      )}
    </div>
  );
}
