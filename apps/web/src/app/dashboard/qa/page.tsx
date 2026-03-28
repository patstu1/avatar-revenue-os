'use client';

import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { pipelineApi } from '@/lib/pipeline-api';
import { Shield, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';

type Brand = { id: string; name: string };

function errMsg(e: unknown) {
  const ax = e as { response?: { data?: { detail?: string } } };
  return ax.response?.data?.detail ?? (e instanceof Error ? e.message : 'Request failed');
}

function asList(val: unknown): string[] {
  if (val == null) return [];
  if (Array.isArray(val)) {
    return val.map((x) => (typeof x === 'string' ? x : JSON.stringify(x)));
  }
  if (typeof val === 'object') {
    return Object.entries(val as Record<string, unknown>).map(([k, v]) => `${k}: ${String(v)}`);
  }
  return [String(val)];
}

function qaStatusBadge(status: string) {
  const s = status.toLowerCase();
  if (s === 'pass') return 'badge-green';
  if (s === 'fail') return 'badge-red';
  if (s === 'review') return 'badge-yellow';
  return 'badge-blue';
}

type QaBundle = { qa: any; similarity: any };

export default function QaCenterPage() {
  const queryClient = useQueryClient();
  const [brandId, setBrandId] = useState<string | null>(null);
  const [bundles, setBundles] = useState<Record<string, QaBundle>>({});

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(brands[0].id);
  }, [brands, brandId]);

  const {
    data: items,
    isLoading: itemsLoading,
    isError: itemsError,
    error: itemsErr,
  } = useQuery({
    queryKey: ['pipeline-content-library', brandId],
    queryFn: () => pipelineApi.contentLibrary(brandId!).then((r) => r.data),
    enabled: !!brandId,
  });

  const runQaMutation = useMutation({
    mutationFn: async (contentId: string) => {
      await pipelineApi.runQA(contentId);
      const r = await pipelineApi.getQA(contentId);
      return { contentId, bundle: { qa: r.data.qa_report, similarity: r.data.similarity_report } as QaBundle };
    },
    onSuccess: ({ contentId, bundle }) => {
      setBundles((b) => ({ ...b, [contentId]: bundle }));
      queryClient.invalidateQueries({ queryKey: ['pipeline-content-library', brandId] });
    },
  });

  function contentStatusBadge(status: string) {
    const s = status.toLowerCase();
    if (s === 'published') return 'badge-green';
    if (s === 'rejected') return 'badge-red';
    if (s === 'qa_complete') return 'badge-blue';
    if (s === 'approved') return 'badge-green';
    return 'badge-yellow';
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-start gap-3">
          <Shield className="text-brand-400 shrink-0 mt-1" size={28} />
          <div>
            <h1 className="text-2xl font-bold text-white">QA Center</h1>
            <p className="text-gray-400 mt-1">Run QA, view scores, similarity, and remediation</p>
          </div>
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
          {itemsError ? (
            <div className="card border-red-900/50 text-red-300 flex items-start gap-2">
              <AlertTriangle className="shrink-0" size={20} />
              <span>Failed to load content: {errMsg(itemsErr)}</span>
            </div>
          ) : itemsLoading ? (
            <div className="text-gray-500 text-center py-12">Loading content library...</div>
          ) : !items?.length ? (
            <div className="card text-center py-12">
              <p className="text-gray-400">No content items for this brand.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {items.map((item: any) => {
                const bundle = bundles[item.id];
                const qa = bundle?.qa;
                const sim = bundle?.similarity;
                return (
                  <div key={item.id} className="card-hover">
                    <div className="flex flex-wrap items-start justify-between gap-2 mb-2">
                      <h3 className="text-lg font-semibold text-white">{item.title}</h3>
                      <span className={contentStatusBadge(item.status)}>{item.status.replace(/_/g, ' ')}</span>
                    </div>
                    <div className="flex flex-wrap gap-2 mb-3">
                      <span className="badge-blue">{String(item.content_type).replace(/_/g, ' ')}</span>
                      {item.platform ? <span className="badge-green">{item.platform}</span> : null}
                      <span className="text-gray-500 text-sm">
                        Cost:{' '}
                        {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(
                          Number(item.total_cost) || 0
                        )}
                      </span>
                    </div>
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={runQaMutation.isPending}
                      onClick={() => runQaMutation.mutate(item.id)}
                    >
                      {runQaMutation.isPending && runQaMutation.variables === item.id ? 'Running QA...' : 'Run QA'}
                    </button>
                    {runQaMutation.isError && runQaMutation.variables === item.id ? (
                      <p className="text-red-400 text-sm mt-2">{errMsg(runQaMutation.error)}</p>
                    ) : null}
                    {qa ? (
                      <div className="mt-4 space-y-4 border-t border-gray-800 pt-4">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={qaStatusBadge(qa.qa_status)}>{qa.qa_status}</span>
                          {qa.qa_status?.toLowerCase() === 'pass' ? (
                            <CheckCircle2 className="text-emerald-400" size={18} />
                          ) : qa.qa_status?.toLowerCase() === 'fail' ? (
                            <XCircle className="text-red-400" size={18} />
                          ) : (
                            <AlertTriangle className="text-amber-400" size={18} />
                          )}
                          <span className="text-gray-300 text-sm">
                            Composite: {Number(qa.composite_score).toFixed(3)}
                          </span>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                          <div>
                            <p className="text-gray-500 text-xs uppercase">Originality</p>
                            <p className="text-white">{Number(qa.originality_score).toFixed(3)}</p>
                          </div>
                          <div>
                            <p className="text-gray-500 text-xs uppercase">Compliance</p>
                            <p className="text-white">{Number(qa.compliance_score).toFixed(3)}</p>
                          </div>
                          <div>
                            <p className="text-gray-500 text-xs uppercase">Brand align</p>
                            <p className="text-white">{Number(qa.brand_alignment_score).toFixed(3)}</p>
                          </div>
                          <div>
                            <p className="text-gray-500 text-xs uppercase">Technical</p>
                            <p className="text-white">{Number(qa.technical_quality_score).toFixed(3)}</p>
                          </div>
                          <div>
                            <p className="text-gray-500 text-xs uppercase">Audio</p>
                            <p className="text-white">{Number(qa.audio_quality_score).toFixed(3)}</p>
                          </div>
                          <div>
                            <p className="text-gray-500 text-xs uppercase">Visual</p>
                            <p className="text-white">{Number(qa.visual_quality_score).toFixed(3)}</p>
                          </div>
                        </div>
                        {qa.explanation ? <p className="text-sm text-gray-400">{qa.explanation}</p> : null}
                        <div className="grid md:grid-cols-2 gap-4">
                          <div>
                            <p className="text-xs font-medium text-gray-500 uppercase mb-2">Issues</p>
                            <ul className="text-sm text-amber-200/90 space-y-1 list-disc list-inside">
                              {asList(qa.issues_found).length ? (
                                asList(qa.issues_found).map((line, i) => <li key={i}>{line}</li>)
                              ) : (
                                <li className="text-gray-500 list-none -ml-4">None listed</li>
                              )}
                            </ul>
                          </div>
                          <div>
                            <p className="text-xs font-medium text-gray-500 uppercase mb-2">Recommendations</p>
                            <ul className="text-sm text-sky-200/90 space-y-1 list-disc list-inside">
                              {asList(qa.recommendations).length ? (
                                asList(qa.recommendations).map((line, i) => <li key={i}>{line}</li>)
                              ) : (
                                <li className="text-gray-500 list-none -ml-4">None listed</li>
                              )}
                            </ul>
                          </div>
                        </div>
                        <div className="rounded-lg border border-gray-800 bg-gray-950/50 p-4">
                          <p className="text-xs font-medium text-gray-500 uppercase mb-2">Similarity check</p>
                          {sim ? (
                            <div className="text-sm space-y-1 text-gray-300">
                              <p>
                                Compared against: {sim.compared_against_count} · Max similarity:{' '}
                                {Number(sim.max_similarity_score).toFixed(3)} · Avg:{' '}
                                {Number(sim.avg_similarity_score).toFixed(3)}
                              </p>
                              <p>
                                Threshold: {Number(sim.threshold_used).toFixed(2)} · Too similar:{' '}
                                <span className={sim.is_too_similar ? 'text-red-300' : 'text-emerald-300'}>
                                  {sim.is_too_similar ? 'yes' : 'no'}
                                </span>
                              </p>
                              {sim.explanation ? <p className="text-gray-400">{sim.explanation}</p> : null}
                            </div>
                          ) : (
                            <p className="text-sm text-gray-500">No similarity report on file for this item.</p>
                          )}
                        </div>
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
