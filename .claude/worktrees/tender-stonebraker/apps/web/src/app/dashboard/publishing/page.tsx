'use client';

import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { pipelineApi } from '@/lib/pipeline-api';
import { FileText, BarChart3, Video, ChevronDown, ChevronRight } from 'lucide-react';

type Brand = { id: string; name: string };

function errMsg(e: unknown) {
  const ax = e as { response?: { data?: { detail?: string } } };
  return ax.response?.data?.detail ?? (e instanceof Error ? e.message : 'Request failed');
}

export default function ScriptReviewPage() {
  const queryClient = useQueryClient();
  const [brandId, setBrandId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [scores, setScores] = useState<Record<string, unknown>>({});

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(brands[0].id);
  }, [brands, brandId]);

  const {
    data: scripts,
    isLoading: scriptsLoading,
    isError: scriptsError,
    error: scriptsErr,
  } = useQuery({
    queryKey: ['pipeline-scripts', brandId],
    queryFn: () => pipelineApi.listScripts(brandId!).then((r) => r.data),
    enabled: !!brandId,
  });

  const scoreMutation = useMutation({
    mutationFn: (id: string) => pipelineApi.scoreScript(id).then((r) => r.data),
    onSuccess: (data, id) => {
      setScores((s) => ({ ...s, [id]: data }));
    },
  });

  const mediaMutation = useMutation({
    mutationFn: (id: string) => pipelineApi.generateMedia(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline-scripts', brandId] });
      queryClient.invalidateQueries({ queryKey: ['pipeline-media-jobs', brandId] });
    },
  });

  const toggle = (id: string) => setExpanded((e) => ({ ...e, [id]: !e[id] }));

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-start gap-3">
          <FileText className="text-brand-400 shrink-0 mt-1" size={28} />
          <div>
            <h1 className="text-2xl font-bold text-white">Script Review</h1>
            <p className="text-gray-400 mt-1">Score scripts, preview full text, enqueue media</p>
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
          {scriptsError ? (
            <div className="card border-red-900/50 text-red-300">Failed to load scripts: {errMsg(scriptsErr)}</div>
          ) : scriptsLoading ? (
            <div className="text-gray-500 text-center py-12">Loading scripts...</div>
          ) : !scripts?.length ? (
            <div className="card text-center py-12">
              <p className="text-gray-400">No scripts for this brand.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {scripts.map((script: any) => (
                <div key={script.id} className="card-hover">
                  <div className="flex flex-wrap items-start justify-between gap-2 mb-2">
                    <h3 className="text-lg font-semibold text-white">{script.title}</h3>
                    <span className="badge-blue">v{script.version}</span>
                  </div>
                  <div className="flex flex-wrap gap-2 text-sm text-gray-400 mb-3">
                    <span>{script.word_count} words</span>
                    <span className="text-gray-600">·</span>
                    <span>{script.generation_model ?? '—'}</span>
                    <span className="text-gray-600">·</span>
                    <span className="badge-yellow">{script.status}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => toggle(script.id)}
                    className="btn-secondary text-sm inline-flex items-center gap-1 mb-3"
                  >
                    {expanded[script.id] ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    {expanded[script.id] ? 'Hide script' : 'Show full script'}
                  </button>
                  {expanded[script.id] ? (
                    <pre className="text-sm text-gray-300 whitespace-pre-wrap bg-gray-950/80 border border-gray-800 rounded-lg p-4 mb-4 max-h-80 overflow-y-auto">
                      {script.full_script}
                    </pre>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      className="btn-secondary inline-flex items-center gap-2"
                      disabled={scoreMutation.isPending}
                      onClick={() => scoreMutation.mutate(script.id)}
                    >
                      <BarChart3 size={16} />
                      Score
                    </button>
                    <button
                      type="button"
                      className="btn-primary inline-flex items-center gap-2"
                      disabled={mediaMutation.isPending}
                      onClick={() => mediaMutation.mutate(script.id)}
                    >
                      <Video size={16} />
                      Generate Media
                    </button>
                  </div>
                  {scores[script.id] != null ? (
                    <div className="mt-4 p-4 rounded-lg bg-gray-950/50 border border-gray-800 text-sm">
                      <p className="text-emerald-300 font-medium">
                        Publish score: {Number((scores[script.id] as any).publish_score).toFixed(3)}
                      </p>
                      {(scores[script.id] as any).publish_ready != null ? (
                        <p className="text-gray-400 mt-1">
                          Ready: {(scores[script.id] as any).publish_ready ? 'yes' : 'no'} · Confidence:{' '}
                          {(scores[script.id] as any).confidence}
                        </p>
                      ) : null}
                      {(scores[script.id] as any).blocking_issues?.length ? (
                        <ul className="mt-2 text-amber-300 list-disc list-inside">
                          {(scores[script.id] as any).blocking_issues.map((x: string, i: number) => (
                            <li key={i}>{x}</li>
                          ))}
                        </ul>
                      ) : null}
                    </div>
                  ) : null}
                  {scoreMutation.isError && scoreMutation.variables === script.id ? (
                    <p className="text-red-400 text-sm mt-2">{errMsg(scoreMutation.error)}</p>
                  ) : null}
                  {mediaMutation.isError && mediaMutation.variables === script.id ? (
                    <p className="text-red-400 text-sm mt-2">{errMsg(mediaMutation.error)}</p>
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
