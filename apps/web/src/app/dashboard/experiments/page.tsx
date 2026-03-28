'use client';

import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { discoveryApi } from '@/lib/discovery-api';
import { AlertTriangle, BarChart3, Shield } from 'lucide-react';

type Brand = { id: string; name: string };

type SaturationRow = {
  id: string;
  saturation_score: number;
  fatigue_score: number;
  originality_score: number;
  topic_overlap_pct: number;
  audience_overlap_pct: number;
  recommended_action: string;
  explanation?: string | null;
  details?: { account_username?: string; platform?: string } | null;
};

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

/** Normalize to 0–1 for threshold coloring */
function norm01(v: number) {
  const n = Number(v);
  if (Number.isNaN(n)) return 0;
  return n > 1 ? n / 100 : n;
}

function barTone01(v01: number) {
  if (v01 > 0.6) return 'bg-emerald-500';
  if (v01 > 0.3) return 'bg-amber-500';
  return 'bg-red-500';
}

function ScoreBar({ label, rawValue }: { label: string; rawValue: number }) {
  const v01 = norm01(rawValue);
  const pct = Math.min(100, Math.max(0, v01 * 100));
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-gray-400">
        <span>{label}</span>
        <span>{pct.toFixed(0)}%</span>
      </div>
      <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
        <div className={`h-full rounded-full ${barTone01(v01)}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function actionBadge(action: string) {
  const a = (action || '').toLowerCase();
  if (a.includes('scale') || a.includes('expand')) return 'badge-green';
  if (a.includes('monitor') || a.includes('hold')) return 'badge-blue';
  if (a.includes('pause') || a.includes('cut')) return 'badge-red';
  return 'badge-yellow';
}

export default function ExperimentsPage() {
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
    data: saturation,
    isLoading: satLoading,
    isError: satError,
    error: satErr,
  } = useQuery({
    queryKey: ['discovery-saturation', selectedBrandId, true],
    queryFn: () => discoveryApi.getSaturation(selectedBrandId, true).then((r) => r.data as SaturationRow[]),
    enabled: Boolean(selectedBrandId),
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
        <h1 className="text-2xl font-bold text-white">Saturation &amp; Fatigue View</h1>
        <div className="card border-red-900/50 text-red-300 py-8 text-center">Failed to load brands: {errMessage(brandsErr)}</div>
      </div>
    );
  }

  if (!brands?.length) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <AlertTriangle className="text-brand-500" size={28} aria-hidden />
            Saturation &amp; Fatigue View
          </h1>
          <p className="text-gray-400 mt-1">Account-level saturation, fatigue, and originality analysis</p>
        </div>
        <div className="card text-center py-12">
          <Shield className="mx-auto text-gray-600 mb-4" size={48} aria-hidden />
          <p className="text-gray-500">No brands yet. Create a brand to view saturation reports.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <AlertTriangle className="text-brand-500" size={28} aria-hidden />
          Saturation &amp; Fatigue View
        </h1>
        <p className="text-gray-400 mt-1">Account-level saturation, fatigue, and originality analysis</p>
      </div>

      <div className="card">
        <label htmlFor="experiments-brand-select" className="stat-label block mb-2">
          Brand
        </label>
        <select
          id="experiments-brand-select"
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

      {satLoading && <div className="card text-center py-12 text-gray-500">Loading saturation analysis…</div>}

      {satError && !satLoading && (
        <div className="card border-red-900/50 text-red-300 py-8 text-center">Failed to load saturation: {errMessage(satErr)}</div>
      )}

      {!satLoading && !satError && saturation?.length === 0 && (
        <div className="card text-center py-12">
          <BarChart3 className="mx-auto text-gray-600 mb-4" size={40} aria-hidden />
          <p className="text-gray-500">No saturation reports for this brand. Add creator accounts and ingest signals.</p>
        </div>
      )}

      {!satLoading && !satError && saturation && saturation.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {saturation.map((row) => {
            const username = row.details?.account_username ?? 'Account';
            const platform = row.details?.platform ?? '—';
            return (
              <div key={row.id} className="card-hover space-y-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <h2 className="text-lg font-semibold text-white">{username}</h2>
                    <p className="text-sm text-gray-500 capitalize">{platform}</p>
                  </div>
                  <span className={actionBadge(row.recommended_action)}>{row.recommended_action}</span>
                </div>
                <div className="space-y-3">
                  <ScoreBar label="Saturation" rawValue={row.saturation_score} />
                  <ScoreBar label="Fatigue" rawValue={row.fatigue_score} />
                  <ScoreBar label="Originality" rawValue={row.originality_score} />
                  <ScoreBar label="Topic overlap" rawValue={row.topic_overlap_pct} />
                  <ScoreBar label="Audience overlap" rawValue={row.audience_overlap_pct} />
                </div>
                {row.explanation && <p className="text-sm text-gray-400 border-t border-gray-800 pt-3">{row.explanation}</p>}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
