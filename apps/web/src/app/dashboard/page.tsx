'use client';

import { useQuery } from '@tanstack/react-query';
import { dashboardApi, healthApi } from '@/lib/api';
import {
  TrendingUp, DollarSign, Eye, MousePointerClick,
  BarChart3, Zap, AlertTriangle, CheckCircle2,
  Megaphone, Palette, ShoppingBag, Users
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
  const { data: overview, isLoading, error } = useQuery({
    queryKey: ['dashboard-overview'],
    queryFn: () => dashboardApi.overview().then((r) => r.data),
    refetchInterval: 30_000,
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
          <p className="text-gray-400 mt-1">Real-time overview across all brands and accounts</p>
        </div>
        <div className="flex items-center gap-2">
          {health?.status === 'ready' ? (
            <span className="badge-green"><CheckCircle2 size={12} className="mr-1" /> System Healthy</span>
          ) : (
            <span className="badge-yellow"><AlertTriangle size={12} className="mr-1" /> Connecting...</span>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className="text-gray-500 text-center py-8">Loading dashboard data...</div>
      ) : error ? (
        <div className="text-red-400 text-center py-8">Failed to load dashboard data. Please try again.</div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Brands" value={String(overview?.total_brands || 0)} icon={Megaphone} color="#14b8a6" />
            <StatCard label="Avatars" value={String(overview?.total_avatars || 0)} icon={Palette} color="#8b5cf6" />
            <StatCard label="Offers" value={String(overview?.total_offers || 0)} icon={ShoppingBag} color="#f59e0b" />
            <StatCard label="Creator Accounts" value={String(overview?.total_creator_accounts || 0)} icon={Users} color="#3b82f6" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Content Items" value={String(overview?.total_content_items || 0)} icon={BarChart3} color="#ec4899" />
            <StatCard label="Publish Jobs" value={String(overview?.total_publish_jobs || 0)} icon={Zap} color="#6366f1" />
            <StatCard label="Audit Entries" value={String(overview?.total_audit_entries || 0)} icon={Eye} color="#10b981" />
            <StatCard
              label="Provider Costs"
              value={`$${(overview?.total_provider_cost || 0).toFixed(2)}`}
              icon={DollarSign}
              color="#f97316"
            />
          </div>

          {/* Accounts by Platform */}
          {overview?.active_accounts_by_platform && Object.keys(overview.active_accounts_by_platform).length > 0 && (
            <div className="card">
              <h3 className="text-lg font-semibold text-white mb-4">Active Accounts by Platform</h3>
              <div className="flex flex-wrap gap-3">
                {Object.entries(overview.active_accounts_by_platform).map(([platform, count]) => (
                  <div key={platform} className="bg-gray-800/50 rounded-lg px-4 py-3 text-center min-w-[100px]">
                    <p className="text-xs text-gray-500 uppercase tracking-wider">{platform}</p>
                    <p className="text-xl font-bold text-white mt-1">{String(count)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Recent Audit Actions */}
            <div className="card">
              <h3 className="text-lg font-semibold text-white mb-4">Recent Actions</h3>
              {!overview?.recent_audit_actions?.length ? (
                <p className="text-gray-500 text-sm py-6 text-center">No recent actions.</p>
              ) : (
                <div className="space-y-2">
                  {overview.recent_audit_actions.map((a: any, i: number) => (
                    <div key={i} className="flex items-center justify-between py-2 px-3 bg-gray-800/50 rounded-lg">
                      <div>
                        <p className="text-sm font-medium text-gray-200">{a.action}</p>
                        {a.entity_type && <p className="text-xs text-gray-500">{a.entity_type}</p>}
                      </div>
                      <span className="text-xs text-gray-500">{a.actor_type}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* System Health */}
            <div className="card">
              <h3 className="text-lg font-semibold text-white mb-4">System Status</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-400">API Server</span>
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
                  <span className="text-sm text-gray-400">System Jobs</span>
                  <span className="badge-blue">{overview?.total_system_jobs || 0} recorded</span>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
