'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { pipelineApi } from '@/lib/pipeline-api';
import { Library, Filter, Eye } from 'lucide-react';

type Brand = { id: string; name: string };

const STATUS_OPTIONS = ['all', 'draft', 'qa_complete', 'approved', 'published', 'rejected'] as const;
type StatusFilter = (typeof STATUS_OPTIONS)[number];

function errMsg(e: unknown) {
  const ax = e as { response?: { data?: { detail?: string } } };
  return ax.response?.data?.detail ?? (e instanceof Error ? e.message : 'Request failed');
}

function statusBadge(status: string) {
  const s = status.toLowerCase();
  if (s === 'published' || s === 'approved') return 'badge-green';
  if (s === 'rejected') return 'badge-red';
  if (s === 'qa_complete') return 'badge-blue';
  return 'badge-yellow';
}

export default function ContentLibraryPage() {
  const [brandId, setBrandId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(brands[0].id);
  }, [brands, brandId]);

  const {
    data: items,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ['pipeline-content-library', brandId, statusFilter],
    queryFn: () =>
      pipelineApi.contentLibrary(brandId!, statusFilter === 'all' ? undefined : statusFilter).then((r) => r.data),
    enabled: !!brandId,
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="flex items-start gap-3">
          <Library className="text-brand-400 shrink-0 mt-1" size={28} />
          <div>
            <h1 className="text-2xl font-bold text-white">Content Library</h1>
            <p className="text-gray-400 mt-1">Browse and filter all content items for the brand</p>
          </div>
        </div>
        <div className="flex flex-col sm:flex-row gap-3 sm:items-center">
          <div className="flex items-center gap-2 text-gray-400">
            <Filter size={18} />
            <select
              className="input-field min-w-[180px]"
              aria-label="Content status filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
            >
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {s === 'all' ? 'All statuses' : s.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </div>
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
            <div className="card border-red-900/50 text-red-300">Failed to load library: {errMsg(error)}</div>
          ) : isLoading ? (
            <div className="text-gray-500 text-center py-12">Loading content...</div>
          ) : !items?.length ? (
            <div className="card text-center py-12 flex flex-col items-center gap-2">
              <Eye className="text-gray-600" size={40} />
              <p className="text-gray-400">No items match this filter.</p>
            </div>
          ) : (
            <div className="card overflow-x-auto p-0">
              <table className="w-full text-sm">
                <thead className="text-gray-400 border-b border-gray-800 bg-gray-950/50">
                  <tr>
                    <th className="p-4 text-left font-medium">Title</th>
                    <th className="p-4 text-left font-medium">Type</th>
                    <th className="p-4 text-left font-medium">Platform</th>
                    <th className="p-4 text-left font-medium">Status</th>
                    <th className="p-4 text-left font-medium">Cost</th>
                    <th className="p-4 text-left font-medium">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item: any) => (
                    <tr key={item.id} className="border-b border-gray-800/80 hover:bg-gray-900/40">
                      <td className="p-4 text-white font-medium max-w-xs truncate" title={item.title}>
                        {item.title}
                      </td>
                      <td className="p-4 text-gray-300">{String(item.content_type).replace(/_/g, ' ')}</td>
                      <td className="p-4 text-gray-300">{item.platform ?? '—'}</td>
                      <td className="p-4">
                        <span className={statusBadge(item.status)}>{item.status.replace(/_/g, ' ')}</span>
                      </td>
                      <td className="p-4 text-gray-300">
                        {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(
                          Number(item.total_cost) || 0
                        )}
                      </td>
                      <td className="p-4 text-gray-500 whitespace-nowrap">
                        {new Date(item.created_at).toLocaleString()}
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
