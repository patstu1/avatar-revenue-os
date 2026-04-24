'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { analyticsApi } from '@/lib/analytics-api';
import { BarChart3, TrendingUp, AlertTriangle, Trophy } from 'lucide-react';

type Brand = { id: string; name: string };

type ContentPerfRow = {
  content_id: string;
  title: string;
  status: string;
  platform: string | null;
  impressions: number;
  views: number;
  clicks: number;
  revenue: number;
  cost: number;
  profit: number;
  rpm: number;
  ctr: number;
  engagement_rate: number;
  avg_watch_pct: number;
};

type BottleneckRow = {
  account_id: string;
  username: string;
  platform: string;
  primary_bottleneck: string;
  severity: string;
  explanation: string;
  recommended_actions: string[];
  all_bottlenecks: string[];
};

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

function severityBadge(sev: string) {
  const s = (sev || '').toLowerCase();
  if (s === 'critical') return 'badge-red';
  if (s === 'warning') return 'badge-yellow';
  return 'badge-blue';
}

function fmtMoney(n: number) {
  return `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function AnalyticsDashboardPage() {
  const queryClient = useQueryClient();
  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [winnersResult, setWinnersResult] = useState<Record<string, unknown> | null>(null);

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
    data: performance,
    isLoading: perfLoading,
    isError: perfError,
    error: perfErr,
  } = useQuery({
    queryKey: ['analytics-content-performance', selectedBrandId],
    queryFn: () => analyticsApi.contentPerformance(selectedBrandId).then((r) => r.data as ContentPerfRow[]),
    enabled: Boolean(selectedBrandId),
  });

  const {
    data: bottlenecks,
    isLoading: bnLoading,
    isError: bnError,
    error: bnErr,
  } = useQuery({
    queryKey: ['analytics-bottlenecks', selectedBrandId],
    queryFn: () => analyticsApi.bottlenecks(selectedBrandId).then((r) => r.data as BottleneckRow[]),
    enabled: Boolean(selectedBrandId),
  });

  const detectMutation = useMutation({
    mutationFn: () => analyticsApi.detectWinners(selectedBrandId).then((r) => r.data),
    onSuccess: (data) => {
      setWinnersResult(data as Record<string, unknown>);
      queryClient.invalidateQueries({ queryKey: ['analytics-content-performance', selectedBrandId] });
    },
  });

  const selectedBrand = useMemo(
    () => brands?.find((b) => String(b.id) === selectedBrandId),
    [brands, selectedBrandId]
  );

  useEffect(() => {
    setWinnersResult(null);
  }, [selectedBrandId]);

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
        <h1 className="text-2xl font-bold text-white">Analytics</h1>
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
            Analytics Dashboard
          </h1>
          <p className="text-gray-400 mt-1">Content performance and account bottlenecks</p>
        </div>
        <div className="card text-center py-12">
          <TrendingUp className="mx-auto text-gray-600 mb-4" size={48} aria-hidden />
          <p className="text-gray-500">No brands yet. Create a brand to view analytics.</p>
        </div>
      </div>
    );
  }

  const mainLoading = perfLoading || bnLoading;
  const mainError = perfError || bnError;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="text-brand-500" size={28} aria-hidden />
            Analytics Dashboard
          </h1>
          <p className="text-gray-400 mt-1">Content performance, bottlenecks, and winner detection</p>
        </div>
        <button
          type="button"
          className="btn-primary inline-flex items-center justify-center gap-2 shrink-0 disabled:opacity-50"
          disabled={!selectedBrandId || detectMutation.isPending}
          onClick={() => detectMutation.mutate()}
        >
          <Trophy size={18} className={detectMutation.isPending ? 'animate-pulse' : ''} aria-hidden />
          {detectMutation.isPending ? 'Detecting…' : 'Detect Winners'}
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

      {detectMutation.isError && (
        <div className="card border-red-900/50 text-red-300 text-sm">{errMessage(detectMutation.error)}</div>
      )}

      {winnersResult && (
        <div className="card space-y-3">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <Trophy size={20} className="text-amber-400" aria-hidden />
            Winner detection result
          </h3>
          <p className="text-sm text-gray-400">
            Analyzed {String(winnersResult.total_analyzed ?? '—')} items ·{' '}
            <span className="text-emerald-300">{String((winnersResult.winners as unknown[])?.length ?? 0)} winners</span>
            {' · '}
            <span className="text-gray-500">{String((winnersResult.losers as unknown[])?.length ?? 0)} losers</span>
            {' · '}
            Clone jobs created: {String(winnersResult.clone_jobs_created ?? 0)}
          </p>
          {Array.isArray(winnersResult.winners) && (winnersResult.winners as { title?: string; explanation?: string }[]).length > 0 && (
            <ul className="text-sm text-gray-300 space-y-2 border-t border-gray-800 pt-3">
              {(winnersResult.winners as { title?: string; explanation?: string; win_score?: number }[]).slice(0, 5).map((w, i) => (
                <li key={i} className="bg-gray-800/40 rounded-lg px-3 py-2">
                  <span className="font-medium text-white">{w.title}</span>
                  {w.win_score != null && <span className="text-gray-500 ml-2">score {Number(w.win_score).toFixed(2)}</span>}
                  {w.explanation && <p className="text-gray-500 text-xs mt-1">{w.explanation}</p>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {mainLoading && <div className="card text-center py-12 text-gray-500">Loading analytics…</div>}

      {mainError && !mainLoading && (
        <div className="card border-red-900/50 text-red-300 py-8 text-center">
          {perfError && <>Performance: {errMessage(perfErr)} </>}
          {bnError && <>Bottlenecks: {errMessage(bnErr)}</>}
        </div>
      )}

      {!mainLoading && !mainError && performance && (
        <div className="card overflow-x-auto">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <TrendingUp size={20} className="text-brand-500" aria-hidden />
            Content performance
          </h3>
          {!performance.length ? (
            <p className="text-gray-500 text-sm py-8 text-center">No content items for this brand.</p>
          ) : (
            <table className="w-full text-sm text-left min-w-[880px]">
              <thead>
                <tr className="text-gray-500 border-b border-gray-800">
                  <th className="pb-3 pr-3 font-medium stat-label">Title</th>
                  <th className="pb-3 pr-3 font-medium stat-label">Platform</th>
                  <th className="pb-3 pr-3 font-medium stat-label text-right">Impressions</th>
                  <th className="pb-3 pr-3 font-medium stat-label text-right">Revenue</th>
                  <th className="pb-3 pr-3 font-medium stat-label text-right">Profit</th>
                  <th className="pb-3 pr-3 font-medium stat-label text-right">RPM</th>
                  <th className="pb-3 pr-3 font-medium stat-label text-right">CTR</th>
                  <th className="pb-3 font-medium stat-label text-right">Engagement</th>
                </tr>
              </thead>
              <tbody className="text-gray-200">
                {performance.map((row) => (
                  <tr key={row.content_id} className="border-b border-gray-800/80">
                    <td className="py-3 pr-3 max-w-[220px]">
                      <span className="font-medium text-white line-clamp-2">{row.title}</span>
                      <span className="text-xs text-gray-500 block mt-0.5">{String(row.status)}</span>
                    </td>
                    <td className="py-3 pr-3">
                      {row.platform ? <span className="badge-blue">{String(row.platform)}</span> : <span className="text-gray-600">—</span>}
                    </td>
                    <td className="py-3 pr-3 text-right tabular-nums">{Number(row.impressions).toLocaleString()}</td>
                    <td className="py-3 pr-3 text-right tabular-nums">{fmtMoney(row.revenue)}</td>
                    <td className="py-3 pr-3 text-right tabular-nums">{fmtMoney(row.profit)}</td>
                    <td className="py-3 pr-3 text-right tabular-nums">{fmtMoney(row.rpm)}</td>
                    <td className="py-3 pr-3 text-right tabular-nums">{(Number(row.ctr) * 100).toFixed(2)}%</td>
                    <td className="py-3 text-right tabular-nums">{(Number(row.engagement_rate) * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {!mainLoading && !mainError && bottlenecks && (
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <AlertTriangle size={20} className="text-amber-400" aria-hidden />
            Account bottlenecks
          </h3>
          {!bottlenecks.length ? (
            <p className="text-gray-500 text-sm py-6 text-center">No active creator accounts.</p>
          ) : (
            <div className="space-y-4">
              {bottlenecks.map((b) => (
                <div key={b.account_id} className="card-hover space-y-2">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="text-white font-medium">
                        {b.username}{' '}
                        <span className="text-gray-500 font-normal">· {b.platform}</span>
                      </p>
                      <p className="text-sm text-gray-400 mt-1">
                        <span className="text-gray-500">Primary: </span>
                        {String(b.primary_bottleneck)}
                      </p>
                    </div>
                    <span className={severityBadge(b.severity)}>{b.severity}</span>
                  </div>
                  <p className="text-sm text-gray-500">{b.explanation}</p>
                  {b.recommended_actions?.length > 0 && (
                    <div>
                      <p className="stat-label mb-2">Recommended actions</p>
                      <ul className="list-disc list-inside text-sm text-gray-300 space-y-1">
                        {b.recommended_actions.map((a, i) => (
                          <li key={i}>{a}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
