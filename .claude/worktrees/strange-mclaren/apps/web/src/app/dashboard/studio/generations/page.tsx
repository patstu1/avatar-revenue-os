'use client';

import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { cinemaStudioApi } from '@/lib/cinema-studio-api';
import { Film, Loader2, CheckCircle2, AlertCircle, Clock, Play } from 'lucide-react';
import Link from 'next/link';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

const STATUS_OPTIONS = ['all', 'pending', 'processing', 'completed', 'failed'] as const;

const STATUS_BADGE: Record<string, string> = {
  pending: 'bg-blue-900/60 text-blue-300',
  processing: 'bg-amber-900/60 text-amber-300',
  completed: 'bg-emerald-900/60 text-emerald-300',
  failed: 'bg-red-900/60 text-red-300',
};

const STATUS_ICON: Record<string, React.ReactNode> = {
  pending: <Clock size={14} />,
  processing: <Loader2 size={14} className="animate-spin" />,
  completed: <CheckCircle2 size={14} />,
  failed: <AlertCircle size={14} />,
};

export default function GenerationQueuePage() {
  const queryClient = useQueryClient();
  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) {
      setSelectedBrandId(String(brands[0].id));
    }
  }, [brands, selectedBrandId]);

  const filterParam = statusFilter === 'all' ? undefined : statusFilter;

  const { data: generations, isLoading, isError, error } = useQuery({
    queryKey: ['studio-generations', selectedBrandId, statusFilter],
    queryFn: () =>
      cinemaStudioApi
        .listGenerations(selectedBrandId, undefined, filterParam)
        .then((r) => r.data),
    enabled: Boolean(selectedBrandId),
  });

  const list = (generations ?? []) as any[];

  const hasActive = list.some((g: any) => g.status === 'pending' || g.status === 'processing');

  useEffect(() => {
    if (!hasActive || !selectedBrandId) return;
    const interval = setInterval(() => {
      queryClient.invalidateQueries({ queryKey: ['studio-generations', selectedBrandId, statusFilter] });
    }, 2000);
    return () => clearInterval(interval);
  }, [hasActive, selectedBrandId, statusFilter, queryClient]);

  const counts = {
    total: list.length,
    pending: list.filter((g: any) => g.status === 'pending').length,
    processing: list.filter((g: any) => g.status === 'processing').length,
    completed: list.filter((g: any) => g.status === 'completed').length,
    failed: list.filter((g: any) => g.status === 'failed').length,
  };

  if (brandsLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-96 bg-gray-800 rounded animate-pulse" />
        <div className="card py-12 text-center text-gray-500">Loading…</div>
      </div>
    );
  }

  if (brandsError) {
    return <div className="card border-red-900/50 text-red-300 py-8 text-center">{errMessage(brandsErr)}</div>;
  }

  if (!brands?.length) {
    return <div className="card text-center py-12 text-gray-500">Create a brand first.</div>;
  }

  return (
    <div className="space-y-8 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Film className="text-brand-500" size={28} aria-hidden />
          Generation Queue
        </h1>
        <p className="text-gray-400 mt-1 max-w-3xl">
          Monitor all video generations across your cinema projects.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-4">
        <div className="card max-w-xs flex-1">
          <label className="stat-label block mb-2">Brand</label>
          <select
            className="input-field w-full"
            value={selectedBrandId}
            onChange={(e) => setSelectedBrandId(e.target.value)}
            aria-label="Select brand"
          >
            {brands.map((b) => (
              <option key={b.id} value={String(b.id)}>{b.name}</option>
            ))}
          </select>
        </div>

        <div className="card max-w-xs flex-1">
          <label className="stat-label block mb-2">Status Filter</label>
          <select
            className="input-field w-full"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            aria-label="Filter by status"
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>{s === 'all' ? 'All Statuses' : s}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
        <SummaryCard label="Total" count={counts.total} color="text-white" />
        <SummaryCard label="Pending" count={counts.pending} color="text-blue-400" />
        <SummaryCard label="Processing" count={counts.processing} color="text-amber-400" />
        <SummaryCard label="Completed" count={counts.completed} color="text-emerald-400" />
        <SummaryCard label="Failed" count={counts.failed} color="text-red-400" />
      </div>

      {isLoading && <div className="card py-12 text-center text-gray-500">Loading generations…</div>}
      {isError && <div className="card border-red-900/50 text-red-300 py-8 text-center">{errMessage(error)}</div>}

      {!isLoading && !isError && list.length === 0 && (
        <div className="card text-center py-12 text-gray-500">No generations yet.</div>
      )}

      <div className="space-y-4">
        {list.map((g: any) => (
          <div key={g.id} className="card">
            <div className="flex flex-col sm:flex-row sm:items-center gap-4">
              {g.status === 'completed' && g.video_url ? (
                <div className="relative w-full sm:w-40 h-24 rounded-lg overflow-hidden bg-gray-800 shrink-0 flex items-center justify-center">
                  <video
                    src={g.video_url}
                    className="w-full h-full object-cover"
                    muted
                    preload="metadata"
                  />
                  <Play size={24} className="absolute text-white/80" />
                </div>
              ) : (
                <div className="w-full sm:w-40 h-24 rounded-lg bg-gray-800 shrink-0 flex items-center justify-center">
                  <Film size={28} className="text-gray-600" />
                </div>
              )}

              <div className="flex-1 min-w-0 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_BADGE[g.status] ?? 'bg-gray-700 text-gray-300'}`}>
                    {STATUS_ICON[g.status]} {g.status}
                  </span>

                  {g.scene_id && (
                    <Link
                      href={`/dashboard/studio/scenes/${g.scene_id}`}
                      className="text-brand-400 hover:underline text-xs"
                    >
                      Scene {String(g.scene_id).slice(0, 8)}…
                    </Link>
                  )}
                </div>

                {g.status === 'processing' && g.progress != null && (
                  <div className="w-full bg-gray-800 rounded h-2 overflow-hidden">
                    <div
                      className="h-2 rounded bg-amber-500 transition-all duration-300"
                      style={{ width: `${Math.min(100, Math.max(0, Number(g.progress)))}%` }}
                    />
                  </div>
                )}

                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-400">
                  {g.model && <span>Model: <span className="text-gray-300">{g.model}</span></span>}
                  {g.steps != null && <span>Steps: <span className="text-gray-300">{g.steps}</span></span>}
                  {g.guidance != null && <span>Guidance: <span className="text-gray-300">{g.guidance}</span></span>}
                  {g.duration_seconds != null && <span>Duration: <span className="text-gray-300">{g.duration_seconds}s</span></span>}
                  {g.created_at && (
                    <span>Created: <span className="text-gray-300">{new Date(g.created_at).toLocaleString()}</span></span>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function SummaryCard({ label, count, color }: { label: string; count: number; color: string }) {
  return (
    <div className="card text-center">
      <span className={`text-2xl font-bold ${color}`}>{count}</span>
      <span className="stat-label block mt-1">{label}</span>
    </div>
  );
}
