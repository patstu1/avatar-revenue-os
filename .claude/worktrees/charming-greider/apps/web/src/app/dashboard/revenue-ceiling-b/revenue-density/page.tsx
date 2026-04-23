'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { revenueCeilingPhaseBApi } from '@/lib/revenue-ceiling-phase-b-api';
import { BarChart3, RefreshCw } from 'lucide-react';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Error';
}

export default function RevenueDensityDashboard() {
  const qc = useQueryClient();
  const [brandId, setBrandId] = useState('');

  const { data: brands } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(String(brands[0].id));
  }, [brands, brandId]);

  const rdQ = useQuery({
    queryKey: ['rc-b-rd', brandId],
    queryFn: () => revenueCeilingPhaseBApi.revenueDensity(brandId).then((r) => r.data),
    enabled: Boolean(brandId),
  });

  const recompute = useMutation({
    mutationFn: () => revenueCeilingPhaseBApi.recomputeRevenueDensity(brandId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rc-b-rd', brandId] }),
  });

  const selected = useMemo(() => brands?.find((b) => String(b.id) === brandId), [brands, brandId]);

  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <BarChart3 className="text-violet-400" size={28} />
          Revenue Density Dashboard
        </h1>
        <p className="text-gray-400 mt-1 max-w-2xl">
          Per-content-item density metrics: revenue per 1k impressions, profit per audience member,
          monetization depth, repeat monetization score, ceiling score, and recommendations.
        </p>
      </div>

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          aria-label="Brand for Revenue Density"
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
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left text-gray-400">
          <thead>
            <tr className="border-b border-gray-800 text-gray-500 text-xs">
              <th className="py-2">Content</th>
              <th className="py-2">Rev / item</th>
              <th className="py-2">Rev / 1k imp</th>
              <th className="py-2">Profit / 1k imp</th>
              <th className="py-2">Profit / member</th>
              <th className="py-2">Depth</th>
              <th className="py-2">Repeat</th>
              <th className="py-2">Ceiling</th>
              <th className="py-2">Recommendation</th>
            </tr>
          </thead>
          <tbody>
            {(rdQ.data as any[] | undefined)?.map((R: Record<string, unknown>) => (
              <tr key={String(R.id)} className="border-b border-gray-900">
                <td className="py-2 text-gray-200 text-xs max-w-[180px] truncate" title={String(R.content_title ?? R.content_item_id)}>
                  {R.content_title ? String(R.content_title) : `${String(R.content_item_id).slice(0, 8)}…`}
                </td>
                <td className="py-2">${Number(R.revenue_per_content_item).toFixed(2)}</td>
                <td className="py-2">${Number(R.revenue_per_1k_impressions).toFixed(2)}</td>
                <td className="py-2">${Number(R.profit_per_1k_impressions).toFixed(2)}</td>
                <td className="py-2">${Number(R.profit_per_audience_member).toFixed(4)}</td>
                <td className="py-2">{(Number(R.monetization_depth_score) * 100).toFixed(0)}%</td>
                <td className="py-2">{(Number(R.repeat_monetization_score) * 100).toFixed(0)}%</td>
                <td className="py-2">{(Number(R.ceiling_score) * 100).toFixed(0)}%</td>
                <td className="py-2 text-xs max-w-[200px] truncate">{String(R.recommendation ?? '')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!rdQ.isLoading && !(rdQ.data as any[])?.length && (
        <p className="text-gray-500">No content density rows — add content items and recompute.</p>
      )}
    </div>
  );
}
