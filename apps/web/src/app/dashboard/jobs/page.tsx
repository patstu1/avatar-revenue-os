'use client';

import { useQuery } from '@tanstack/react-query';
import { jobsApi, healthApi } from '@/lib/api';
import { Shield, Clock, Activity, DollarSign, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';

const STATUS_BADGE: Record<string, string> = {
  pending: 'badge-yellow', queued: 'badge-blue', running: 'badge-blue',
  completed: 'badge-green', failed: 'badge-red', cancelled: 'badge-red', retrying: 'badge-yellow',
};

const HEALTH_BADGE: Record<string, { cls: string; icon: any }> = {
  ready: { cls: 'badge-green', icon: CheckCircle2 },
  degraded: { cls: 'badge-yellow', icon: AlertTriangle },
};

export default function SystemHealthPage() {
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => healthApi.readyz().then((r) => r.data),
    refetchInterval: 15_000,
  });

  const { data: jobs, isLoading: jobsLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => jobsApi.list({ page: 1 }).then((r) => r.data),
    refetchInterval: 10_000,
  });

  const { data: auditLogs, isLoading: auditLoading } = useQuery({
    queryKey: ['audit-logs'],
    queryFn: () => jobsApi.auditLogs(1).then((r) => r.data),
  });

  const { data: costs } = useQuery({
    queryKey: ['provider-costs'],
    queryFn: () => jobsApi.providerCosts().then((r) => r.data),
  });

  const healthInfo = HEALTH_BADGE[health?.status] || HEALTH_BADGE.degraded;

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Admin / System Health</h1>
          <p className="text-gray-400 mt-1">Service health, job monitoring, audit trail, and provider costs</p>
        </div>
        {health && (
          <span className={healthInfo.cls}>
            <healthInfo.icon size={12} className="mr-1" /> System {health.status}
          </span>
        )}
      </div>

      {/* Health Checks */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <p className="stat-label">API</p>
          <p className="text-xl font-bold text-emerald-400 mt-1">Online</p>
        </div>
        <div className="card">
          <p className="stat-label">Database</p>
          <p className={`text-xl font-bold mt-1 ${health?.checks?.database ? 'text-emerald-400' : 'text-red-400'}`}>
            {health?.checks?.database ? 'Connected' : 'Disconnected'}
          </p>
        </div>
        <div className="card">
          <p className="stat-label">Workers</p>
          <p className="text-xl font-bold text-blue-400 mt-1">Standby</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* System Jobs */}
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Activity size={18} /> System Jobs
          </h3>
          {jobsLoading ? (
            <p className="text-gray-500 text-sm">Loading jobs...</p>
          ) : !jobs?.items?.length ? (
            <p className="text-gray-500 text-sm py-6 text-center">No system jobs recorded yet.</p>
          ) : (
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {jobs.items.map((job: any) => (
                <div key={job.id} className="flex items-center justify-between py-2 px-3 bg-gray-800/50 rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-gray-200">{job.job_name}</p>
                    <p className="text-xs text-gray-500">{job.job_type} &middot; {job.queue} &middot; retries: {job.retries}/{job.max_retries}</p>
                    {job.error_message && <p className="text-xs text-red-400 mt-0.5 truncate max-w-xs">{job.error_message}</p>}
                  </div>
                  <span className={STATUS_BADGE[job.status] || 'badge-blue'}>{job.status}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Audit Log */}
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Clock size={18} /> Audit Log
          </h3>
          {auditLoading ? (
            <p className="text-gray-500 text-sm">Loading audit log...</p>
          ) : !auditLogs?.items?.length ? (
            <p className="text-gray-500 text-sm py-6 text-center">No audit entries yet.</p>
          ) : (
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {auditLogs.items.map((log: any) => (
                <div key={log.id} className="py-2 px-3 bg-gray-800/50 rounded-lg">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-gray-200">{log.action}</p>
                    <span className="text-xs text-gray-500">{log.actor_type}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    {log.entity_type && <span className="text-xs text-gray-500">{log.entity_type}</span>}
                    <span className="text-xs text-gray-600">{new Date(log.created_at).toLocaleString()}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Provider Costs */}
      <div className="card">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <DollarSign size={18} /> Provider Usage Costs
        </h3>
        {!costs?.items?.length ? (
          <p className="text-gray-500 text-sm py-6 text-center">No provider costs recorded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b border-gray-800">
                  <th className="pb-2 font-medium">Provider</th>
                  <th className="pb-2 font-medium">Type</th>
                  <th className="pb-2 font-medium">Operation</th>
                  <th className="pb-2 font-medium text-right">Input</th>
                  <th className="pb-2 font-medium text-right">Output</th>
                  <th className="pb-2 font-medium text-right">Cost</th>
                  <th className="pb-2 font-medium">Date</th>
                </tr>
              </thead>
              <tbody>
                {costs.items.map((c: any) => (
                  <tr key={c.id} className="border-b border-gray-800/50">
                    <td className="py-2 text-gray-200 font-medium capitalize">{c.provider}</td>
                    <td className="py-2 text-gray-400">{c.provider_type}</td>
                    <td className="py-2 text-gray-400">{c.operation}</td>
                    <td className="py-2 text-right text-gray-400">{c.input_units.toLocaleString()}</td>
                    <td className="py-2 text-right text-gray-400">{c.output_units.toLocaleString()}</td>
                    <td className="py-2 text-right text-emerald-400 font-medium">${c.cost.toFixed(4)}</td>
                    <td className="py-2 text-gray-500 text-xs">{new Date(c.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
