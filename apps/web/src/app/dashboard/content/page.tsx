'use client';

import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { pipelineApi } from '@/lib/pipeline-api';
import { FileText, Plus, Zap } from 'lucide-react';

type Brand = { id: string; name: string };

function briefStatusBadge(status: string) {
  const s = status.toLowerCase();
  if (s === 'draft') return 'badge-yellow';
  if (s === 'script_generated') return 'badge-blue';
  if (s === 'triggered') return 'badge-green';
  return 'badge-blue';
}

export default function ContentBriefsPage() {
  const queryClient = useQueryClient();
  const [brandId, setBrandId] = useState<string | null>(null);

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) {
      setBrandId(brands[0].id);
    }
  }, [brands, brandId]);

  const {
    data: briefs,
    isLoading: briefsLoading,
    isError: briefsError,
    error: briefsErr,
  } = useQuery({
    queryKey: ['pipeline-briefs', brandId],
    queryFn: () => pipelineApi.listBriefs(brandId!).then((r) => r.data),
    enabled: !!brandId,
  });

  const generateMutation = useMutation({
    mutationFn: (briefId: string) => pipelineApi.generateScript(briefId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline-briefs', brandId] });
      queryClient.invalidateQueries({ queryKey: ['pipeline-scripts', brandId] });
    },
  });

  const errMsg = (e: unknown) => {
    const ax = e as { response?: { data?: { detail?: string } } };
    return ax.response?.data?.detail ?? (e instanceof Error ? e.message : 'Request failed');
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-start gap-3">
          <FileText className="text-brand-400 shrink-0 mt-1" size={28} />
          <div>
            <h1 className="text-2xl font-bold text-white">Content Briefs</h1>
            <p className="text-gray-400 mt-1">Briefs, hooks, and script generation</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Plus className="text-gray-500" size={18} aria-hidden />
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
          <p className="text-gray-400">No brands yet. Create a brand first.</p>
        </div>
      ) : null}

      {brandId && !brandsLoading && brands?.length ? (
        <>
          {briefsError ? (
            <div className="card border-red-900/50 text-red-300">Failed to load briefs: {errMsg(briefsErr)}</div>
          ) : briefsLoading ? (
            <div className="text-gray-500 text-center py-12">Loading briefs...</div>
          ) : !briefs?.length ? (
            <div className="card text-center py-12">
              <p className="text-gray-400">No briefs for this brand.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {briefs.map((brief: any) => (
                <div key={brief.id} className="card-hover">
                  <div className="flex flex-wrap items-start justify-between gap-2 mb-3">
                    <h3 className="text-lg font-semibold text-white pr-2">{brief.title}</h3>
                    <span className={briefStatusBadge(brief.status)}>{brief.status.replace(/_/g, ' ')}</span>
                  </div>
                  <div className="flex flex-wrap gap-2 mb-3">
                    <span className="badge-blue">{String(brief.content_type).replace(/_/g, ' ')}</span>
                    {brief.target_platform ? (
                      <span className="badge-green">{brief.target_platform}</span>
                    ) : (
                      <span className="badge-yellow">no platform</span>
                    )}
                  </div>
                  {brief.hook ? <p className="text-sm text-gray-300 mb-2 line-clamp-3">{brief.hook}</p> : null}
                  {brief.angle ? <p className="text-sm text-gray-500 mb-4">Angle: {brief.angle}</p> : null}
                  <button
                    type="button"
                    className="btn-primary inline-flex items-center gap-2"
                    disabled={generateMutation.isPending}
                    onClick={() => generateMutation.mutate(brief.id)}
                  >
                    <Zap size={16} />
                    {generateMutation.isPending ? 'Generating...' : 'Generate Script'}
                  </button>
                  {generateMutation.isError ? (
                    <p className="text-red-400 text-sm mt-2">{errMsg(generateMutation.error)}</p>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
