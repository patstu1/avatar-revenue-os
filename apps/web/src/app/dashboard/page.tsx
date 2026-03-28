'use client';

import { useEffect, useMemo, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { dashboardApi, brandsApi, healthApi } from '@/lib/api';
import { analyticsApi } from '@/lib/analytics-api';
import {
  DollarSign,
  TrendingUp,
  Eye,
  MousePointerClick,
  BarChart3,
  Zap,
  AlertTriangle,
  CheckCircle2,
} from 'lucide-react';

type Brand = { id: string; name: string };

type RevenueDash = {
  gross_revenue: number;
  net_profit: number;
  total_impressions: number;
  avg_ctr: number;
  rpm: number;
  epc: number;
  total_conversions: number;
  revenue_by_platform: Record<string, { revenue: number; impressions: number }>;
};

type Overview = {
  total_content_items: number;
  recent_audit_actions: Array<{
    action: string;
    actor_type?: string;
    entity_type?: string;
    created_at?: string;
  }>;
  total_system_jobs: number;
};

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

function StatCard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: string;
  icon: LucideIcon;
  color: string;
}) {
  return (
    <div className="card-hover">
      <div className="flex items-start justify-between">
        <div>
          <p className="stat-label">{label}</p>
          <p className="stat-value mt-1" style={{ color }}>
            {value}
          </p>
        </div>
        <div className="p-2 rounded-lg" style={{ backgroundColor: `${color}15` }}>
          <Icon size={20} style={{ color }} />
        </div>
      </div>
    </div>
  );
}

export default function DashboardOverviewPage() {
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

  const { data: overview, isLoading: overviewLoading, isError: overviewError, error: overviewErr } = useQuery({
    queryKey: ['dashboard-overview'],
    queryFn: () => dashboardApi.overview().then((r) => r.data as Overview),
    refetchInterval: 30_000,
  });

  const {
    data: revenue,
    isLoading: revenueLoading,
    isError: revenueError,
    error: revenueErr,
  } = useQuery({
    queryKey: ['analytics-revenue-dashboard', selectedBrandId],
    queryFn: () => analyticsApi.revenueDashboard(selectedBrandId).then((r) => r.data as RevenueDash),
    enabled: Boolean(selectedBrandId),
    refetchInterval: 30_000,
  });

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => healthApi.readyz().then((r) => r.data),
    refetchInterval: 30_000,
  });

  const selectedBrand = useMemo(
    () => brands?.find((b) => String(b.id) === selectedBrandId),
    [brands, selectedBrandId]
  );

  const fmtMoney = (n: number) =>
    `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const ctrPct = revenue ? (Number(revenue.avg_ctr) * 100).toFixed(2) : '0.00';

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
        <h1 className="text-2xl font-bold text-white">Overview</h1>
        <div className="card border-red-900/50 text-red-300 py-8 text-center">Failed to load brands: {errMessage(brandsErr)}</div>
      </div>
    );
  }

  if (!brands?.length) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Overview Dashboard</h1>
          <p className="text-gray-400 mt-1">Revenue and entity snapshot for your organization</p>
        </div>
        <div className="card text-center py-12">
          <BarChart3 className="mx-auto text-gray-600 mb-4" size={48} aria-hidden />
          <p className="text-gray-500">No brands yet. Create a brand to see the overview.</p>
        </div>
      </div>
    );
  }

  const dataLoading = overviewLoading || revenueLoading;
  const dataError = overviewError || revenueError;

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Overview Dashboard</h1>
          <p className="text-gray-400 mt-1">Brand-scoped revenue metrics plus org-wide entity counts</p>
        </div>
        <div className="flex items-center gap-2">
          {health?.status === 'ready' ? (
            <span className="badge-green">
              <CheckCircle2 size={12} className="mr-1" /> System Healthy
            </span>
          ) : (
            <span className="badge-yellow">
              <AlertTriangle size={12} className="mr-1" /> Connecting…
            </span>
          )}
        </div>
      </div>

      <div className="card">
        <label htmlFor="dash-brand-select" className="stat-label block mb-2">
          Brand
        </label>
        <select
          id="dash-brand-select"
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

      {dataLoading && <div className="text-gray-500 text-center py-8">Loading dashboard data…</div>}

      {dataError && !dataLoading && (
        <div className="card border-red-900/50 text-red-300 py-8 text-center">
          {overviewError && <>Overview: {errMessage(overviewErr)} </>}
          {revenueError && <>Revenue: {errMessage(revenueErr)}</>}
        </div>
      )}

      {!dataLoading && !dataError && revenue && overview && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Gross Revenue" value={fmtMoney(revenue.gross_revenue)} icon={DollarSign} color="#22c55e" />
            <StatCard label="Net Profit" value={fmtMoney(revenue.net_profit)} icon={TrendingUp} color="#14b8a6" />
            <StatCard
              label="Total Impressions"
              value={Number(revenue.total_impressions).toLocaleString()}
              icon={Eye}
              color="#8b5cf6"
            />
            <StatCard label="Avg CTR" value={`${ctrPct}%`} icon={MousePointerClick} color="#3b82f6" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="RPM" value={fmtMoney(revenue.rpm)} icon={BarChart3} color="#f59e0b" />
            <StatCard label="EPC" value={fmtMoney(revenue.epc)} icon={DollarSign} color="#f97316" />
            <StatCard
              label="Conversions"
              value={String(revenue.total_conversions)}
              icon={Zap}
              color="#6366f1"
            />
            <StatCard
              label="Total Content Items"
              value={String(overview.total_content_items ?? 0)}
              icon={BarChart3}
              color="#ec4899"
            />
          </div>

          {revenue.revenue_by_platform && Object.keys(revenue.revenue_by_platform).length > 0 && (
            <div className="card">
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <BarChart3 size={20} className="text-brand-500" aria-hidden />
                Revenue by platform
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {Object.entries(revenue.revenue_by_platform).map(([platform, row]) => (
                  <div key={platform} className="bg-gray-800/50 rounded-lg px-4 py-3">
                    <p className="text-xs text-gray-500 uppercase tracking-wider">{platform}</p>
                    <p className="text-lg font-bold text-white mt-1">{fmtMoney(row.revenue)}</p>
                    <p className="text-xs text-gray-500 mt-1">{Number(row.impressions).toLocaleString()} impressions</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="card">
              <h3 className="text-lg font-semibold text-white mb-4">Recent actions</h3>
              {!overview.recent_audit_actions?.length ? (
                <p className="text-gray-500 text-sm py-6 text-center">No recent actions.</p>
              ) : (
                <div className="space-y-2">
                  {overview.recent_audit_actions.map((a, i) => (
                    <div key={i} className="flex items-center justify-between py-2 px-3 bg-gray-800/50 rounded-lg gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-gray-200 truncate">{a.action}</p>
                        {a.entity_type && <p className="text-xs text-gray-500">{a.entity_type}</p>}
                      </div>
                      <div className="text-right shrink-0">
                        <span className="text-xs text-gray-500 block">{a.actor_type}</span>
                        {a.created_at && (
                          <span className="text-xs text-gray-600 block mt-0.5">
                            {new Date(a.created_at).toLocaleString()}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="card">
              <h3 className="text-lg font-semibold text-white mb-4">System status</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-400">API server</span>
                  <span className="badge-green">Online</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-400">Database</span>
                  <span className={health?.checks?.database ? 'badge-green' : 'badge-red'}>
                    {health?.checks?.database ? 'Connected' : 'Disconnected'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-400">Workers</span>
                  <span className="badge-blue">Standby</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-400">System jobs</span>
                  <span className="badge-blue">{overview.total_system_jobs ?? 0} recorded</span>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
