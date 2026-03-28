'use client';

import { useQuery } from '@tanstack/react-query';
import { brandsApi, healthApi } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import {
  TrendingUp, DollarSign, Eye, MousePointerClick,
  BarChart3, Zap, AlertTriangle, CheckCircle2
} from 'lucide-react';

function StatCard({ label, value, icon: Icon, trend, color }: {
  label: string; value: string; icon: any; trend?: string; color: string;
}) {
  return (
    <div className="card-hover">
      <div className="flex items-start justify-between">
        <div>
          <p className="stat-label">{label}</p>
          <p className="stat-value mt-1" style={{ color }}>{value}</p>
          {trend && <p className="text-xs text-gray-500 mt-1">{trend}</p>}
        </div>
        <div className="p-2 rounded-lg" style={{ backgroundColor: `${color}15` }}>
          <Icon size={20} style={{ color }} />
        </div>
      </div>
    </div>
  );
}

export default function RevenueDashboard() {
  const { data: brands } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data),
  });

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => healthApi.readyz().then((r) => r.data),
    refetchInterval: 30_000,
  });

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Revenue Dashboard</h1>
          <p className="text-gray-400 mt-1">Real-time performance across all brands and accounts</p>
        </div>
        <div className="flex items-center gap-2">
          {health?.status === 'ready' ? (
            <span className="badge-green"><CheckCircle2 size={12} className="mr-1" /> System Healthy</span>
          ) : (
            <span className="badge-yellow"><AlertTriangle size={12} className="mr-1" /> Connecting...</span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Gross Revenue" value="$0.00" icon={DollarSign} trend="Awaiting data" color="#10b981" />
        <StatCard label="Net Profit" value="$0.00" icon={TrendingUp} trend="Awaiting data" color="#6366f1" />
        <StatCard label="Total Impressions" value="0" icon={Eye} trend="Awaiting data" color="#3b82f6" />
        <StatCard label="Avg CTR" value="0.0%" icon={MousePointerClick} trend="Awaiting data" color="#f59e0b" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Revenue Per Mille" value="$0.00" icon={BarChart3} color="#8b5cf6" />
        <StatCard label="Conversion Rate" value="0.0%" icon={Zap} color="#ec4899" />
        <StatCard label="Active Brands" value={String(brands?.length || 0)} icon={BarChart3} color="#14b8a6" />
        <StatCard label="Active Accounts" value="0" icon={BarChart3} color="#f97316" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">Top Opportunities</h3>
          <div className="text-gray-500 text-sm py-8 text-center">
            No opportunities scored yet. Create a brand and configure topic sources to begin discovery.
          </div>
        </div>

        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">Recent Decisions</h3>
          <div className="text-gray-500 text-sm py-8 text-center">
            No decisions recorded yet. Decisions will appear as the system begins operating.
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">Revenue Bottlenecks</h3>
          <div className="text-gray-500 text-sm py-8 text-center">
            Bottleneck analysis requires performance data.
          </div>
        </div>

        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">Scale Recommendations</h3>
          <div className="text-gray-500 text-sm py-8 text-center">
            Scale recommendations will appear after initial performance period.
          </div>
        </div>

        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">System Health</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">API</span>
              <span className="badge-green">Online</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">Database</span>
              <span className={health?.checks?.database ? 'badge-green' : 'badge-red'}>
                {health?.checks?.database ? 'Connected' : 'Connecting...'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">Workers</span>
              <span className="badge-blue">Standby</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
