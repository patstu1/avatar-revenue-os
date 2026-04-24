'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { revenueCeilingPhaseAApi } from '@/lib/revenue-ceiling-phase-a-api';
import { Users, RefreshCw } from 'lucide-react';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Error';
}

export default function OwnedAudienceDashboard() {
  const qc = useQueryClient();
  const [brandId, setBrandId] = useState('');

  const { data: brands } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(String(brands[0].id));
  }, [brands, brandId]);

  const audienceQ = useQuery({
    queryKey: ['rc-owned-audience', brandId],
    queryFn: () => revenueCeilingPhaseAApi.ownedAudience(brandId).then((r) => r.data),
    enabled: Boolean(brandId),
  });

  const recompute = useMutation({
    mutationFn: () => revenueCeilingPhaseAApi.recomputeOwnedAudience(brandId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rc-owned-audience', brandId] }),
  });

  const selected = useMemo(() => brands?.find((b) => String(b.id) === brandId), [brands, brandId]);

  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Users className="text-emerald-400" size={28} />
          Owned Audience Dashboard
        </h1>
        <p className="text-gray-400 mt-1 max-w-2xl">
          Owned-audience assets (newsletter, lead magnet, waitlist, SMS, community, remarketing), CTA variants,
          channel value estimates, and opt-in event tracking by source content.
        </p>
      </div>

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          aria-label="Brand for Owned Audience"
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
          Recompute owned audience
        </button>
      </div>
      {recompute.isError && (
        <div className="card border-red-900/50 text-red-300 text-sm">{errMessage(recompute.error)}</div>
      )}

      <h3 className="text-sm font-semibold text-gray-300">Assets &amp; CTAs</h3>
      <div className="grid gap-3 md:grid-cols-2">
        {(audienceQ.data?.assets ?? []).map((a) => (
          <div key={a.id} className="card border border-gray-800 text-sm">
            <span className="badge-yellow text-[10px]">{a.asset_type}</span>
            <p className="text-white mt-2">{a.channel_name}</p>
            <p className="text-gray-500 text-xs mt-1">Family: {a.content_family ?? '—'}</p>
            <p className="text-xs text-emerald-300/90 mt-2">
              Est. value ${a.estimated_channel_value.toFixed(0)} · direct vs capture{' '}
              {(a.direct_vs_capture_score * 100).toFixed(0)}%
            </p>
            {Array.isArray(a.cta_variants) && (
              <ul className="text-xs text-gray-500 mt-2 list-disc pl-4">
                {a.cta_variants.slice(0, 3).map((c, i) => (
                  <li key={i}>{String(c)}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>

      <h3 className="text-sm font-semibold text-gray-300 pt-4">Recent opt-in events</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left text-gray-400">
          <thead>
            <tr className="border-b border-gray-800 text-gray-500 text-xs">
              <th className="py-2">Type</th>
              <th className="py-2">Value</th>
              <th className="py-2">Content</th>
            </tr>
          </thead>
          <tbody>
            {(audienceQ.data?.events ?? []).slice(0, 15).map((e) => (
              <tr key={e.id} className="border-b border-gray-900">
                <td className="py-2">{e.event_type}</td>
                <td className="py-2">${e.value_contribution.toFixed(2)}</td>
                <td className="py-2 font-mono text-xs">{e.content_item_id?.slice(0, 8) ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!audienceQ.isLoading && !(audienceQ.data?.assets ?? []).length && (
        <p className="text-gray-500">No owned audience data — run recompute.</p>
      )}
    </div>
  );
}
