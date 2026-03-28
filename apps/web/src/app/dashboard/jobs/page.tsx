'use client';

import { useQuery } from '@tanstack/react-query';
import { jobsApi } from '@/lib/api';
import { Shield, Clock, CheckCircle2, XCircle, RefreshCw } from 'lucide-react';

const STATUS_BADGES: Record<string, string> = {
  pending: 'badge-yellow',
  queued: 'badge-blue',
  running: 'badge-blue',
  completed: 'badge-green',
  failed: 'badge-red',
  cancelled: 'badge-red',
  retrying: 'badge-yellow',
};

export default function JobsPage() {
  const { data: jobs, isLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => jobsApi.list().then((r) => r.data),
    refetchInterval: 10_000,
  });

  const { data: auditLogs } = useQuery({
    queryKey: ['audit-logs'],
    queryFn: () => jobsApi.auditLogs().then((r) => r.data),
  });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Jobs & Workers</h1>
        <p className="text-gray-400 mt-1">Monitor system jobs, worker health, and audit trail</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Shield size={18} /> System Jobs
          </h3>
          {isLoading ? (
            <p className="text-gray-500 text-sm">Loading...</p>
          ) : !jobs?.items?.length ? (
            <p className="text-gray-500 text-sm py-8 text-center">No jobs recorded yet.</p>
          ) : (
            <div className="space-y-2">
              {jobs.items.map((job: any) => (
                <div key={job.id} className="flex items-center justify-between py-2 px-3 bg-gray-800/50 rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-gray-200">{job.job_name}</p>
                    <p className="text-xs text-gray-500">{job.job_type} &middot; {job.queue}</p>
                  </div>
                  <span className={STATUS_BADGES[job.status] || 'badge-blue'}>{job.status}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Clock size={18} /> Audit Log
          </h3>
          {!auditLogs?.items?.length ? (
            <p className="text-gray-500 text-sm py-8 text-center">No audit entries yet.</p>
          ) : (
            <div className="space-y-2">
              {auditLogs.items.slice(0, 20).map((log: any) => (
                <div key={log.id} className="py-2 px-3 bg-gray-800/50 rounded-lg">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-gray-200">{log.action}</p>
                    <span className="text-xs text-gray-500">{log.actor_type}</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {new Date(log.created_at).toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
