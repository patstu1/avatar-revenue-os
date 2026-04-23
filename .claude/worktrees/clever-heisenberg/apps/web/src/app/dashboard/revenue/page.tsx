'use client';

import { useEffect, useMemo, useState, useCallback } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { analyticsApi } from '@/lib/analytics-api';
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  ArrowUpRight,
  ArrowDownRight,
  Clock,
  Wallet,
  BarChart3,
  ChevronUp,
  ChevronDown,
  Zap,
  EyeOff,
  Layers,
  Monitor,
  RefreshCw,
} from 'lucide-react';

/* ────────────────────────────── types ────────────────────────────── */

type Brand = { id: string; name: string };

type RevenueSummary = {
  gross_revenue: number;
  net_revenue: number;
  pending_revenue: number;
  gross_trend: number; // percent change vs last period
  net_trend: number;
  pending_trend: number;
  revenue_by_source: Record<string, { amount: number; pct: number }>;
  revenue_by_platform: Record<string, { amount: number; pct: number }>;
};

type TimelinePoint = {
  date: string;
  revenue: number;
};

type RevenueTimeline = {
  points: TimelinePoint[];
  granularity: string;
};

type AttributionRow = {
  id: string;
  name: string;
  revenue: number;
  clicks: number;
  conversions: number;
};

type RevenueAttribution = {
  by_content: AttributionRow[];
  by_platform: AttributionRow[];
  by_offer: AttributionRow[];
};

type OfferPerf = {
  id: string;
  name: string;
  type: string;
  revenue: number;
  clicks: number;
  conversion_rate: number;
  status: string;
};

/* ────────────────────────────── helpers ────────────────────────────── */

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

function fmtMoney(n: number) {
  return `$${Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtPct(n: number) {
  return `${(Number(n || 0) * 100).toFixed(1)}%`;
}

function fmtPctRaw(n: number) {
  return `${Number(n || 0).toFixed(1)}%`;
}

function fmtNum(n: number) {
  return Number(n || 0).toLocaleString();
}

const SOURCE_LABELS: Record<string, string> = {
  affiliate: 'Affiliate',
  sponsor: 'Sponsor',
  direct_sales: 'Direct Sales',
  services: 'Services',
  subscriptions: 'Subscriptions',
};

const PLATFORM_LABELS: Record<string, string> = {
  youtube: 'YouTube',
  tiktok: 'TikTok',
  instagram: 'Instagram',
  x: 'X (Twitter)',
  twitter: 'X (Twitter)',
};

const PLATFORM_COLORS: Record<string, string> = {
  youtube: 'bg-red-500',
  tiktok: 'bg-pink-500',
  instagram: 'bg-purple-500',
  x: 'bg-gray-400',
  twitter: 'bg-gray-400',
};

type SortDir = 'asc' | 'desc';

function useSortable<T>(data: T[], defaultKey: keyof T, defaultDir: SortDir = 'desc') {
  const [sortKey, setSortKey] = useState<keyof T>(defaultKey);
  const [sortDir, setSortDir] = useState<SortDir>(defaultDir);

  const sorted = useMemo(() => {
    if (!data?.length) return data ?? [];
    return [...data].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === 'number' && typeof bv === 'number') {
        return sortDir === 'asc' ? av - bv : bv - av;
      }
      return sortDir === 'asc'
        ? String(av).localeCompare(String(bv))
        : String(bv).localeCompare(String(av));
    });
  }, [data, sortKey, sortDir]);

  const toggle = useCallback(
    (key: keyof T) => {
      if (key === sortKey) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortKey(key);
        setSortDir('desc');
      }
    },
    [sortKey],
  );

  return { sorted, sortKey, sortDir, toggle };
}

/* ────────────────────────── SVG mini chart ───────────────────────── */

function RevenueChart({ points }: { points: TimelinePoint[] }) {
  if (!points?.length) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500 text-sm">
        No timeline data yet
      </div>
    );
  }

  const W = 800;
  const H = 240;
  const PAD_X = 60;
  const PAD_Y = 24;
  const chartW = W - PAD_X * 2;
  const chartH = H - PAD_Y * 2;

  const vals = points.map((p) => p.revenue);
  const maxV = Math.max(...vals, 1);
  const minV = Math.min(...vals, 0);
  const range = maxV - minV || 1;

  const toX = (i: number) => PAD_X + (i / Math.max(points.length - 1, 1)) * chartW;
  const toY = (v: number) => PAD_Y + chartH - ((v - minV) / range) * chartH;

  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${toX(i).toFixed(1)},${toY(p.revenue).toFixed(1)}`).join(' ');
  const areaPath = `${linePath} L${toX(points.length - 1).toFixed(1)},${(H - PAD_Y).toFixed(1)} L${PAD_X},${(H - PAD_Y).toFixed(1)} Z`;

  // Y-axis ticks
  const ticks = 5;
  const yTicks = Array.from({ length: ticks }, (_, i) => minV + (range * i) / (ticks - 1));

  // X-axis labels: show ~6
  const xStep = Math.max(1, Math.floor(points.length / 6));
  const xLabels = points.filter((_, i) => i % xStep === 0 || i === points.length - 1);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="rev-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgb(34 211 238)" stopOpacity="0.3" />
          <stop offset="100%" stopColor="rgb(34 211 238)" stopOpacity="0.02" />
        </linearGradient>
      </defs>

      {/* Grid lines */}
      {yTicks.map((v, i) => (
        <g key={i}>
          <line
            x1={PAD_X}
            y1={toY(v)}
            x2={W - PAD_X}
            y2={toY(v)}
            stroke="rgb(55 65 81)"
            strokeWidth="0.5"
            strokeDasharray="4 4"
          />
          <text x={PAD_X - 8} y={toY(v) + 4} textAnchor="end" fill="rgb(156 163 175)" fontSize="10">
            ${(v / 1000).toFixed(v >= 1000 ? 0 : 1)}
            {v >= 1000 ? 'k' : ''}
          </text>
        </g>
      ))}

      {/* X labels */}
      {xLabels.map((p) => {
        const idx = points.indexOf(p);
        return (
          <text
            key={p.date}
            x={toX(idx)}
            y={H - 4}
            textAnchor="middle"
            fill="rgb(156 163 175)"
            fontSize="10"
          >
            {new Date(p.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
          </text>
        );
      })}

      {/* Area + line */}
      <path d={areaPath} fill="url(#rev-grad)" />
      <path d={linePath} fill="none" stroke="rgb(34 211 238)" strokeWidth="2" />

      {/* Dots */}
      {points.map((p, i) => (
        <circle key={i} cx={toX(i)} cy={toY(p.revenue)} r="3" fill="rgb(34 211 238)">
          <title>
            {new Date(p.date).toLocaleDateString()}: {fmtMoney(p.revenue)}
          </title>
        </circle>
      ))}
    </svg>
  );
}

/* ──────────────────────── Trend arrow badge ──────────────────────── */

function TrendBadge({ value }: { value: number }) {
  if (value === 0) return <span className="text-xs text-gray-500 ml-2">--</span>;
  const up = value > 0;
  return (
    <span
      className={`inline-flex items-center gap-0.5 ml-2 text-xs font-medium ${up ? 'text-emerald-400' : 'text-red-400'}`}
    >
      {up ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
      {Math.abs(value).toFixed(1)}%
    </span>
  );
}

/* ──────────────────── Sort header helper ──────────────────── */

function SortHeader<T>({
  label,
  field,
  sortKey,
  sortDir,
  toggle,
  className,
}: {
  label: string;
  field: keyof T;
  sortKey: keyof T;
  sortDir: SortDir;
  toggle: (k: keyof T) => void;
  className?: string;
}) {
  const active = sortKey === field;
  return (
    <th
      className={`px-3 py-2 text-xs text-gray-400 uppercase tracking-wider cursor-pointer select-none whitespace-nowrap ${className ?? ''}`}
      onClick={() => toggle(field)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {active ? (
          sortDir === 'asc' ? (
            <ChevronUp size={12} />
          ) : (
            <ChevronDown size={12} />
          )
        ) : (
          <ChevronDown size={12} className="opacity-30" />
        )}
      </span>
    </th>
  );
}

/* ──────────────────────────── main page ──────────────────────────── */

export default function RevenueDashboardPage() {
  const queryClient = useQueryClient();
  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [timeRange, setTimeRange] = useState<string>('30d');
  const [granularity, setGranularity] = useState<string>('daily');

  /* ── Brands ── */
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

  /* ── Revenue Summary ── */
  const {
    data: summary,
    isLoading: summaryLoading,
    isError: summaryError,
    error: summaryErr,
  } = useQuery({
    queryKey: ['revenue-summary', selectedBrandId, timeRange],
    queryFn: () =>
      analyticsApi.revenueSummary(selectedBrandId, timeRange).then((r) => r.data as RevenueSummary),
    enabled: Boolean(selectedBrandId),
    refetchInterval: 60_000,
  });

  /* ── Timeline ── */
  const {
    data: timeline,
    isLoading: timelineLoading,
  } = useQuery({
    queryKey: ['revenue-timeline', selectedBrandId, granularity, timeRange],
    queryFn: () =>
      analyticsApi.revenueTimeline(selectedBrandId, granularity, timeRange).then((r) => r.data as RevenueTimeline),
    enabled: Boolean(selectedBrandId),
    refetchInterval: 60_000,
  });

  /* ── Attribution ── */
  const {
    data: attribution,
    isLoading: attrLoading,
  } = useQuery({
    queryKey: ['revenue-attribution', selectedBrandId],
    queryFn: () =>
      analyticsApi.revenueAttribution(selectedBrandId).then((r) => r.data as RevenueAttribution),
    enabled: Boolean(selectedBrandId),
    refetchInterval: 60_000,
  });

  /* ── Offers ── */
  const {
    data: offers,
    isLoading: offersLoading,
  } = useQuery({
    queryKey: ['revenue-offers', selectedBrandId],
    queryFn: () =>
      analyticsApi.revenueOffers(selectedBrandId).then((r) => r.data as OfferPerf[]),
    enabled: Boolean(selectedBrandId),
    refetchInterval: 60_000,
  });

  /* ── Boost / Suppress mutations ── */
  const boostMut = useMutation({
    mutationFn: (offerId: string) => analyticsApi.boostOffer(offerId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['revenue-offers'] }),
  });

  const suppressMut = useMutation({
    mutationFn: (offerId: string) => analyticsApi.suppressOffer(offerId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['revenue-offers'] }),
  });

  /* ── Sortable tables for attribution ── */
  const contentSort = useSortable<AttributionRow>(
    attribution?.by_content?.slice(0, 10) ?? [],
    'revenue',
  );
  const platformSort = useSortable<AttributionRow>(
    attribution?.by_platform?.slice(0, 10) ?? [],
    'revenue',
  );
  const offerAttrSort = useSortable<AttributionRow>(
    attribution?.by_offer?.slice(0, 10) ?? [],
    'revenue',
  );
  const offersSort = useSortable<OfferPerf>(offers ?? [], 'revenue');

  const selectedBrand = useMemo(
    () => brands?.find((b) => String(b.id) === selectedBrandId),
    [brands, selectedBrandId],
  );

  /* ── Revenue by source derived data ── */
  const sourceEntries = useMemo(() => {
    if (!summary?.revenue_by_source) return [];
    return Object.entries(summary.revenue_by_source).map(([key, val]) => ({
      key,
      label: SOURCE_LABELS[key] || key.replace(/_/g, ' '),
      amount: val.amount ?? 0,
      pct: val.pct ?? 0,
    }));
  }, [summary]);

  const platformEntries = useMemo(() => {
    if (!summary?.revenue_by_platform) return [];
    return Object.entries(summary.revenue_by_platform).map(([key, val]) => ({
      key,
      label: PLATFORM_LABELS[key] || key,
      amount: val.amount ?? 0,
      pct: val.pct ?? 0,
      color: PLATFORM_COLORS[key] || 'bg-cyan-500',
    }));
  }, [summary]);

  /* ── Early returns ── */

  if (brandsLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-64 bg-gray-800 rounded animate-pulse" />
        <div className="card py-12 text-center text-gray-500">Loading brands...</div>
      </div>
    );
  }

  if (brandsError) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Revenue</h1>
        <div className="card border-red-900/50 text-red-300 py-8 text-center">
          Failed to load brands: {errMessage(brandsErr)}
        </div>
      </div>
    );
  }

  if (!brands?.length) {
    return (
      <div className="space-y-6">
        <Header />
        <div className="card text-center py-12">
          <Wallet className="mx-auto text-gray-600 mb-4" size={48} aria-hidden />
          <p className="text-gray-500">No brands yet. Create a brand to view revenue.</p>
        </div>
      </div>
    );
  }

  const loading = summaryLoading || timelineLoading || attrLoading || offersLoading;

  return (
    <div className="space-y-6">
      <Header />

      {/* Brand selector + time range */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="card flex-1">
          <label htmlFor="rev-brand" className="stat-label block mb-2">
            Brand
          </label>
          <select
            id="rev-brand"
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
          {selectedBrand && (
            <p className="text-sm text-gray-500 mt-2">Viewing: {selectedBrand.name}</p>
          )}
        </div>

        <div className="card">
          <label className="stat-label block mb-2">Time Range</label>
          <div className="flex gap-2 flex-wrap">
            {['7d', '30d', '90d', 'all'].map((r) => (
              <button
                key={r}
                onClick={() => setTimeRange(r)}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                  timeRange === r
                    ? 'bg-cyan-600 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
              >
                {r === 'all' ? 'All Time' : r.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="card text-center py-12 text-gray-500 flex items-center justify-center gap-2">
          <RefreshCw size={18} className="animate-spin" />
          Loading revenue data...
        </div>
      )}

      {summaryError && !loading && (
        <div className="card border-red-900/50 text-red-300 py-8 text-center">
          {errMessage(summaryErr)}
        </div>
      )}

      {!loading && summary && (
        <>
          {/* ──────── Summary Cards ──────── */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="card-hover">
              <p className="stat-label flex items-center gap-1">
                <DollarSign size={14} aria-hidden /> Total Gross
              </p>
              <p className="stat-value mt-2 text-emerald-400">
                {fmtMoney(summary.gross_revenue)}
                <TrendBadge value={summary.gross_trend} />
              </p>
            </div>
            <div className="card-hover">
              <p className="stat-label flex items-center gap-1">
                <TrendingUp size={14} aria-hidden /> Net Revenue
              </p>
              <p className="stat-value mt-2 text-white">
                {fmtMoney(summary.net_revenue)}
                <TrendBadge value={summary.net_trend} />
              </p>
            </div>
            <div className="card-hover">
              <p className="stat-label flex items-center gap-1">
                <Clock size={14} aria-hidden /> Pending
              </p>
              <p className="stat-value mt-2 text-amber-300">
                {fmtMoney(summary.pending_revenue)}
                <TrendBadge value={summary.pending_trend} />
              </p>
            </div>
          </div>

          {/* ──────── Revenue by Source ──────── */}
          <div className="card">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Layers size={20} className="text-brand-500" aria-hidden />
              Revenue by Source
            </h3>
            {sourceEntries.length === 0 ? (
              <p className="text-gray-500 text-sm">No revenue data yet</p>
            ) : (
              <div className="space-y-4 max-w-2xl">
                {sourceEntries.map((s) => (
                  <div key={s.key}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-300 capitalize">{s.label}</span>
                      <span className="text-white tabular-nums">
                        {fmtMoney(s.amount)}{' '}
                        <span className="text-gray-500 ml-1">{fmtPctRaw(s.pct)}</span>
                      </span>
                    </div>
                    <div className="h-2.5 rounded-full bg-gray-800 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-cyan-600 to-cyan-400 transition-all"
                        style={{ width: `${Math.min(100, s.pct)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ──────── Revenue by Platform ──────── */}
          <div className="card">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Monitor size={20} className="text-brand-500" aria-hidden />
              Revenue by Platform
            </h3>
            {platformEntries.length === 0 ? (
              <p className="text-gray-500 text-sm">No platform data yet</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {platformEntries.map((p) => (
                  <div key={p.key} className="card-hover">
                    <div className="flex items-center gap-2 mb-2">
                      <div className={`w-3 h-3 rounded-full ${p.color}`} />
                      <p className="text-xs text-gray-500 uppercase tracking-wider">{p.label}</p>
                    </div>
                    <p className="text-xl font-bold text-white">{fmtMoney(p.amount)}</p>
                    <p className="text-xs text-gray-500 mt-1">{fmtPctRaw(p.pct)} of total</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ──────── Timeline Chart ──────── */}
          <div className="card">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <BarChart3 size={20} className="text-brand-500" aria-hidden />
                Revenue Over Time
              </h3>
              <div className="flex gap-2">
                {['daily', 'weekly', 'monthly'].map((g) => (
                  <button
                    key={g}
                    onClick={() => setGranularity(g)}
                    className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                      granularity === g
                        ? 'bg-cyan-600 text-white'
                        : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                    }`}
                  >
                    {g.charAt(0).toUpperCase() + g.slice(1)}
                  </button>
                ))}
              </div>
            </div>
            <RevenueChart points={timeline?.points ?? []} />
          </div>

          {/* ──────── Attribution Section ──────── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* By Content */}
            <div className="card overflow-hidden">
              <h3 className="text-sm font-semibold text-white mb-3 uppercase tracking-wider">
                Top Content
              </h3>
              {contentSort.sorted.length === 0 ? (
                <p className="text-gray-500 text-sm">No revenue data yet</p>
              ) : (
                <div className="overflow-x-auto -mx-4 sm:-mx-6">
                  <table className="w-full text-sm min-w-[320px]">
                    <thead>
                      <tr className="border-b border-gray-800">
                        <SortHeader<AttributionRow>
                          label="Content"
                          field="name"
                          {...contentSort}
                          className="text-left"
                        />
                        <SortHeader<AttributionRow>
                          label="Revenue"
                          field="revenue"
                          {...contentSort}
                          className="text-right"
                        />
                      </tr>
                    </thead>
                    <tbody>
                      {contentSort.sorted.map((row) => (
                        <tr key={row.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                          <td className="px-3 py-2 text-gray-300 truncate max-w-[180px]">
                            {row.name}
                          </td>
                          <td className="px-3 py-2 text-right text-white tabular-nums">
                            {fmtMoney(row.revenue)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* By Platform */}
            <div className="card overflow-hidden">
              <h3 className="text-sm font-semibold text-white mb-3 uppercase tracking-wider">
                Top Platforms
              </h3>
              {platformSort.sorted.length === 0 ? (
                <p className="text-gray-500 text-sm">No revenue data yet</p>
              ) : (
                <div className="overflow-x-auto -mx-4 sm:-mx-6">
                  <table className="w-full text-sm min-w-[320px]">
                    <thead>
                      <tr className="border-b border-gray-800">
                        <SortHeader<AttributionRow>
                          label="Platform"
                          field="name"
                          {...platformSort}
                          className="text-left"
                        />
                        <SortHeader<AttributionRow>
                          label="Revenue"
                          field="revenue"
                          {...platformSort}
                          className="text-right"
                        />
                      </tr>
                    </thead>
                    <tbody>
                      {platformSort.sorted.map((row) => (
                        <tr key={row.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                          <td className="px-3 py-2 text-gray-300">{row.name}</td>
                          <td className="px-3 py-2 text-right text-white tabular-nums">
                            {fmtMoney(row.revenue)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* By Offer */}
            <div className="card overflow-hidden">
              <h3 className="text-sm font-semibold text-white mb-3 uppercase tracking-wider">
                Top Offers
              </h3>
              {offerAttrSort.sorted.length === 0 ? (
                <p className="text-gray-500 text-sm">No revenue data yet</p>
              ) : (
                <div className="overflow-x-auto -mx-4 sm:-mx-6">
                  <table className="w-full text-sm min-w-[320px]">
                    <thead>
                      <tr className="border-b border-gray-800">
                        <SortHeader<AttributionRow>
                          label="Offer"
                          field="name"
                          {...offerAttrSort}
                          className="text-left"
                        />
                        <SortHeader<AttributionRow>
                          label="Revenue"
                          field="revenue"
                          {...offerAttrSort}
                          className="text-right"
                        />
                      </tr>
                    </thead>
                    <tbody>
                      {offerAttrSort.sorted.map((row) => (
                        <tr key={row.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                          <td className="px-3 py-2 text-gray-300 truncate max-w-[180px]">
                            {row.name}
                          </td>
                          <td className="px-3 py-2 text-right text-white tabular-nums">
                            {fmtMoney(row.revenue)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

          {/* ──────── Offer Performance Table ──────── */}
          <div className="card">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <DollarSign size={20} className="text-brand-500" aria-hidden />
              Offer Performance
            </h3>
            {!offers?.length ? (
              <p className="text-gray-500 text-sm">No revenue data yet</p>
            ) : (
              <div className="overflow-x-auto -mx-4 sm:-mx-6">
                <table className="w-full text-sm min-w-[700px]">
                  <thead>
                    <tr className="border-b border-gray-800">
                      <SortHeader<OfferPerf>
                        label="Offer"
                        field="name"
                        {...offersSort}
                        className="text-left"
                      />
                      <SortHeader<OfferPerf>
                        label="Type"
                        field="type"
                        {...offersSort}
                        className="text-left"
                      />
                      <SortHeader<OfferPerf>
                        label="Revenue"
                        field="revenue"
                        {...offersSort}
                        className="text-right"
                      />
                      <SortHeader<OfferPerf>
                        label="Clicks"
                        field="clicks"
                        {...offersSort}
                        className="text-right"
                      />
                      <SortHeader<OfferPerf>
                        label="Conv. Rate"
                        field="conversion_rate"
                        {...offersSort}
                        className="text-right"
                      />
                      <SortHeader<OfferPerf>
                        label="Status"
                        field="status"
                        {...offersSort}
                        className="text-left"
                      />
                      <th className="px-3 py-2 text-xs text-gray-400 uppercase tracking-wider text-right">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {offersSort.sorted.map((o) => (
                      <tr
                        key={o.id}
                        className="border-b border-gray-800/50 hover:bg-gray-800/30"
                      >
                        <td className="px-3 py-2.5 text-gray-200 font-medium truncate max-w-[200px]">
                          {o.name}
                        </td>
                        <td className="px-3 py-2.5 text-gray-400 capitalize">
                          {o.type?.replace(/_/g, ' ') || '--'}
                        </td>
                        <td className="px-3 py-2.5 text-right text-white tabular-nums">
                          {fmtMoney(o.revenue)}
                        </td>
                        <td className="px-3 py-2.5 text-right text-gray-300 tabular-nums">
                          {fmtNum(o.clicks)}
                        </td>
                        <td className="px-3 py-2.5 text-right text-gray-300 tabular-nums">
                          {fmtPct(o.conversion_rate)}
                        </td>
                        <td className="px-3 py-2.5">
                          <span
                            className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                              o.status === 'active'
                                ? 'bg-emerald-900/40 text-emerald-400'
                                : o.status === 'paused'
                                  ? 'bg-amber-900/40 text-amber-400'
                                  : 'bg-gray-800 text-gray-400'
                            }`}
                          >
                            {o.status || 'unknown'}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => boostMut.mutate(o.id)}
                              disabled={boostMut.isPending}
                              className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-cyan-900/40 text-cyan-300 hover:bg-cyan-800/60 transition-colors disabled:opacity-50"
                              title="Boost placement priority"
                            >
                              <Zap size={12} /> Boost
                            </button>
                            <button
                              onClick={() => suppressMut.mutate(o.id)}
                              disabled={suppressMut.isPending}
                              className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-gray-800 text-gray-400 hover:bg-gray-700 transition-colors disabled:opacity-50"
                              title="Suppress placement"
                            >
                              <EyeOff size={12} /> Suppress
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {/* Auto-refresh indicator */}
      <p className="text-xs text-gray-600 text-center flex items-center justify-center gap-1">
        <RefreshCw size={10} /> Auto-refreshes every 60s
      </p>
    </div>
  );
}

/* ── Page header (reused in empty and loaded states) ── */
function Header() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-white flex items-center gap-2">
        <DollarSign className="text-brand-500" size={28} aria-hidden />
        Revenue Dashboard
      </h1>
      <p className="text-gray-400 mt-1">
        Revenue metrics, attribution, timeline, and offer performance
      </p>
    </div>
  );
}
