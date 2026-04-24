'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { pipelineApi } from '@/lib/pipeline-api';
import { CheckCircle2, XCircle, MessageSquare } from 'lucide-react';

type Brand = { id: string; name: string };

function errMsg(e: unknown) {
  const ax = e as { response?: { data?: { detail?: string } } };
  return ax.response?.data?.detail ?? (e instanceof Error ? e.message : 'Request failed');
}

function itemStatusBadge(status: string) {
  const s = status.toLowerCase();
  if (s === 'approved' || s === 'published') return 'badge-green';
  if (s === 'rejected') return 'badge-red';
  if (s === 'revision_requested') return 'badge-yellow';
  if (s === 'qa_complete') return 'badge-blue';
  return 'badge-yellow';
}

export default function ApprovalQueuePage() {
  const queryClient = useQueryClient();
  const [brandId, setBrandId] = useState<string | null>(null);
  const [notesByContent, setNotesByContent] = useState<Record<string, string>>({});

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(brands[0].id);
  }, [brands, brandId]);

  const {
    data: queue,
    isLoading: queueLoading,
    isError: queueError,
    error: queueErr,
  } = useQuery({
    queryKey: ['pipeline-approval-queue', brandId],
    queryFn: () => pipelineApi.approvalQueue(brandId!).then((r) => r.data),
    enabled: !!brandId,
  });

  const {
    data: library,
    isLoading: libLoading,
    isError: libError,
    error: libErr,
  } = useQuery({
    queryKey: ['pipeline-content-library', brandId, 'all'],
    queryFn: () => pipelineApi.contentLibrary(brandId!).then((r) => r.data),
    enabled: !!brandId,
  });

  const contentById = useMemo(() => {
    const m = new Map<string, any>();
    (library ?? []).forEach((c: any) => m.set(c.id, c));
    return m;
  }, [library]);

  const pendingIds = useMemo(() => new Set((queue ?? []).map((a: any) => a.content_item_id)), [queue]);

  const needsReview = useMemo(() => {
    return (library ?? []).filter(
      (c: any) =>
        ['qa_complete', 'draft'].includes(String(c.status).toLowerCase()) && !pendingIds.has(c.id)
    );
  }, [library, pendingIds]);

  const historyItems = useMemo(() => {
    return (library ?? []).filter((c: any) =>
      ['approved', 'rejected', 'revision_requested'].includes(String(c.status).toLowerCase())
    );
  }, [library]);

  const invalidateApproval = () => {
    queryClient.invalidateQueries({ queryKey: ['pipeline-approval-queue', brandId] });
    queryClient.invalidateQueries({ queryKey: ['pipeline-content-library', brandId] });
    queryClient.invalidateQueries({ queryKey: ['pipeline-content-library', brandId, 'all'] });
  };

  const approveMutation = useMutation({
    mutationFn: ({ id, notes }: { id: string; notes: string }) => pipelineApi.approve(id, notes),
    onSuccess: invalidateApproval,
  });
  const rejectMutation = useMutation({
    mutationFn: ({ id, notes }: { id: string; notes: string }) => pipelineApi.reject(id, notes),
    onSuccess: invalidateApproval,
  });
  const requestChangesMutation = useMutation({
    mutationFn: ({ id, notes }: { id: string; notes: string }) => pipelineApi.requestChanges(id, notes),
    onSuccess: invalidateApproval,
  });

  const note = (contentId: string) => notesByContent[contentId] ?? '';

  function ActionRow({ contentId }: { contentId: string }) {
    const busy =
      approveMutation.isPending || rejectMutation.isPending || requestChangesMutation.isPending;
    return (
      <div className="space-y-2 mt-3">
        <input
          className="input-field w-full text-sm"
          placeholder="Notes (optional)"
          value={note(contentId)}
          onChange={(e) => setNotesByContent((n) => ({ ...n, [contentId]: e.target.value }))}
        />
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="btn-primary inline-flex items-center gap-2 bg-emerald-700 hover:bg-emerald-600"
            disabled={busy}
            onClick={() => approveMutation.mutate({ id: contentId, notes: note(contentId) })}
          >
            <CheckCircle2 size={16} /> Approve
          </button>
          <button
            type="button"
            className="btn-secondary inline-flex items-center gap-2 border-red-900 text-red-300 hover:bg-red-950/40"
            disabled={busy}
            onClick={() => rejectMutation.mutate({ id: contentId, notes: note(contentId) })}
          >
            <XCircle size={16} /> Reject
          </button>
          <button
            type="button"
            className="btn-secondary inline-flex items-center gap-2 border-amber-800 text-amber-200"
            disabled={busy}
            onClick={() => requestChangesMutation.mutate({ id: contentId, notes: note(contentId) })}
          >
            <MessageSquare size={16} /> Request Changes
          </button>
        </div>
      </div>
    );
  }

  const listLoading = queueLoading || libLoading;
  const listError = queueError || libError;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-start gap-3">
          <CheckCircle2 className="text-brand-400 shrink-0 mt-1" size={28} />
          <div>
            <h1 className="text-2xl font-bold text-white">Approval Queue</h1>
            <p className="text-gray-400 mt-1">Pending decisions, review items, and recent outcomes</p>
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
          {listError ? (
            <div className="card border-red-900/50 text-red-300">
              Failed to load data: {errMsg(queueErr || libErr)}
            </div>
          ) : listLoading ? (
            <div className="text-gray-500 text-center py-12">Loading approvals...</div>
          ) : (
            <>
              <section className="space-y-3">
                <h2 className="text-lg font-semibold text-white">Pending approvals</h2>
                {!queue?.length ? (
                  <div className="card text-gray-500 text-sm">No items in the approval queue.</div>
                ) : (
                  <div className="space-y-4">
                    {(queue as any[]).map((ap: any) => {
                      const item = contentById.get(ap.content_item_id);
                      return (
                        <div key={ap.id} className="card-hover">
                          <div className="flex flex-wrap justify-between gap-2">
                            <div>
                              <p className="text-white font-medium">
                                {item?.title ?? `Content ${ap.content_item_id}`}
                              </p>
                              <p className="text-xs text-gray-500 mt-1">
                                Approval {ap.id.slice(0, 8)}… · {ap.decision_mode.replace(/_/g, ' ')}
                                {ap.auto_approved ? ' · auto' : ''}
                              </p>
                            </div>
                            <span className="badge-yellow">pending</span>
                          </div>
                          <ActionRow contentId={ap.content_item_id} />
                          {(approveMutation.isError || rejectMutation.isError || requestChangesMutation.isError) &&
                          (approveMutation.variables?.id === ap.content_item_id ||
                            rejectMutation.variables?.id === ap.content_item_id ||
                            requestChangesMutation.variables?.id === ap.content_item_id) ? (
                            <p className="text-red-400 text-sm mt-2">
                              {errMsg(
                                approveMutation.error || rejectMutation.error || requestChangesMutation.error
                              )}
                            </p>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>

              <section className="space-y-3 pt-4 border-t border-gray-800">
                <h2 className="text-lg font-semibold text-white">Content needing approval</h2>
                <p className="text-sm text-gray-500">
                  Items in QA complete or draft without a pending approval record.
                </p>
                {!needsReview.length ? (
                  <div className="card text-gray-500 text-sm">No additional items flagged.</div>
                ) : (
                  <div className="space-y-4">
                    {needsReview.map((item: any) => (
                      <div key={item.id} className="card-hover">
                        <div className="flex flex-wrap justify-between gap-2">
                          <p className="text-white font-medium">{item.title}</p>
                          <span className={itemStatusBadge(item.status)}>{item.status.replace(/_/g, ' ')}</span>
                        </div>
                        <ActionRow contentId={item.id} />
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <section className="space-y-3 pt-4 border-t border-gray-800">
                <h2 className="text-lg font-semibold text-white">Approval history</h2>
                <p className="text-sm text-gray-500">Recent content by approval outcome (from library).</p>
                {!historyItems.length ? (
                  <div className="card text-gray-500 text-sm">No approved, rejected, or revision items in view.</div>
                ) : (
                  <div className="card overflow-x-auto p-0">
                    <table className="w-full text-sm">
                      <thead className="text-gray-400 border-b border-gray-800 bg-gray-950/50">
                        <tr>
                          <th className="p-3 text-left font-medium">Title</th>
                          <th className="p-3 text-left font-medium">Type</th>
                          <th className="p-3 text-left font-medium">Platform</th>
                          <th className="p-3 text-left font-medium">Status</th>
                          <th className="p-3 text-left font-medium">Created</th>
                        </tr>
                      </thead>
                      <tbody>
                        {historyItems.map((item: any) => (
                          <tr key={item.id} className="border-b border-gray-800/80">
                            <td className="p-3 text-white">{item.title}</td>
                            <td className="p-3 text-gray-300">{item.content_type}</td>
                            <td className="p-3 text-gray-300">{item.platform ?? '—'}</td>
                            <td className="p-3">
                              <span className={itemStatusBadge(item.status)}>{item.status.replace(/_/g, ' ')}</span>
                            </td>
                            <td className="p-3 text-gray-500">{new Date(item.created_at).toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            </>
          )}
        </>
      ) : null}
    </div>
  );
}
