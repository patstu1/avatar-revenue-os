'use client';

import { useQuery } from '@tanstack/react-query';
import { healthApi } from '@/lib/api';
import { orchestrationApi } from '@/lib/orchestration-api';
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Cpu,
  Gauge,
  Loader2,
  RefreshCw,
  Server,
  Shield,
  XCircle,
  Zap,
} from 'lucide-react';

type OrchState = {
  jobs_by_status: Record<string, number>;
  jobs_by_queue: Record<string, number>;
  running_jobs: Array<{ id: string; job_name: string; queue: string; started_at?: string; retries: number }>;
  recent_failures: Array<{ id: string; job_name: string; queue: string; error_message: string; retries: number; max_retries?: number; completed_at?: string }>;
  throughput: {
    completed_1h: number;
    completed_24h: number;
    failed_24h: number;
    success_rate: number;
    avg_duration_seconds?: number;
    retry_count_24h: number;
  };
};

type ProviderHealth = {
  providers: Array<{ provider_key: string; display_name: string; category: string; status: string; is_primary: boolean }>;
  blockers: Array<{ id: string; provider_key?: string; blocker_type: string; severity: string; detail?: string }>;
  counts: { healthy: number; degraded: number; blocked: number; total: number };
};

function timeAgo(dateStr?: string): string {
  if (!dateStr) return '—';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

const statusColors: Record<string, string> = {
  pending: 'text-yellow-400 bg-yellow-500/10',
  queued: 'text-blue-400 bg-blue-500/10',
  running: 'text-cyan-400 bg-cyan-500/10',
  completed: 'text-emerald-400 bg-emerald-500/10',
  failed: 'text-red-400 bg-red-500/10',
  retrying: 'text-orange-400 bg-orange-500/10',
  cancelled: 'text-gray-400 bg-gray-500/10',
};

const providerStatusColors: Record<string, { text: string; bg: string; icon: typeof CheckCircle2 }> = {
  healthy: { text: 'text-emerald-400', bg: 'bg-emerald-500/10', icon: CheckCircle2 },
  degraded: { text: 'text-yellow-400', bg: 'bg-yellow-500/10', icon: AlertTriangle },
  blocked: { text: 'text-red-400', bg: 'bg-red-500/10', icon: XCircle },
};

export default function OrchestrationPage() {
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => healthApi.readyz().then((r) => r.data),
    refetchInterval: 15_000,
  });

  const { data: orch, isLoading: orchLoading } = useQuery({
    queryKey: ['orchestration-state'],
    queryFn: () => orchestrationApi.state().then((r) => r.data as OrchState),
    refetchInterval: 10_000,
  });

  const { data: providers } = useQuery({
    queryKey: ['orchestration-providers'],
    queryFn: () => orchestrationApi.providers().then((r) => r.data as ProviderHealth),
    refetchInterval: 30_000,
  });

  const tp = orch?.throughput;

  return (
    <div className="space-y-6 max-w-[1600px]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Orchestration</h1>
          <p className="text-sm text-gray-500 mt-0.5">Jobs, workers, providers, and execution health</p>
        </div>
        <div className="flex items-center gap-2">
          {health?.status === 'ready' ? (
            <span className="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 rounded-full px-2.5 py-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Online
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-xs text-yellow-400 bg-yellow-500/10 border border-yellow-500/30 rounded-full px-2.5 py-1">
              <Loader2 size={10} className="animate-spin" /> Connecting
            </span>
          )}
        </div>
      </div>

      {orchLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="animate-spin text-gray-600" size={32} />
        </div>
      ) : (
        <>
          {/* Throughput Metrics */}
          {tp && (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              <MetricCard label="Completed (1h)" value={tp.completed_1h} icon={Zap} color="#14b8a6" />
              <MetricCard label="Completed (24h)" value={tp.completed_24h} icon={CheckCircle2} color="#22c55e" />
              <MetricCard label="Failed (24h)" value={tp.failed_24h} icon={XCircle} color={tp.failed_24h > 0 ? '#ef4444' : '#22c55e'} />
              <MetricCard label="Success Rate" value={`${tp.success_rate}%`} icon={Gauge} color={tp.success_rate >= 95 ? '#22c55e' : tp.success_rate >= 80 ? '#f59e0b' : '#ef4444'} />
              <MetricCard label="Avg Duration" value={tp.avg_duration_seconds ? `${tp.avg_duration_seconds}s` : '—'} icon={Clock} color="#8b5cf6" />
              <MetricCard label="Retries (24h)" value={tp.retry_count_24h} icon={RefreshCw} color={tp.retry_count_24h > 0 ? '#f59e0b' : '#6b7280'} />
            </div>
          )}

          {/* Job Status + Queue Distribution */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Job Status Distribution */}
            <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                <Activity size={16} className="text-cyan-400" />
                Job Status
              </h3>
              <div className="space-y-2">
                {Object.entries(orch?.jobs_by_status || {}).map(([status, count]) => (
                  <div key={status} className="flex items-center justify-between">
                    <span className={`text-xs font-medium rounded-full px-2.5 py-0.5 ${statusColors[status] || 'text-gray-400 bg-gray-500/10'}`}>
                      {status}
                    </span>
                    <span className="text-sm font-bold text-white">{count}</span>
                  </div>
                ))}
                {Object.keys(orch?.jobs_by_status || {}).length === 0 && (
                  <p className="text-sm text-gray-600 text-center py-4">No jobs recorded yet</p>
                )}
              </div>
            </div>

            {/* Queue Distribution */}
            <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                <Cpu size={16} className="text-purple-400" />
                Queue Activity (24h)
              </h3>
              <div className="space-y-2">
                {Object.entries(orch?.jobs_by_queue || {}).slice(0, 10).map(([queue, count]) => (
                  <div key={queue} className="flex items-center justify-between">
                    <span className="text-xs text-gray-400 font-mono">{queue}</span>
                    <span className="text-sm font-bold text-white">{count}</span>
                  </div>
                ))}
                {Object.keys(orch?.jobs_by_queue || {}).length === 0 && (
                  <p className="text-sm text-gray-600 text-center py-4">No queue activity in last 24h</p>
                )}
              </div>
            </div>
          </div>

          {/* Running Jobs */}
          {(orch?.running_jobs?.length ?? 0) > 0 && (
            <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-cyan-400 mb-4 flex items-center gap-2">
                <Loader2 size={16} className="animate-spin" />
                Running Jobs ({orch!.running_jobs.length})
              </h3>
              <div className="space-y-2">
                {orch!.running_jobs.map((job) => (
                  <div key={job.id} className="flex items-center justify-between py-2 px-3 bg-gray-800/30 rounded-lg">
                    <div>
                      <p className="text-sm text-white font-medium">{job.job_name}</p>
                      <p className="text-[10px] text-gray-500">{job.queue} · started {timeAgo(job.started_at)}</p>
                    </div>
                    {job.retries > 0 && (
                      <span className="text-[10px] text-orange-400">retry #{job.retries}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recent Failures */}
          {(orch?.recent_failures?.length ?? 0) > 0 && (
            <div className="bg-gray-900/80 border border-red-500/20 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-red-400 mb-4 flex items-center gap-2">
                <AlertOctagon size={16} />
                Recent Failures ({orch!.recent_failures.length})
              </h3>
              <div className="space-y-2">
                {orch!.recent_failures.map((job) => (
                  <div key={job.id} className="py-2.5 px-3 bg-red-500/5 border border-red-500/10 rounded-lg">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-white font-medium">{job.job_name}</p>
                        {job.error_message && (
                          <p className="text-xs text-red-300/70 mt-1 line-clamp-2">{job.error_message}</p>
                        )}
                      </div>
                      <div className="text-right shrink-0">
                        <p className="text-[10px] text-gray-500">{timeAgo(job.completed_at)}</p>
                        <p className="text-[10px] text-gray-600">{job.queue} · {job.retries}/{job.max_retries} retries</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Provider Health */}
          {providers && (
            <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                <Server size={16} className="text-blue-400" />
                Provider Health
                <span className="ml-auto text-[10px] text-gray-500">
                  {providers.counts.healthy} healthy · {providers.counts.degraded} degraded · {providers.counts.blocked} blocked
                </span>
              </h3>

              {/* Blockers */}
              {providers.blockers.length > 0 && (
                <div className="mb-4 space-y-2">
                  {providers.blockers.map((b) => (
                    <div key={b.id} className="flex items-start gap-2 py-2 px-3 bg-red-500/5 border border-red-500/10 rounded-lg">
                      <AlertTriangle size={14} className="text-red-400 mt-0.5 shrink-0" />
                      <div>
                        <p className="text-xs text-red-300 font-medium">{b.provider_key}: {b.blocker_type}</p>
                        {b.detail && <p className="text-[10px] text-gray-500 mt-0.5">{b.detail}</p>}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Provider Grid */}
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                {providers.providers.map((p) => {
                  const cfg = providerStatusColors[p.status] || providerStatusColors.healthy;
                  const Icon = cfg.icon;
                  return (
                    <div key={p.provider_key} className={`flex items-center gap-2 py-2 px-3 rounded-lg ${cfg.bg}`}>
                      <Icon size={14} className={cfg.text} />
                      <div className="min-w-0">
                        <p className="text-xs text-white font-medium truncate">{p.display_name || p.provider_key}</p>
                        <p className="text-[10px] text-gray-500">{p.category}{p.is_primary ? ' · primary' : ''}</p>
                      </div>
                    </div>
                  );
                })}
                {providers.providers.length === 0 && (
                  <p className="col-span-full text-sm text-gray-600 text-center py-4">
                    No providers registered. Run a provider audit to discover available providers.
                  </p>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function MetricCard({ label, value, icon: Icon, color }: { label: string; value: string | number; icon: any; color: string }) {
  return (
    <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl px-4 py-3">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wider">{label}</p>
          <p className="text-xl font-bold mt-0.5" style={{ color }}>{value}</p>
        </div>
        <Icon size={16} style={{ color, opacity: 0.5 }} />
      </div>
    </div>
  );
}
