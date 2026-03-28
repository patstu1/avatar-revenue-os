'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { discoveryApi } from '@/lib/discovery-api';
import { Check, RefreshCw, TrendingUp, X, Zap } from 'lucide-react';

type Brand = { id: string; name: string };

type TrendSignal = {
  id: string;
  keyword: string;
  platform?: string | null;
  signal_type: string;
  volume: number;
  velocity: number;
  strength: string;
  is_actionable: boolean;
};

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

function velocityBarClass(v: number) {
  if (v > 0.6) return 'bg-emerald-500';
  if (v > 0.3) return 'bg-amber-500';
  return 'bg-red-500';
}

function strengthBadgeClass(s: string) {
  const x = (s || '').toLowerCase();
  if (x === 'strong') return 'badge-green';
  if (x === 'moderate') return 'badge-yellow';
  if (x === 'weak' || x === 'insufficient') return 'badge-red';
  return 'badge-yellow';
}

function platformBadge(platform: string | null | undefined) {
  const p = (platform || 'unknown').toLowerCase();
  const base = 'capitalize';
  const tone =
    p === 'youtube'
      ? 'badge-red'
      : p === 'tiktok'
        ? 'badge-blue'
        : p === 'instagram'
          ? 'badge-yellow'
          : 'badge-blue';
  return `${tone} ${base}`;
}

export default function ScalePage() {
  const queryClient = useQueryClient();
  const [selectedBrandId, setSelectedBrandId] = useState('');

  const {
    data: brands,
    isLoading: brandsLoading,
    isError: brandsError,
    error: brandsErr,
  } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) {
      setSelectedBrandId(String(brands[0].id));
    }
  }, [brands, selectedBrandId]);

  const {
    data: trends,
    isLoading: trendsLoading,
    isError: trendsError,
    error: trendsErr,
  } = useQuery({
    queryKey: ['discovery-trends', selectedBrandId],
    queryFn: () => discoveryApi.getTrends(selectedBrandId).then((r) => r.data as TrendSignal[]),
    enabled: Boolean(selectedBrandId),
  });

  const recomputeMutation = useMutation({
    mutationFn: () => discoveryApi.recomputeTrends(selectedBrandId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['discovery-trends', selectedBrandId] });
    },
  });

  const selectedBrand = useMemo(
    () => brands?.find((b) => String(b.id) === selectedBrandId),
    [brands, selectedBrandId]
  );

  if (brandsLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-64 bg-gray-800 rounded animate-pulse" />
        <div className="card py-12 text-center text-gray-500">Loading brands…</div>
      </div>
    );
  }

  if (brandsError) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Trend Scanner</h1>
        <div className="card border-red-900/50 text-red-300 py-8 text-center">Failed to load brands: {errMessage(brandsErr)}</div>
      </div>
    );
  }

  if (!brands?.length) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <TrendingUp className="text-brand-500" size={28} aria-hidden />
            Trend Scanner
          </h1>
          <p className="text-gray-400 mt-1">Active trend signals across platforms ranked by velocity</p>
        </div>
        <div className="card text-center py-12">
          <Zap className="mx-auto text-gray-600 mb-4" size={48} aria-hidden />
          <p className="text-gray-500">No brands yet. Create a brand to scan trends.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <TrendingUp className="text-brand-500" size={28} aria-hidden />
            Trend Scanner
          </h1>
          <p className="text-gray-400 mt-1">Active trend signals across platforms ranked by velocity</p>
        </div>
        <button
          type="button"
          className="btn-primary flex items-center justify-center gap-2 shrink-0 disabled:opacity-50"
          disabled={!selectedBrandId || recomputeMutation.isPending}
          onClick={() => recomputeMutation.mutate()}
        >
          <RefreshCw size={16} className={recomputeMutation.isPending ? 'animate-spin' : ''} aria-hidden />
          Recompute Trends
        </button>
      </div>

      <div className="card">
        <label htmlFor="scale-brand-select" className="stat-label block mb-2">
          Brand
        </label>
        <select
          id="scale-brand-select"
          className="input-field w-full max-w-md"
          value={selectedBrandId}
          onChange={(e) => setSelectedBrandId(e.target.value)}
        >
          {brands.map((b) => (
            <option key={b.id} value={String(b.id)}>
              {b.name}
            </option>
          ))}
        </select>
        {selectedBrand && <p className="text-sm text-gray-500 mt-2">Viewing: {selectedBrand.name}</p>}
      </div>

      {recomputeMutation.isError && (
        <div className="card border-red-900/50 text-red-300 text-sm">{errMessage(recomputeMutation.error)}</div>
      )}

      {trendsLoading && <div className="card text-center py-12 text-gray-500">Loading trends…</div>}

      {trendsError && !trendsLoading && (
        <div className="card border-red-900/50 text-red-300 py-8 text-center">Failed to load trends: {errMessage(trendsErr)}</div>
      )}

      {!trendsLoading && !trendsError && trends?.length === 0 && (
        <div className="card text-center py-12">
          <Zap className="mx-auto text-gray-600 mb-4" size={40} aria-hidden />
          <p className="text-gray-500">No trend signals yet. Ingest signals or recompute after data is available.</p>
        </div>
      )}

      {!trendsLoading && !trendsError && trends && trends.length > 0 && (
        <div className="card overflow-x-auto p-0">
          <table className="w-full text-sm text-left">
            <thead>
              <tr className="border-b border-gray-800 text-gray-400 uppercase text-xs tracking-wider">
                <th className="px-6 py-3 font-medium">Keyword</th>
                <th className="px-6 py-3 font-medium">Platform</th>
                <th className="px-6 py-3 font-medium">Volume</th>
                <th className="px-6 py-3 font-medium min-w-[140px]">Velocity</th>
                <th className="px-6 py-3 font-medium">Strength</th>
                <th className="px-6 py-3 font-medium text-center">Actionable</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {trends.map((t) => {
                const vel = Number(t.velocity);
                const pct = Math.min(100, Math.max(0, vel * 100));
                return (
                  <tr key={t.id} className="hover:bg-gray-800/40">
                    <td className="px-6 py-3 text-white font-medium">{t.keyword}</td>
                    <td className="px-6 py-3">
                      <span className={platformBadge(t.platform)}>{t.platform || '—'}</span>
                    </td>
                    <td className="px-6 py-3 text-gray-300">{t.volume.toLocaleString()}</td>
                    <td className="px-6 py-3">
                      <div className="h-2 rounded-full bg-gray-800 overflow-hidden max-w-[120px]">
                        <div
                          className={`h-full rounded-full ${velocityBarClass(vel)}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </td>
                    <td className="px-6 py-3">
                      <span className={strengthBadgeClass(t.strength)}>{t.strength}</span>
                    </td>
                    <td className="px-6 py-3 text-center text-gray-300">
                      {t.is_actionable ? (
                        <Check className="inline text-emerald-400" size={20} aria-label="Yes" />
                      ) : (
                        <X className="inline text-red-400" size={20} aria-label="No" />
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
