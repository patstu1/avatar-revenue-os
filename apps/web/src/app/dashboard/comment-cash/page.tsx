'use client';

import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { phase7Api } from '@/lib/phase7-api';
import { MessageSquareDot } from 'lucide-react';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

export default function CommentCashPage() {
  const [selectedBrandId, setSelectedBrandId] = useState('');

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) {
      setSelectedBrandId(String(brands[0].id));
    }
  }, [brands, selectedBrandId]);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['comment-cash', selectedBrandId],
    queryFn: () => phase7Api.commentCashSignals(selectedBrandId).then((r) => r.data),
    enabled: Boolean(selectedBrandId),
  });

  const selectedBrand = useMemo(
    () => brands?.find((b) => String(b.id) === selectedBrandId),
    [brands, selectedBrandId]
  );

  const signals = (data?.signals || data || []) as any[];

  if (brandsLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-96 bg-gray-800 rounded animate-pulse" />
        <div className="card py-12 text-center text-gray-500">Loading…</div>
      </div>
    );
  }

  if (brandsError) {
    return <div className="card border-red-900/50 text-red-300 py-8 text-center">{errMessage(brandsErr)}</div>;
  }

  if (!brands?.length) {
    return <div className="card text-center py-12 text-gray-500">Create a brand to view comment-to-cash signals.</div>;
  }

  return (
    <div className="space-y-8 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <MessageSquareDot className="text-brand-500" size={28} aria-hidden />
          Comment-to-Cash
        </h1>
        <p className="text-gray-400 mt-1 max-w-3xl">
          Phase 7 comment analysis — revenue signals extracted from audience engagement patterns.
        </p>
      </div>

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          value={selectedBrandId}
          onChange={(e) => setSelectedBrandId(e.target.value)}
          aria-label="Select brand for comment-to-cash signals"
        >
          {brands.map((b) => (
            <option key={b.id} value={String(b.id)}>
              {b.name}
            </option>
          ))}
        </select>
        {selectedBrand && <p className="text-sm text-gray-500 mt-2">Viewing: {selectedBrand.name}</p>}
      </div>

      {isLoading && <div className="card py-12 text-center text-gray-500">Analyzing comment signals…</div>}
      {isError && <div className="card border-red-900/50 text-red-300 py-6">{errMessage(error)}</div>}

      {!isLoading && !isError && Array.isArray(signals) && (
        <div className="space-y-3">
          {signals.map((s: any, i: number) => {
            const strength = Number(s.strength ?? s.signal_strength ?? 0);
            const strengthPct = Math.min(Math.max(strength * 100, 0), 100);
            return (
              <div key={s.id || i} className="card">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-3">
                  <div className="flex items-center gap-3">
                    <span className="inline-block px-2 py-0.5 rounded text-xs bg-brand-600/25 text-brand-300 uppercase tracking-wide">
                      {s.signal_type || s.type || 'signal'}
                    </span>
                    <span className="text-white font-medium">
                      {s.suggested_content_angle || s.content_angle || s.title || '—'}
                    </span>
                  </div>
                  {s.revenue_potential != null && (
                    <span className="text-emerald-300 font-semibold shrink-0">
                      ${Number(s.revenue_potential).toLocaleString()} rev potential
                    </span>
                  )}
                </div>

                <div className="mb-3">
                  <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                    <span>Strength</span>
                    <span>{strengthPct.toFixed(0)}%</span>
                  </div>
                  <div className="w-full bg-gray-800 rounded-full h-2">
                    <div
                      className="bg-brand-500 h-2 rounded-full transition-all"
                      style={{ width: `${strengthPct}%` }}
                    />
                  </div>
                </div>

                {(s.explanation || s.rationale) && (
                  <p className="text-sm text-gray-400">{s.explanation || s.rationale}</p>
                )}
              </div>
            );
          })}

          {!signals.length && (
            <div className="card text-center py-12 text-gray-500">
              No comment-to-cash signals detected yet. Ingest engagement data to generate signals.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
