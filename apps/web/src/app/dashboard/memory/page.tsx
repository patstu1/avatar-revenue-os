'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { pipelineApi } from '@/lib/pipeline-api';
import { Video, RefreshCw, AlertTriangle } from 'lucide-react';

type Brand = { id: string; name: string };

function errMsg(e: unknown) {
  const ax = e as { response?: { data?: { detail?: string } } };
  return ax.response?.data?.detail ?? (e instanceof Error ? e.message : 'Request failed');
}

function jobStatusBadge(status: string) {
  const s = status.toLowerCase();
  if (s === 'pending' || s === 'queued') return 'badge-yellow';
  if (s === 'running' || s === 'retrying') return 'badge-blue';
  if (s === 'completed') return 'badge-green';
  if (s === 'failed' || s === 'cancelled') return 'badge-red';
  return 'badge-blue';
}

export default function MediaJobQueuePage() {
  const [brandId, setBrandId] = useState<string | null>(null);

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(brands[0].id);
  }, [brands, brandId]);

  const { data: jobs, isLoading, isError, error, dataUpdatedAt, refetch, isFetching } = useQuery({
    queryKey: ['pipeline-media-jobs', brandId],
    queryFn: () => pipelineApi.listMediaJobs(brandId!).then((r) => r.data),
    enabled: !!brandId,
    refetchInterval: 10_000,
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-start gap-3">
          <Video className="text-brand-400 shrink-0 mt-1" size={28} />
          <div>
            <h1 className="text-2xl font-bold text-white">Media Job Queue</h1>
            <p className="text-gray-400 mt-1">Provider jobs, retries, and costs (refreshes every 10s)</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="btn-secondary inline-flex items-center gap-2"
            onClick={() => refetch()}
            disabled={!brandId || isFetching}
          >
            <RefreshCw size={16} className={isFetching ? 'animate-spin' : ''} />
            Refresh
          </button>
          <select
            className="input-field min-w-[200px]"
            aria-label="Brand"
            value={brandId ?? ''}
            onChange={(e) => setBrandId(e.target.value || null)}
            disabled={!brands?.length}
          >
            {!brands?.length ? <option value="">No brands</option> : null}
            {brands?.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {dataUpdatedAt ? (
        <p className="text-xs text-gray-500">
          Last updated {new Date(dataUpdatedAt).toLocaleTimeString()}
        </p>
      ) : null}

      {brandsError ? (
        <div className="card border-red-900/50 text-red-300">Failed to load brands: {errMsg(brandsErr)}</div>
      ) : brandsLoading ? (
        <div className="text-gray-500 text-center py-12">Loading brands...</div>
      ) : !brands?.length ? (
        <div className="card text-center py-12">
          <p className="text-gray-400">No brands yet.</p>
        </div>
      ) : null}

      {brandId && !brandsLoading && brands?.length ? (
        <>
          {isError ? (
            <div className="card border-red-900/50 text-red-300 flex items-start gap-2">
              <AlertTriangle className="shrink-0 text-red-400" size={20} />
              <span>Failed to load media jobs: {errMsg(error)}</span>
            </div>
          ) : isLoading ? (
            <div className="text-gray-500 text-center py-12">Loading media jobs...</div>
          ) : !jobs?.length ? (
            <div className="card text-center py-12">
              <p className="text-gray-400">No media jobs for this brand.</p>
            </div>
          ) : (
            <div className="card overflow-x-auto p-0">
              <table className="w-full text-sm text-left">
                <thead className="text-gray-400 border-b border-gray-800 bg-gray-950/50">
                  <tr>
                    <th className="p-4 font-medium">Type</th>
                    <th className="p-4 font-medium">Provider</th>
                    <th className="p-4 font-medium">Status</th>
                    <th className="p-4 font-medium">Retries</th>
                    <th className="p-4 font-medium">Cost</th>
                    <th className="p-4 font-medium">Error</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job: any) => (
                    <tr key={job.id} className="border-b border-gray-800/80 hover:bg-gray-900/40">
                      <td className="p-4 text-white">{job.job_type}</td>
                      <td className="p-4 text-gray-300">{job.provider ?? '—'}</td>
                      <td className="p-4">
                        <span className={jobStatusBadge(job.status)}>{job.status}</span>
                      </td>
                      <td className="p-4 text-gray-300">
                        {job.retries}/{job.max_retries}
                      </td>
                      <td className="p-4 text-gray-300">
                        {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(
                          Number(job.cost) || 0
                        )}
                      </td>
                      <td className="p-4 text-red-300 max-w-xs truncate" title={job.error_message ?? ''}>
                        {job.error_message ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
