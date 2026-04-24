'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { brandsApi } from '@/lib/api';
import { scaleAlertsApi } from '@/lib/scale-alerts-api';
import {
  AlertTriangle,
  Bell,
  CheckCircle,
  Gauge,
  RefreshCw,
  Rocket,
  Send,
  ShieldAlert,
} from 'lucide-react';

type Brand = { id: string; name: string };

type ScaleAlert = {
  id: string;
  alert_type: string;
  title: string;
  summary: string;
  confidence: number;
  urgency: number;
  expected_upside: number;
  status: string;
};

type LaunchCandidate = {
  id: string;
  candidate_type: string;
  primary_platform: string;
  niche: string;
  sub_niche?: string | null;
  avatar_persona_strategy?: string | null;
  monetization_path?: string | null;
  content_style?: string | null;
  posting_strategy?: string | null;
  expected_monthly_revenue_min: number;
  expected_monthly_revenue_max: number;
  expected_launch_cost: number;
  expected_time_to_signal_days: number;
  expected_time_to_profit_days: number;
  cannibalization_risk: number;
  audience_separation_score: number;
  confidence: number;
  urgency: number;
  supporting_reasons?: unknown[] | null;
  required_resources?: unknown[] | null;
  launch_blockers?: unknown[] | null;
};

type ScaleBlocker = {
  id: string;
  blocker_type: string;
  severity: string;
  title: string;
  explanation?: string | null;
  recommended_fix?: string | null;
  current_value: number;
  threshold_value: number;
};

type LaunchReadiness = {
  id: string;
  launch_readiness_score: number;
  explanation?: string | null;
  recommended_action: string;
  gating_factors?: unknown[] | null;
  components?: Record<string, unknown> | null;
};

type ScaleNotification = {
  id: string;
  channel: string;
  status: string;
  attempts: number;
  last_error?: string | null;
};

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

function pct01(n: number) {
  const x = Number(n);
  if (Number.isNaN(x)) return 0;
  if (x > 1) return Math.min(100, x);
  return Math.min(100, Math.max(0, x * 100));
}

function badgeClass(kind: 'neutral' | 'brand' | 'amber' | 'green' | 'red' | 'orange') {
  const map = {
    neutral: 'bg-gray-800 text-gray-300 border-gray-700',
    brand: 'bg-brand-600/20 text-brand-300 border-brand-500/40',
    amber: 'bg-amber-900/40 text-amber-200 border-amber-700/50',
    green: 'bg-emerald-900/40 text-emerald-200 border-emerald-700/50',
    red: 'bg-red-900/40 text-red-200 border-red-700/50',
    orange: 'bg-orange-900/40 text-orange-200 border-orange-700/50',
  };
  return map[kind];
}

function severityKind(sev: string): 'red' | 'orange' | 'amber' | 'neutral' {
  const s = String(sev).toLowerCase();
  if (s === 'critical') return 'red';
  if (s === 'high') return 'orange';
  if (s === 'medium') return 'amber';
  return 'neutral';
}

function listItems(raw: unknown[] | null | undefined) {
  if (!raw?.length) return [];
  return raw.map((x) => (typeof x === 'string' ? x : JSON.stringify(x)));
}

const TABS = [
  { id: 'alerts' as const, label: 'Alerts', icon: Bell },
  { id: 'candidates' as const, label: 'Candidates', icon: Rocket },
  { id: 'blockers' as const, label: 'Blockers', icon: ShieldAlert },
  { id: 'readiness' as const, label: 'Readiness', icon: Gauge },
  { id: 'notifications' as const, label: 'Notifications', icon: Send },
];

export default function ScaleAlertsPage() {
  const queryClient = useQueryClient();
  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [tab, setTab] = useState<(typeof TABS)[number]['id']>('alerts');

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) {
      setSelectedBrandId(String(brands[0].id));
    }
  }, [brands, selectedBrandId]);

  const alertsQ = useQuery({
    queryKey: ['scale-alerts', selectedBrandId],
    queryFn: () => scaleAlertsApi.alerts(selectedBrandId).then((r) => r.data as ScaleAlert[]),
    enabled: Boolean(selectedBrandId),
  });

  const candidatesQ = useQuery({
    queryKey: ['launch-candidates', selectedBrandId],
    queryFn: () => scaleAlertsApi.launchCandidates(selectedBrandId).then((r) => r.data as LaunchCandidate[]),
    enabled: Boolean(selectedBrandId),
  });

  const blockersQ = useQuery({
    queryKey: ['scale-blockers', selectedBrandId],
    queryFn: () => scaleAlertsApi.scaleBlockers(selectedBrandId).then((r) => r.data as ScaleBlocker[]),
    enabled: Boolean(selectedBrandId),
  });

  const readinessQ = useQuery({
    queryKey: ['launch-readiness', selectedBrandId],
    queryFn: async () => {
      try {
        const r = await scaleAlertsApi.launchReadiness(selectedBrandId);
        return r.data as LaunchReadiness;
      } catch (e) {
        if (axios.isAxiosError(e) && e.response?.status === 404) return null;
        throw e;
      }
    },
    enabled: Boolean(selectedBrandId),
  });

  const notificationsQ = useQuery({
    queryKey: ['scale-notifications', selectedBrandId],
    queryFn: () => scaleAlertsApi.notifications(selectedBrandId).then((r) => r.data as ScaleNotification[]),
    enabled: Boolean(selectedBrandId),
  });

  const recomputeAll = useMutation({
    mutationFn: () => scaleAlertsApi.recomputeAll(selectedBrandId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scale-alerts', selectedBrandId] });
      queryClient.invalidateQueries({ queryKey: ['launch-candidates', selectedBrandId] });
      queryClient.invalidateQueries({ queryKey: ['scale-blockers', selectedBrandId] });
      queryClient.invalidateQueries({ queryKey: ['launch-readiness', selectedBrandId] });
      queryClient.invalidateQueries({ queryKey: ['scale-notifications', selectedBrandId] });
    },
  });

  const ackMut = useMutation({
    mutationFn: (alertId: string) => scaleAlertsApi.acknowledge(alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scale-alerts', selectedBrandId] });
    },
  });

  const resolveMut = useMutation({
    mutationFn: ({ alertId, notes }: { alertId: string; notes?: string }) =>
      scaleAlertsApi.resolve(alertId, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scale-alerts', selectedBrandId] });
    },
  });

  const selectedBrand = useMemo(
    () => brands?.find((b) => String(b.id) === selectedBrandId),
    [brands, selectedBrandId]
  );

  if (brandsLoading) {
    return (
      <div className="min-h-[60vh] rounded-xl border border-gray-800 bg-gray-900 p-8 text-white">
        <div className="h-8 w-80 bg-gray-800 rounded animate-pulse mb-6" />
        <div className="h-40 bg-gray-800/80 rounded animate-pulse" />
        <p className="text-center text-brand-300 mt-8">Loading…</p>
      </div>
    );
  }

  if (brandsError) {
    return (
      <div className="rounded-xl border border-red-900/50 bg-gray-900 p-8 text-red-300 flex items-center gap-2">
        <AlertTriangle size={20} />
        {errMessage(brandsErr)}
      </div>
    );
  }

  if (!brands?.length) {
    return (
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-12 text-center text-gray-400">
        <CheckCircle className="mx-auto mb-3 text-brand-300 opacity-50" size={32} />
        Create a brand to use Scale Alerts.
      </div>
    );
  }

  return (
    <div className="space-y-6 rounded-xl border border-gray-800 bg-gray-900 p-6 md:p-8 text-white">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2 text-white">
            <Bell className="text-brand-300" size={28} aria-hidden />
            Scale Alerts
          </h1>
          <p className="text-gray-400 mt-1 max-w-2xl text-sm">
            Launch candidates, blockers, readiness, and operator notifications for scaling decisions.
          </p>
        </div>
        <button
          type="button"
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-gray-700 bg-gray-800 px-4 py-2.5 text-sm font-medium text-brand-300 hover:bg-gray-700 disabled:opacity-50"
          disabled={!selectedBrandId || recomputeAll.isPending}
          onClick={() => recomputeAll.mutate()}
        >
          <RefreshCw size={16} className={recomputeAll.isPending ? 'animate-spin' : ''} />
          Recompute All Scale Intelligence
        </button>
      </div>

      <div className="max-w-xl rounded-lg border border-gray-800 bg-gray-950/50 p-4">
        <label className="block text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">Brand</label>
        <select
          className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 outline-none"
          value={selectedBrandId}
          onChange={(e) => setSelectedBrandId(e.target.value)}
          aria-label="Select brand for scale alerts"
        >
          {brands.map((b) => (
            <option key={b.id} value={String(b.id)}>
              {b.name}
            </option>
          ))}
        </select>
        {selectedBrand && <p className="text-xs text-gray-500 mt-2">Viewing: {selectedBrand.name}</p>}
      </div>

      {(recomputeAll.isError || ackMut.isError || resolveMut.isError) && (
        <div className="rounded-lg border border-amber-900/50 bg-amber-950/20 px-4 py-3 text-sm text-amber-200 flex items-start gap-2">
          <AlertTriangle size={18} className="shrink-0 mt-0.5" />
          <span>
            {recomputeAll.isError
              ? errMessage(recomputeAll.error)
              : ackMut.isError
                ? errMessage(ackMut.error)
                : errMessage(resolveMut.error)}
          </span>
        </div>
      )}

      <div className="flex flex-wrap gap-2 border-b border-gray-800 pb-1">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = tab === t.id;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`inline-flex items-center gap-2 rounded-t-lg px-4 py-2.5 text-sm font-medium transition-colors ${
                active
                  ? 'bg-gray-800 text-brand-300 border border-b-0 border-gray-700'
                  : 'text-gray-400 hover:text-gray-200 border border-transparent'
              }`}
            >
              <Icon size={16} aria-hidden />
              {t.label}
            </button>
          );
        })}
      </div>

      <div className="pt-2">
        {tab === 'alerts' && (
          <section aria-labelledby="tab-alerts">
            <h2 id="tab-alerts" className="sr-only">
              Scale alerts feed
            </h2>
            {alertsQ.isLoading && (
              <div className="py-16 text-center text-brand-300">Loading alerts…</div>
            )}
            {alertsQ.isError && (
              <div className="rounded-lg border border-red-900/50 p-6 text-red-300 flex gap-2">
                <AlertTriangle size={20} />
                {errMessage(alertsQ.error)}
              </div>
            )}
            {!alertsQ.isLoading && !alertsQ.isError && !(alertsQ.data?.length ?? 0) && (
              <div className="py-16 text-center text-gray-500 border border-dashed border-gray-800 rounded-lg">
                No alerts yet. Run recompute to populate.
              </div>
            )}
            {!alertsQ.isLoading && !alertsQ.isError && (alertsQ.data?.length ?? 0) > 0 && (
              <ul className="space-y-4">
                {alertsQ.data!.map((a) => {
                  const st = String(a.status).toLowerCase();
                  const statusKind: 'brand' | 'amber' | 'green' =
                    st === 'resolved' ? 'green' : st === 'acknowledged' ? 'amber' : 'brand';
                  return (
                    <li
                      key={a.id}
                      className="rounded-xl border border-gray-800 bg-gray-950/40 p-4 space-y-3"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <span
                          className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${badgeClass('neutral')}`}
                        >
                          {a.alert_type}
                        </span>
                        <span
                          className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium capitalize ${badgeClass(statusKind)}`}
                        >
                          {a.status}
                        </span>
                      </div>
                      <h3 className="text-lg font-semibold text-white">{a.title}</h3>
                      <p className="text-sm text-gray-400">{a.summary}</p>
                      <div className="space-y-1">
                        <div className="flex justify-between text-xs text-gray-500">
                          <span>Urgency</span>
                          <span className="text-brand-300">{pct01(a.urgency).toFixed(0)}%</span>
                        </div>
                        <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
                          <div
                            className="h-full rounded-full bg-brand-500/80"
                            style={{ width: `${pct01(a.urgency)}%` }}
                          />
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-4 text-sm">
                        <span className="text-gray-400">
                          Confidence:{' '}
                          <strong className="text-brand-300">{(Number(a.confidence) * 100).toFixed(0)}%</strong>
                        </span>
                        <span className="text-gray-400">
                          Expected upside:{' '}
                          <strong className="text-white">${Number(a.expected_upside).toLocaleString()}</strong>
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-xs font-medium text-brand-300 hover:bg-gray-700 disabled:opacity-40"
                          disabled={ackMut.isPending || st === 'acknowledged' || st === 'resolved'}
                          onClick={() => ackMut.mutate(a.id)}
                        >
                          Acknowledge
                        </button>
                        <button
                          type="button"
                          className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-xs font-medium text-gray-200 hover:bg-gray-700 disabled:opacity-40"
                          disabled={resolveMut.isPending || st === 'resolved'}
                          onClick={() => {
                            const notes = typeof window !== 'undefined' ? window.prompt('Resolution notes (optional)') : null;
                            resolveMut.mutate({ alertId: a.id, notes: notes || undefined });
                          }}
                        >
                          Resolve
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        )}

        {tab === 'candidates' && (
          <section aria-labelledby="tab-candidates">
            <h2 id="tab-candidates" className="sr-only">
              Launch candidates
            </h2>
            {candidatesQ.isLoading && (
              <div className="py-16 text-center text-brand-300">Loading candidates…</div>
            )}
            {candidatesQ.isError && (
              <div className="rounded-lg border border-red-900/50 p-6 text-red-300 flex gap-2">
                <AlertTriangle size={20} />
                {errMessage(candidatesQ.error)}
              </div>
            )}
            {!candidatesQ.isLoading && !candidatesQ.isError && !(candidatesQ.data?.length ?? 0) && (
              <div className="py-16 text-center text-gray-500 border border-dashed border-gray-800 rounded-lg">
                No launch candidates. Run recompute to generate.
              </div>
            )}
            {!candidatesQ.isLoading && !candidatesQ.isError && (candidatesQ.data?.length ?? 0) > 0 && (
              <div className="grid gap-4 md:grid-cols-2">
                {candidatesQ.data!.map((c) => (
                  <article
                    key={c.id}
                    className="rounded-xl border border-gray-800 bg-gray-950/40 p-4 space-y-3"
                  >
                    <div className="flex flex-wrap gap-2">
                      <span
                        className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${badgeClass('brand')}`}
                      >
                        {c.candidate_type}
                      </span>
                      <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs ${badgeClass('neutral')}`}>
                        {c.primary_platform}
                      </span>
                    </div>
                    <p className="text-sm text-gray-300">
                      <span className="text-gray-500">Niche:</span> {c.niche}
                      {c.sub_niche ? (
                        <>
                          {' '}
                          · <span className="text-gray-500">Sub:</span> {c.sub_niche}
                        </>
                      ) : null}
                    </p>
                    <dl className="grid grid-cols-1 gap-2 text-xs text-gray-400">
                      {c.avatar_persona_strategy ? (
                        <div>
                          <dt className="text-gray-600">Avatar strategy</dt>
                          <dd className="text-gray-300">{c.avatar_persona_strategy}</dd>
                        </div>
                      ) : null}
                      {c.monetization_path ? (
                        <div>
                          <dt className="text-gray-600">Monetization</dt>
                          <dd className="text-gray-300">{c.monetization_path}</dd>
                        </div>
                      ) : null}
                      {c.content_style ? (
                        <div>
                          <dt className="text-gray-600">Content style</dt>
                          <dd className="text-gray-300">{c.content_style}</dd>
                        </div>
                      ) : null}
                      {c.posting_strategy ? (
                        <div>
                          <dt className="text-gray-600">Posting</dt>
                          <dd className="text-gray-300">{c.posting_strategy}</dd>
                        </div>
                      ) : null}
                    </dl>
                    <div className="text-sm text-gray-300">
                      Revenue range:{' '}
                      <strong className="text-white">
                        ${Number(c.expected_monthly_revenue_min).toLocaleString()} – $
                        {Number(c.expected_monthly_revenue_max).toLocaleString()}
                      </strong>
                      /mo
                    </div>
                    <div className="flex flex-wrap gap-3 text-xs text-gray-400">
                      <span>
                        Launch cost:{' '}
                        <strong className="text-brand-300">${Number(c.expected_launch_cost).toLocaleString()}</strong>
                      </span>
                      <span>
                        Signal: <strong className="text-white">{c.expected_time_to_signal_days}d</strong>
                      </span>
                      <span>
                        Profit: <strong className="text-white">{c.expected_time_to_profit_days}d</strong>
                      </span>
                    </div>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs text-gray-500">
                        <span>Cannibalization risk</span>
                        <span className="text-brand-300">{pct01(c.cannibalization_risk).toFixed(0)}%</span>
                      </div>
                      <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-orange-500/70"
                          style={{ width: `${pct01(c.cannibalization_risk)}%` }}
                        />
                      </div>
                    </div>
                    <div className="text-xs text-gray-400">
                      Audience separation:{' '}
                      <strong className="text-brand-300">
                        {(Number(c.audience_separation_score) * 100).toFixed(0)}%
                      </strong>
                      {' · '}
                      Confidence{' '}
                      <strong className="text-white">{(Number(c.confidence) * 100).toFixed(0)}%</strong>
                      {' · '}
                      Urgency{' '}
                      <strong className="text-white">{(Number(c.urgency) * 100).toFixed(0)}%</strong>
                    </div>
                    {listItems(c.supporting_reasons as unknown[]).length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                          Supporting reasons
                        </p>
                        <ul className="list-disc list-inside text-sm text-gray-300 space-y-1">
                          {listItems(c.supporting_reasons as unknown[]).map((line, i) => (
                            <li key={i}>{line}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {listItems(c.required_resources as unknown[]).length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                          Required resources
                        </p>
                        <ul className="list-disc list-inside text-sm text-gray-300 space-y-1">
                          {listItems(c.required_resources as unknown[]).map((line, i) => (
                            <li key={i}>{line}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {listItems(c.launch_blockers as unknown[]).length > 0 && (
                      <div className="rounded-lg border border-amber-900/40 bg-amber-950/20 p-3">
                        <p className="text-xs font-semibold text-amber-200/90 mb-1 flex items-center gap-1">
                          <AlertTriangle size={14} />
                          Blockers
                        </p>
                        <ul className="list-disc list-inside text-sm text-amber-100/90 space-y-1">
                          {listItems(c.launch_blockers as unknown[]).map((line, i) => (
                            <li key={i}>{line}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </article>
                ))}
              </div>
            )}
          </section>
        )}

        {tab === 'blockers' && (
          <section aria-labelledby="tab-blockers">
            <h2 id="tab-blockers" className="sr-only">
              Scale blockers
            </h2>
            {blockersQ.isLoading && (
              <div className="py-16 text-center text-brand-300">Loading blockers…</div>
            )}
            {blockersQ.isError && (
              <div className="rounded-lg border border-red-900/50 p-6 text-red-300 flex gap-2">
                <AlertTriangle size={20} />
                {errMessage(blockersQ.error)}
              </div>
            )}
            {!blockersQ.isLoading && !blockersQ.isError && !(blockersQ.data?.length ?? 0) && (
              <div className="py-16 text-center text-gray-500 border border-dashed border-gray-800 rounded-lg flex flex-col items-center gap-2">
                <CheckCircle className="text-brand-300/40" size={28} />
                No scale blockers detected.
              </div>
            )}
            {!blockersQ.isLoading && !blockersQ.isError && (blockersQ.data?.length ?? 0) > 0 && (
              <ul className="space-y-3">
                {blockersQ.data!.map((b) => {
                  const sk = severityKind(b.severity);
                  return (
                    <li
                      key={b.id}
                      className={`rounded-xl border p-4 bg-gray-950/40 ${sk === 'red' ? 'border-red-900/60' : sk === 'orange' ? 'border-orange-900/50' : sk === 'amber' ? 'border-amber-900/50' : 'border-gray-800'}`}
                    >
                      <div className="flex flex-wrap items-center gap-2 mb-2">
                        <span
                          className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${badgeClass('neutral')}`}
                        >
                          {b.blocker_type}
                        </span>
                        <span
                          className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium capitalize ${badgeClass(sk === 'red' ? 'red' : sk === 'orange' ? 'orange' : sk === 'amber' ? 'amber' : 'neutral')}`}
                        >
                          {b.severity}
                        </span>
                      </div>
                      <h3 className="font-semibold text-white">{b.title}</h3>
                      {b.explanation ? <p className="text-sm text-gray-400 mt-1">{b.explanation}</p> : null}
                      {b.recommended_fix ? (
                        <p className="text-sm text-brand-300 mt-2">
                          <span className="text-gray-500">Fix:</span> {b.recommended_fix}
                        </p>
                      ) : null}
                      <p className="text-xs text-gray-500 mt-3">
                        Current <strong className="text-white">{Number(b.current_value).toFixed(2)}</strong> vs
                        threshold <strong className="text-white">{Number(b.threshold_value).toFixed(2)}</strong>
                      </p>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        )}

        {tab === 'readiness' && (
          <section aria-labelledby="tab-readiness">
            <h2 id="tab-readiness" className="sr-only">
              Launch readiness
            </h2>
            {readinessQ.isLoading && (
              <div className="py-16 text-center text-brand-300">Loading readiness…</div>
            )}
            {readinessQ.isError && (
              <div className="rounded-lg border border-red-900/50 p-6 text-red-300 flex gap-2">
                <AlertTriangle size={20} />
                {errMessage(readinessQ.error)}
              </div>
            )}
            {!readinessQ.isLoading && !readinessQ.isError && readinessQ.data === null && (
              <div className="py-16 text-center text-gray-500 border border-dashed border-gray-800 rounded-lg">
                No readiness report yet. Use &quot;Recompute All Scale Intelligence&quot; to generate.
              </div>
            )}
            {!readinessQ.isLoading && !readinessQ.isError && readinessQ.data && (
              <div className="space-y-6">
                <div className="flex flex-wrap items-end gap-6 rounded-xl border border-gray-800 bg-gray-950/40 p-6">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-gray-500 mb-1">Launch readiness</p>
                    <p className="text-5xl font-bold text-brand-300 tabular-nums">
                      {Math.round(Number(readinessQ.data.launch_readiness_score) * 100) / 100}
                    </p>
                  </div>
                  <div className="pb-1">
                    <span
                      className={`inline-flex rounded-md border px-3 py-1 text-sm font-medium capitalize ${badgeClass('brand')}`}
                    >
                      {readinessQ.data.recommended_action}
                    </span>
                  </div>
                </div>
                {readinessQ.data.explanation ? (
                  <p className="text-sm text-gray-300 leading-relaxed">{readinessQ.data.explanation}</p>
                ) : null}
                {listItems(readinessQ.data.gating_factors as unknown[]).length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                      Gating factors
                    </p>
                    <ul className="space-y-2">
                      {listItems(readinessQ.data.gating_factors as unknown[]).map((g, i) => (
                        <li
                          key={i}
                          className="flex gap-2 text-sm text-gray-300 border-l-2 border-brand-500/50 pl-3"
                        >
                          {g}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {readinessQ.data.components && Object.keys(readinessQ.data.components).length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                      Component breakdown
                    </p>
                    <div className="rounded-lg border border-gray-800 overflow-hidden">
                      <table className="w-full text-sm">
                        <tbody>
                          {Object.entries(readinessQ.data.components).map(([k, v]) => (
                            <tr key={k} className="border-t border-gray-800 first:border-t-0">
                              <td className="px-4 py-2 text-gray-500 capitalize">{k.replace(/_/g, ' ')}</td>
                              <td className="px-4 py-2 text-brand-300 text-right font-mono text-xs">
                                {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </section>
        )}

        {tab === 'notifications' && (
          <section aria-labelledby="tab-notifications">
            <h2 id="tab-notifications" className="sr-only">
              Notification feed
            </h2>
            {notificationsQ.isLoading && (
              <div className="py-16 text-center text-brand-300">Loading notifications…</div>
            )}
            {notificationsQ.isError && (
              <div className="rounded-lg border border-red-900/50 p-6 text-red-300 flex gap-2">
                <AlertTriangle size={20} />
                {errMessage(notificationsQ.error)}
              </div>
            )}
            {!notificationsQ.isLoading && !notificationsQ.isError && !(notificationsQ.data?.length ?? 0) && (
              <div className="py-16 text-center text-gray-500 border border-dashed border-gray-800 rounded-lg">
                No notifications logged for this brand.
              </div>
            )}
            {!notificationsQ.isLoading && !notificationsQ.isError && (notificationsQ.data?.length ?? 0) > 0 && (
              <ul className="space-y-3">
                {notificationsQ.data!.map((n) => (
                  <li
                    key={n.id}
                    className="rounded-xl border border-gray-800 bg-gray-950/40 p-4 flex flex-wrap gap-4 justify-between items-start"
                  >
                    <div>
                      <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${badgeClass('brand')}`}>
                        {n.channel}
                      </span>
                      <p className="text-sm text-gray-400 mt-2">
                        Status:{' '}
                        <strong className="text-white capitalize">{n.status}</strong>
                      </p>
                      <p className="text-xs text-gray-500 mt-1">Attempts: {n.attempts}</p>
                    </div>
                    <div className="text-right max-w-md min-w-[12rem]">
                      <p className="text-xs font-semibold text-gray-500 uppercase">Errors</p>
                      <p className="text-sm text-red-300/90 break-words mt-1">
                        {n.last_error || '—'}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
