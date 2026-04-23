'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { accountsApi, brandsApi } from '@/lib/api';
import { pipelineApi } from '@/lib/pipeline-api';
import { Calendar, Send, Clock } from 'lucide-react';

type Brand = { id: string; name: string };

type CreatorAccount = {
  id: string;
  platform: string;
  platform_username: string;
};

function errMsg(e: unknown) {
  const ax = e as { response?: { data?: { detail?: string } } };
  return ax.response?.data?.detail ?? (e instanceof Error ? e.message : 'Request failed');
}

function publishJobBadge(status: string) {
  const s = status.toLowerCase();
  if (s === 'completed') return 'badge-green';
  if (s === 'failed' || s === 'cancelled') return 'badge-red';
  if (s === 'running' || s === 'pending' || s === 'queued') return 'badge-blue';
  return 'badge-yellow';
}

export default function PublishingCalendarPage() {
  const queryClient = useQueryClient();
  const [brandId, setBrandId] = useState<string | null>(null);
  const [accountByItem, setAccountByItem] = useState<Record<string, string>>({});
  const [scheduledAtByItem, setScheduledAtByItem] = useState<Record<string, string>>({});

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(brands[0].id);
  }, [brands, brandId]);

  const { data: accounts, isLoading: accountsLoading } = useQuery({
    queryKey: ['accounts', brandId],
    queryFn: () => accountsApi.list(brandId!).then((r) => r.data as CreatorAccount[]),
    enabled: !!brandId,
  });

  const {
    data: approvedItems,
    isLoading: itemsLoading,
    isError: itemsError,
    error: itemsErr,
  } = useQuery({
    queryKey: ['pipeline-content-library', brandId, 'approved'],
    queryFn: () => pipelineApi.contentLibrary(brandId!, 'approved').then((r) => r.data),
    enabled: !!brandId,
  });

  const items = approvedItems ?? [];

  const publishQueries = useQueries({
    queries: items.map((item: { id: string }) => ({
      queryKey: ['pipeline-publish-status', item.id],
      queryFn: () => pipelineApi.publishStatus(item.id).then((r) => r.data),
      enabled: !!brandId && items.length > 0,
    })),
  });

  const accountOptions = accounts ?? [];

  const scheduleMutation = useMutation({
    mutationFn: ({
      contentId,
      creator_account_id,
      platform,
      scheduled_at,
    }: {
      contentId: string;
      creator_account_id: string;
      platform: string;
      scheduled_at: string;
    }) =>
      pipelineApi.schedule(contentId, {
        creator_account_id,
        platform,
        scheduled_at,
      }),
    onSuccess: (_d, v) => {
      queryClient.invalidateQueries({ queryKey: ['pipeline-publish-status', v.contentId] });
      queryClient.invalidateQueries({ queryKey: ['pipeline-content-library', brandId] });
    },
  });

  const publishNowMutation = useMutation({
    mutationFn: ({
      contentId,
      creator_account_id,
      platform,
    }: {
      contentId: string;
      creator_account_id: string;
      platform: string;
    }) => pipelineApi.publishNow(contentId, { creator_account_id, platform }),
    onSuccess: (_d, v) => {
      queryClient.invalidateQueries({ queryKey: ['pipeline-publish-status', v.contentId] });
      queryClient.invalidateQueries({ queryKey: ['pipeline-content-library', brandId] });
    },
  });

  const accountById = useMemo(() => {
    const m = new Map<string, CreatorAccount>();
    accountOptions.forEach((a) => m.set(a.id, a));
    return m;
  }, [accountOptions]);

  function resolveAccount(contentId: string) {
    const accId = accountByItem[contentId];
    if (!accId) return null;
    return accountById.get(accId) ?? null;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-start gap-3">
          <Calendar className="text-brand-400 shrink-0 mt-1" size={28} />
          <div>
            <h1 className="text-2xl font-bold text-white">Publishing Calendar</h1>
            <p className="text-gray-400 mt-1">Schedule or publish approved content via creator accounts</p>
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
          {accountsLoading ? (
            <p className="text-sm text-gray-500">Loading creator accounts…</p>
          ) : !accountOptions.length ? (
            <div className="card border-amber-900/40 text-amber-200 text-sm">
              No creator accounts for this brand. Add accounts under Creator Accounts before scheduling.
            </div>
          ) : null}

          {itemsError ? (
            <div className="card border-red-900/50 text-red-300">Failed to load approved content: {errMsg(itemsErr)}</div>
          ) : itemsLoading ? (
            <div className="text-gray-500 text-center py-12">Loading approved content...</div>
          ) : !items.length ? (
            <div className="card text-center py-12">
              <Clock className="mx-auto text-gray-600 mb-3" size={40} />
              <p className="text-gray-400">No approved content ready to schedule.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {items.map((item: any, idx: number) => {
                const statusQuery = publishQueries[idx];
                const jobs = (statusQuery?.data ?? []) as any[];
                const acc = resolveAccount(item.id);
                const selectedAccId = accountByItem[item.id] ?? '';
                const dt = scheduledAtByItem[item.id] ?? '';

                return (
                  <div key={item.id} className="card-hover">
                    <div className="flex flex-wrap items-start justify-between gap-2 mb-3">
                      <div>
                        <h3 className="text-lg font-semibold text-white">{item.title}</h3>
                        <p className="text-sm text-gray-500 mt-1">
                          {String(item.content_type).replace(/_/g, ' ')}
                          {item.platform ? ` · ${item.platform}` : ''}
                        </p>
                      </div>
                      <span className="badge-green">approved</span>
                    </div>

                    <div className="mb-4">
                      <p className="text-xs text-gray-500 uppercase mb-2">Publish status</p>
                      {statusQuery?.isLoading ? (
                        <p className="text-sm text-gray-500">Loading jobs…</p>
                      ) : statusQuery?.isError ? (
                        <p className="text-sm text-red-400">{errMsg(statusQuery.error)}</p>
                      ) : !jobs.length ? (
                        <p className="text-sm text-gray-500">No publish jobs yet.</p>
                      ) : (
                        <ul className="space-y-2 text-sm">
                          {jobs.map((job: any) => (
                            <li
                              key={job.id}
                              className="flex flex-wrap items-center gap-2 border border-gray-800 rounded-lg px-3 py-2 bg-gray-950/40"
                            >
                              <span className={publishJobBadge(job.status)}>{job.status}</span>
                              <span className="text-gray-400">{job.platform}</span>
                              {job.scheduled_at ? (
                                <span className="text-gray-500">
                                  Scheduled {new Date(job.scheduled_at).toLocaleString()}
                                </span>
                              ) : null}
                              {job.published_at ? (
                                <span className="text-gray-500">
                                  Published {new Date(job.published_at).toLocaleString()}
                                </span>
                              ) : null}
                              {job.platform_post_url ? (
                                <a
                                  href={job.platform_post_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-brand-400 hover:underline"
                                >
                                  View post
                                </a>
                              ) : null}
                              {job.error_message ? (
                                <span className="text-red-400 text-xs">{job.error_message}</span>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>

                    <div className="grid md:grid-cols-2 gap-4 border-t border-gray-800 pt-4">
                      <div>
                        <label
                          className="block text-xs text-gray-500 uppercase mb-1"
                          htmlFor={`creator-account-${item.id}`}
                        >
                          Creator account
                        </label>
                        <select
                          id={`creator-account-${item.id}`}
                          className="input-field w-full"
                          aria-label="Creator account for publish"
                          value={selectedAccId}
                          onChange={(e) =>
                            setAccountByItem((m) => ({
                              ...m,
                              [item.id]: e.target.value,
                            }))
                          }
                        >
                          <option value="">Select account…</option>
                          {accountOptions.map((a) => (
                            <option key={a.id} value={a.id}>
                              @{a.platform_username} · {a.platform}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label
                          className="block text-xs text-gray-500 uppercase mb-1"
                          htmlFor={`schedule-at-${item.id}`}
                        >
                          Schedule at
                        </label>
                        <input
                          id={`schedule-at-${item.id}`}
                          type="datetime-local"
                          className="input-field w-full"
                          aria-label="Schedule publish date and time"
                          value={dt}
                          onChange={(e) =>
                            setScheduledAtByItem((m) => ({
                              ...m,
                              [item.id]: e.target.value,
                            }))
                          }
                        />
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2 mt-4">
                      <button
                        type="button"
                        className="btn-primary inline-flex items-center gap-2"
                        disabled={
                          !acc ||
                          !dt ||
                          scheduleMutation.isPending ||
                          publishNowMutation.isPending
                        }
                        onClick={() => {
                          if (!acc || !dt) return;
                          const scheduled_at = new Date(dt).toISOString();
                          scheduleMutation.mutate({
                            contentId: item.id,
                            creator_account_id: acc.id,
                            platform: acc.platform,
                            scheduled_at,
                          });
                        }}
                      >
                        <Calendar size={16} />
                        Schedule
                      </button>
                      <button
                        type="button"
                        className="btn-secondary inline-flex items-center gap-2"
                        disabled={!acc || scheduleMutation.isPending || publishNowMutation.isPending}
                        onClick={() => {
                          if (!acc) return;
                          publishNowMutation.mutate({
                            contentId: item.id,
                            creator_account_id: acc.id,
                            platform: acc.platform,
                          });
                        }}
                      >
                        <Send size={16} />
                        Publish Now
                      </button>
                    </div>
                    {scheduleMutation.isError && scheduleMutation.variables?.contentId === item.id ? (
                      <p className="text-red-400 text-sm mt-2">{errMsg(scheduleMutation.error)}</p>
                    ) : null}
                    {publishNowMutation.isError && publishNowMutation.variables?.contentId === item.id ? (
                      <p className="text-red-400 text-sm mt-2">{errMsg(publishNowMutation.error)}</p>
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
