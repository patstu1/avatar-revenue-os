'use client';

import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { analyticsApi } from '@/lib/analytics-api';
import { DollarSign, Wallet, TrendingUp, ArrowDown } from 'lucide-react';

type Brand = { id: string; name: string };

type RevenueDash = {
  gross_revenue: number;
  attribution_revenue: number;
  total_revenue: number;
  total_cost: number;
  net_profit: number;
  revenue_by_platform: Record<string, { revenue: number; impressions: number }>;
};

type FunnelData = {
  impressions: number;
  total_clicks: number;
  funnel_stages: Record<string, { count: number; value: number }>;
};

const FUNNEL_ORDER = [
  'click',
  'opt_in',
  'lead',
  'booked_call',
  'purchase',
  'coupon_redemption',
  'affiliate_conversion',
  'assisted_conversion',
];

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

function fmtMoney(n: number) {
  return `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function FunnelRow({
  label,
  count,
  value,
  max,
  prevCount,
  showValue,
}: {
  label: string;
  count: number;
  value: number;
  max: number;
  prevCount: number | null;
  showValue: boolean;
}) {
  const pctOfMax = max > 0 ? Math.min(100, (count / max) * 100) : 0;
  const dropPct =
    prevCount != null && prevCount > 0 && count <= prevCount
      ? (((prevCount - count) / prevCount) * 100).toFixed(1)
      : null;

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="text-gray-300 font-medium capitalize">{label}</span>
        <div className="text-right">
          <span className="text-white tabular-nums">{count.toLocaleString()}</span>
          {showValue && (
            <>
              <span className="text-gray-500 mx-2">·</span>
              <span className="text-emerald-300/90 tabular-nums">{fmtMoney(value)}</span>
            </>
          )}
        </div>
      </div>
      <div className="h-2.5 rounded-full bg-gray-800 overflow-hidden">
        <div
          className="h-full rounded-full bg-gradient-to-r from-brand-600 to-brand-400 transition-all"
          style={{ width: `${pctOfMax}%` }}
        />
      </div>
      {dropPct != null && Number(dropPct) > 0 && (
        <p className="text-xs text-gray-500 flex items-center gap-1">
          <ArrowDown size={12} className="shrink-0 text-amber-500" aria-hidden />
          {dropPct}% drop from previous stage
        </p>
      )}
    </div>
  );
}

export default function RevenueDashboardPage() {
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
    data: revenue,
    isLoading: revLoading,
    isError: revError,
    error: revErr,
  } = useQuery({
    queryKey: ['analytics-revenue-dashboard', selectedBrandId],
    queryFn: () => analyticsApi.revenueDashboard(selectedBrandId).then((r) => r.data as RevenueDash),
    enabled: Boolean(selectedBrandId),
    refetchInterval: 60_000,
  });

  const {
    data: funnel,
    isLoading: funnelLoading,
    isError: funnelError,
    error: funnelErr,
  } = useQuery({
    queryKey: ['analytics-funnel', selectedBrandId],
    queryFn: () => analyticsApi.funnelDashboard(selectedBrandId).then((r) => r.data as FunnelData),
    enabled: Boolean(selectedBrandId),
    refetchInterval: 60_000,
  });

  const selectedBrand = useMemo(
    () => brands?.find((b) => String(b.id) === selectedBrandId),
    [brands, selectedBrandId]
  );

  const funnelStages = funnel?.funnel_stages ?? {};
  const funnelRows = useMemo(() => {
    if (!funnel) return [];
    const stages = funnel.funnel_stages ?? {};
    const rows: { label: string; count: number; value: number; showValue: boolean }[] = [
      { label: 'Impressions', count: funnel.impressions, value: 0, showValue: false },
      {
        label: 'Clicks',
        count: funnel.total_clicks,
        value: stages.click?.value ?? 0,
        showValue: true,
      },
      ...FUNNEL_ORDER.filter((k) => k !== 'click').map((k) => ({
        label: k.replace(/_/g, ' '),
        count: stages[k]?.count ?? 0,
        value: stages[k]?.value ?? 0,
        showValue: true,
      })),
    ];
    return rows;
  }, [funnel]);

  const maxFunnel = funnelRows.length ? Math.max(...funnelRows.map((r) => r.count), 1) : 0;

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
        <h1 className="text-2xl font-bold text-white">Revenue</h1>
        <div className="card border-red-900/50 text-red-300 py-8 text-center">Failed to load brands: {errMessage(brandsErr)}</div>
      </div>
    );
  }

  if (!brands?.length) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <DollarSign className="text-brand-500" size={28} aria-hidden />
            Revenue Dashboard
          </h1>
          <p className="text-gray-400 mt-1">Revenue metrics and attribution funnel</p>
        </div>
        <div className="card text-center py-12">
          <Wallet className="mx-auto text-gray-600 mb-4" size={48} aria-hidden />
          <p className="text-gray-500">No brands yet. Create a brand to view revenue.</p>
        </div>
      </div>
    );
  }

  const loading = revLoading || funnelLoading;
  const err = revError || funnelError;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <DollarSign className="text-brand-500" size={28} aria-hidden />
          Revenue Dashboard
        </h1>
        <p className="text-gray-400 mt-1">Revenue metrics, funnel drop-off, and platform breakdown</p>
      </div>

      <div className="card">
        <label htmlFor="revenue-brand-select" className="stat-label block mb-2">
          Brand
        </label>
        <select
          id="revenue-brand-select"
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

      {loading && <div className="card text-center py-12 text-gray-500">Loading revenue and funnel…</div>}

      {err && !loading && (
        <div className="card border-red-900/50 text-red-300 py-8 text-center">
          {revError && <>Revenue: {errMessage(revErr)} </>}
          {funnelError && <>Funnel: {errMessage(funnelErr)}</>}
        </div>
      )}

      {!loading && !err && revenue && funnel && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            <div className="card-hover">
              <p className="stat-label flex items-center gap-1">
                <DollarSign size={14} aria-hidden /> Gross
              </p>
              <p className="stat-value mt-2 text-emerald-400">{fmtMoney(revenue.gross_revenue)}</p>
            </div>
            <div className="card-hover">
              <p className="stat-label flex items-center gap-1">
                <TrendingUp size={14} aria-hidden /> Attribution
              </p>
              <p className="stat-value mt-2 text-sky-400">{fmtMoney(revenue.attribution_revenue)}</p>
            </div>
            <div className="card-hover">
              <p className="stat-label flex items-center gap-1">
                <Wallet size={14} aria-hidden /> Total revenue
              </p>
              <p className="stat-value mt-2 text-white">{fmtMoney(revenue.total_revenue)}</p>
            </div>
            <div className="card-hover">
              <p className="stat-label">Cost</p>
              <p className="stat-value mt-2 text-amber-300">{fmtMoney(revenue.total_cost)}</p>
            </div>
            <div className="card-hover">
              <p className="stat-label">Net profit</p>
              <p className="stat-value mt-2 text-teal-300">{fmtMoney(revenue.net_profit)}</p>
            </div>
          </div>

          <div className="card">
            <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
              <ArrowDown size={22} className="text-brand-500" aria-hidden />
              Funnel
            </h3>
            <div className="space-y-6 max-w-3xl">
              {funnelRows.map((row, i) => (
                <FunnelRow
                  key={`${row.label}-${i}`}
                  label={row.label}
                  count={row.count}
                  value={row.value}
                  max={maxFunnel}
                  prevCount={i === 0 ? null : funnelRows[i - 1].count}
                  showValue={row.showValue}
                />
              ))}
            </div>
          </div>

          {revenue.revenue_by_platform && Object.keys(revenue.revenue_by_platform).length > 0 && (
            <div className="card">
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <TrendingUp size={20} className="text-brand-500" aria-hidden />
                Revenue by platform
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {Object.entries(revenue.revenue_by_platform).map(([platform, row]) => (
                  <div key={platform} className="card-hover">
                    <p className="text-xs text-gray-500 uppercase tracking-wider">{platform}</p>
                    <p className="text-xl font-bold text-white mt-1">{fmtMoney(row.revenue)}</p>
                    <p className="text-xs text-gray-500 mt-1">{Number(row.impressions).toLocaleString()} impressions</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
