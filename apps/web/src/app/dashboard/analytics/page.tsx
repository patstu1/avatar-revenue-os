'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { discoveryApi } from '@/lib/discovery-api';
import { BarChart3, RefreshCw, Target } from 'lucide-react';

type Brand = { id: string; name: string };

type NicheCluster = {
  id: string;
  cluster_name: string;
  keywords?: string[] | null;
  estimated_audience_size: number;
  monetization_potential: number;
  competition_density: number;
  content_gap_score: number;
  saturation_level: number;
  recommended_entry_angle?: string | null;
};

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

function barTone(v: number) {
  if (v > 0.6) return 'bg-emerald-500';
  if (v > 0.3) return 'bg-amber-500';
  return 'bg-red-500';
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const pct = Math.min(100, Math.max(0, Number(value) * 100));
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-gray-400">
        <span>{label}</span>
        <span>{pct.toFixed(0)}%</span>
      </div>
      <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
        <div className={`h-full rounded-full transition-all ${barTone(value)}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
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
    data: niches,
    isLoading: nichesLoading,
    isError: nichesError,
    error: nichesErr,
  } = useQuery({
    queryKey: ['discovery-niches', selectedBrandId],
    queryFn: () => discoveryApi.getNiches(selectedBrandId).then((r) => r.data as NicheCluster[]),
    enabled: Boolean(selectedBrandId),
  });

  const recomputeMutation = useMutation({
    mutationFn: () => discoveryApi.recomputeNiches(selectedBrandId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['discovery-niches', selectedBrandId] });
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
        <h1 className="text-2xl font-bold text-white">Niche Ranking Dashboard</h1>
        <div className="card border-red-900/50 text-red-300 py-8 text-center">Failed to load brands: {errMessage(brandsErr)}</div>
      </div>
    );
  }

  if (!brands?.length) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="text-brand-500" size={28} aria-hidden />
            Niche Ranking Dashboard
          </h1>
          <p className="text-gray-400 mt-1">Ranked niches by monetization potential, content gaps, and saturation</p>
        </div>
        <div className="card text-center py-12">
          <Target className="mx-auto text-gray-600 mb-4" size={48} aria-hidden />
          <p className="text-gray-500">No brands yet. Create a brand to view niche discovery.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="text-brand-500" size={28} aria-hidden />
            Niche Ranking Dashboard
          </h1>
          <p className="text-gray-400 mt-1">Ranked niches by monetization potential, content gaps, and saturation</p>
        </div>
        <button
          type="button"
          className="btn-primary flex items-center justify-center gap-2 shrink-0 disabled:opacity-50"
          disabled={!selectedBrandId || recomputeMutation.isPending}
          onClick={() => recomputeMutation.mutate()}
        >
          <RefreshCw size={16} className={recomputeMutation.isPending ? 'animate-spin' : ''} aria-hidden />
          Recompute Niches
        </button>
      </div>

      <div className="card">
        <label htmlFor="analytics-brand-select" className="stat-label block mb-2">
          Brand
        </label>
        <select
          id="analytics-brand-select"
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

      {nichesLoading && (
        <div className="card text-center py-12 text-gray-500">Loading niches…</div>
      )}

      {nichesError && !nichesLoading && (
        <div className="card border-red-900/50 text-red-300 py-8 text-center">Failed to load niches: {errMessage(nichesErr)}</div>
      )}

      {!nichesLoading && !nichesError && niches?.length === 0 && (
        <div className="card text-center py-12">
          <Target className="mx-auto text-gray-600 mb-4" size={40} aria-hidden />
          <p className="text-gray-500">No niche clusters yet. Run Recompute Niches after ingesting signals.</p>
        </div>
      )}

      {!nichesLoading && !nichesError && niches && niches.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {niches.map((n) => (
            <div key={n.id} className="card-hover space-y-4">
              <div className="flex items-start justify-between gap-2">
                <h2 className="text-lg font-semibold text-white">{n.cluster_name}</h2>
                <span className="badge-blue whitespace-nowrap">Audience: {n.estimated_audience_size.toLocaleString()}</span>
              </div>
              <div className="space-y-3">
                <ScoreBar label="Monetization potential" value={n.monetization_potential} />
                <ScoreBar label="Competition density" value={n.competition_density} />
                <ScoreBar label="Content gap" value={n.content_gap_score} />
                <ScoreBar label="Saturation" value={n.saturation_level} />
              </div>
              {n.keywords && n.keywords.length > 0 && (
                <div>
                  <p className="stat-label mb-2">Keywords</p>
                  <div className="flex flex-wrap gap-1.5">
                    {n.keywords.map((k, i) => (
                      <span key={`${n.id}-k-${i}`} className="badge-blue">
                        {typeof k === 'string' ? k : String(k)}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {n.recommended_entry_angle && (
                <p className="text-sm text-gray-300 border-t border-gray-800 pt-3">
                  <span className="text-gray-500">Entry angle: </span>
                  {n.recommended_entry_angle}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
