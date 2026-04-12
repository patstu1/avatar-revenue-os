'use client';

import { useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useBrandId } from '@/hooks/useBrandId';
import { ScaleCommandCenter, scaleApi } from '@/lib/scale-api';
import {
  scaleAlertsApi,
  type LaunchCandidate as LaunchCandidateRow,
  type OperatorAlert as OperatorAlertRow,
  type LaunchReadiness,
} from '@/lib/scale-alerts-api';
import {
  AlertTriangle,
  BarChart3,
  Bell,
  Calendar,
  CheckCircle2,
  Clock,
  Layers,
  LineChart,
  Package,
  RefreshCw,
  Rocket,
  Sparkles,
  Target,
  TrendingUp,
  Wallet,
  XCircle,
} from 'lucide-react';

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

function humanizeKey(k: string) {
  return k.replace(/_/g, ' ');
}

export default function ScaleCommandCenterPage() {
  const queryClient = useQueryClient();
  const selectedBrandId = useBrandId() || '';

  const {
    data: center,
    isLoading: centerLoading,
    isError: centerError,
    error: centerErr,
  } = useQuery({
    queryKey: ['scale-command-center', selectedBrandId],
    queryFn: () => scaleApi.commandCenter(selectedBrandId).then((r) => r.data),
    enabled: Boolean(selectedBrandId),
  });

  const recMut = useMutation({
    mutationFn: () => scaleApi.recomputeRecommendations(selectedBrandId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scale-command-center', selectedBrandId] });
      queryClient.invalidateQueries({ queryKey: ['scale-recommendations', selectedBrandId] });
    },
  });

  const allocMut = useMutation({
    mutationFn: () => scaleApi.recomputeAllocations(selectedBrandId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scale-command-center', selectedBrandId] });
    },
  });

  const alertsQ = useQuery({
    queryKey: ['scale-alerts', selectedBrandId],
    queryFn: () => scaleAlertsApi.alerts(selectedBrandId).then((r) => r.data),
    enabled: Boolean(selectedBrandId),
  });
  const candidatesQ = useQuery({
    queryKey: ['scale-candidates', selectedBrandId],
    queryFn: () => scaleAlertsApi.launchCandidates(selectedBrandId).then((r) => r.data),
    enabled: Boolean(selectedBrandId),
  });
  const blockersQ = useQuery({
    queryKey: ['scale-blockers', selectedBrandId],
    queryFn: () => scaleAlertsApi.scaleBlockers(selectedBrandId).then((r) => r.data),
    enabled: Boolean(selectedBrandId),
  });
  const readinessQ = useQuery({
    queryKey: ['scale-readiness', selectedBrandId],
    queryFn: () => scaleAlertsApi.launchReadiness(selectedBrandId).then((r) => r.data),
    enabled: Boolean(selectedBrandId),
    retry: false,
  });
  const notificationsQ = useQuery({
    queryKey: ['scale-notifications', selectedBrandId],
    queryFn: () => scaleAlertsApi.notifications(selectedBrandId).then((r) => r.data),
    enabled: Boolean(selectedBrandId),
  });

  const intelMut = useMutation({
    mutationFn: () => scaleAlertsApi.recomputeAll(selectedBrandId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scale-alerts', selectedBrandId] });
      queryClient.invalidateQueries({ queryKey: ['scale-candidates', selectedBrandId] });
      queryClient.invalidateQueries({ queryKey: ['scale-blockers', selectedBrandId] });
      queryClient.invalidateQueries({ queryKey: ['scale-readiness', selectedBrandId] });
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
    mutationFn: ({ id, notes }: { id: string; notes?: string }) => scaleAlertsApi.resolve(id, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scale-alerts', selectedBrandId] });
    },
  });

  if (!selectedBrandId) {
    return (
      <div className="card text-center py-12 text-gray-500">
        No active brand selected. Use the brand switcher in the top bar.
      </div>
    );
  }

  const c = center as ScaleCommandCenter | undefined;
  const overviewAccounts = (c?.portfolio_overview?.accounts as Record<string, unknown>[]) || [];
  const allRecs = (c?.ai_recommendations as Record<string, unknown>[]) || [];
  const primaryRec =
    (allRecs.find((r) => String(r.recommendation_key) !== 'reduce_or_suppress_weak_account') as
      | Record<string, unknown>
      | undefined) ?? allRecs[0];
  const tradeoff = c?.incremental_tradeoff;
  const totals = c?.portfolio_overview?.totals;

  return (
    <div className="space-y-8 pb-16">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Rocket className="text-brand-500" size={28} aria-hidden />
            AI Scale Command Center
          </h1>
          <p className="text-gray-400 mt-1 max-w-2xl">
            Portfolio overview, incremental profit tradeoffs, allocation, and weekly ops — linked to revenue leaks
            and growth blockers.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 shrink-0">
          <button
            type="button"
            className="btn-primary flex items-center gap-2 disabled:opacity-50"
            disabled={!selectedBrandId || recMut.isPending}
            onClick={() => recMut.mutate()}
          >
            <Sparkles size={16} className={recMut.isPending ? 'animate-pulse' : ''} />
            Recompute scale
          </button>
          <button
            type="button"
            className="px-4 py-2 rounded-lg bg-gray-800 text-gray-200 text-sm border border-gray-700 hover:bg-gray-700 flex items-center gap-2 disabled:opacity-50"
            disabled={!selectedBrandId || allocMut.isPending}
            onClick={() => allocMut.mutate()}
          >
            <RefreshCw size={16} className={allocMut.isPending ? 'animate-spin' : ''} />
            Recompute allocation
          </button>
        </div>
      </div>

      <div className="card">
        <p className="text-xs text-gray-500">Scoped to the active brand (use the top-bar switcher to change brand).</p>
      </div>

      {(recMut.isError || allocMut.isError) && (
        <div className="card border-amber-900/50 text-amber-200 text-sm">
          {recMut.isError ? errMessage(recMut.error) : errMessage(allocMut.error)}
        </div>
      )}

      {centerLoading && <div className="card py-12 text-center text-gray-500">Loading command center…</div>}
      {centerError && (
        <div className="card border-red-900/50 text-red-300 py-6">{errMessage(centerErr)}</div>
      )}

      {!centerLoading && c && (
        <>
          {totals && (
            <div className="flex flex-wrap gap-4 text-sm text-gray-400">
              <span>
                Portfolio profit:{' '}
                <strong className="text-white">${Number(totals.total_profit).toLocaleString()}</strong>
              </span>
              <span>
                Revenue:{' '}
                <strong className="text-white">${Number(totals.total_revenue).toLocaleString()}</strong>
              </span>
              <span>
                Active accounts: <strong className="text-white">{totals.active_accounts}</strong>
              </span>
            </div>
          )}

          {tradeoff?.interpretation && (
            <div className="card border border-gray-700 bg-gray-900/50">
              <p className="stat-label">New account vs more volume (audit)</p>
              <p className="text-sm text-gray-300 mt-2">{tradeoff.interpretation}</p>
              <p className="text-xs text-gray-500 mt-2">
                Ratio new/volume: {Number(tradeoff.comparison_ratio_new_vs_volume ?? 0).toFixed(3)} · Winner hint:{' '}
                <span className="text-brand-300">{String(tradeoff.tradeoff_winner_hint ?? '—')}</span>
              </p>
              {c?.audit?.formula_constants && (
                <p className="text-[10px] text-gray-600 mt-3 font-mono">
                  Constants: overhead ${c.audit.formula_constants.new_account_overhead_usd} · volume_lift{' '}
                  {c.audit.formula_constants.volume_lift_factor} · expand_if_new_gt_volume ×
                  {c.audit.formula_constants.expansion_beats_existing_ratio}
                  {c.audit.funnel_weak_gate_current ? ' · funnel_weak_now' : ''}
                  {c.audit.offer_diversity_weak_current ? ' · thin_offers_now' : ''}
                </p>
              )}
            </div>
          )}

          {/* Summary strip */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="card">
              <p className="stat-label flex items-center gap-1">
                <Target size={14} /> Scale readiness
              </p>
              <p className="text-2xl font-bold text-white mt-1">
                {typeof primaryRec?.scale_readiness_score === 'number'
                  ? `${Number(primaryRec.scale_readiness_score).toFixed(0)}`
                  : '—'}
              </p>
            </div>
            <div className="card">
              <p className="stat-label flex items-center gap-1">
                <TrendingUp size={14} /> Δ profit (new acct)
              </p>
              <p className="text-2xl font-bold text-emerald-400 mt-1">
                ${typeof primaryRec?.incremental_profit_new_account === 'number' ? Number(primaryRec.incremental_profit_new_account).toFixed(0) : '0'}
              </p>
            </div>
            <div className="card">
              <p className="stat-label flex items-center gap-1">
                <LineChart size={14} /> Δ profit (volume)
              </p>
              <p className="text-2xl font-bold text-brand-300 mt-1">
                ${typeof primaryRec?.incremental_profit_existing_push === 'number' ? Number(primaryRec.incremental_profit_existing_push).toFixed(0) : '0'}
              </p>
            </div>
            <div className="card">
              <p className="stat-label flex items-center gap-1">
                <Layers size={14} /> Target accounts
              </p>
              <p className="text-2xl font-bold text-white mt-1">{c.recommended_account_count}</p>
            </div>
          </div>

          {/* Scale alerts & launch intelligence */}
          {(() => {
            const alerts = (alertsQ.data ?? []) as OperatorAlertRow[];
            const candidates = (candidatesQ.data ?? []) as LaunchCandidateRow[];
            const readiness = readinessQ.data as LaunchReadiness | undefined;
            const blockersRows = blockersQ.data ?? [];
            const notifications = notificationsQ.data ?? [];
            const blockedLaunches = candidates.filter((c) => (c.launch_blockers as unknown[] | null)?.length);
            const launchNow = candidates.filter(
              (c) => !(c.launch_blockers as unknown[] | null)?.length && c.urgency >= 45
            );
            const whyNot =
              readiness?.recommended_action && readiness.recommended_action !== 'launch_now'
                ? (readiness.gating_factors as string[] | undefined) ?? []
                : [];

            const CandidateCard = ({ row }: { row: LaunchCandidateRow }) => (
              <div
                key={row.id}
                className="rounded-xl border border-gray-800 bg-gray-900/40 p-4 text-sm text-gray-300 space-y-2"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="badge-yellow text-[10px]">{humanizeKey(row.candidate_type)}</span>
                  <span className="text-gray-500">{row.primary_platform}</span>
                  {row.secondary_platform && (
                    <span className="text-gray-600">+ {row.secondary_platform}</span>
                  )}
                </div>
                <p>
                  <span className="text-gray-500">Niche:</span> {row.niche}
                  {row.sub_niche ? ` · ${row.sub_niche}` : ''}
                </p>
                <p>
                  <span className="text-gray-500">Persona:</span> {row.avatar_persona_strategy ?? '—'}
                </p>
                <p>
                  <span className="text-gray-500">Monetization:</span> {row.monetization_path ?? '—'}
                </p>
                <p className="text-xs text-gray-400">
                  Rev/mo ${Number(row.expected_monthly_revenue_min).toLocaleString()} – $
                  {Number(row.expected_monthly_revenue_max).toLocaleString()} · Launch cost $
                  {Number(row.expected_launch_cost).toFixed(0)} · TTS {row.expected_time_to_signal_days}d · TTP{' '}
                  {row.expected_time_to_profit_days}d
                </p>
                <p className="text-xs">
                  Cannibalization {Number(row.cannibalization_risk).toFixed(2)} · Confidence{' '}
                  {Number(row.confidence).toFixed(2)} · Urgency {Number(row.urgency).toFixed(0)}
                </p>
                {Array.isArray(row.required_resources) && row.required_resources.length > 0 && (
                  <p className="text-xs text-amber-200/90 flex gap-1 flex-wrap">
                    <Package size={12} className="mt-0.5 shrink-0" />
                    {(row.required_resources as string[]).join(' · ')}
                  </p>
                )}
                {Array.isArray(row.supporting_reasons) && row.supporting_reasons.length > 0 && (
                  <ul className="text-xs text-gray-500 list-disc pl-4 space-y-1">
                    {(row.supporting_reasons as string[]).slice(0, 4).map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                )}
                {Array.isArray(row.launch_blockers) && row.launch_blockers.length > 0 && (
                  <p className="text-xs text-red-300/90 border-t border-gray-800 pt-2 mt-2">
                    Blockers: {(row.launch_blockers as string[]).join(' · ')}
                  </p>
                )}
              </div>
            );

            return (
              <div className="space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                  <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                    <Bell className="text-amber-400" size={22} aria-hidden />
                    Scale alerts &amp; launch intelligence
                  </h2>
                  <button
                    type="button"
                    className="px-4 py-2 rounded-lg bg-amber-950/40 text-amber-100 text-sm border border-amber-900/50 hover:bg-amber-950/60 flex items-center gap-2 disabled:opacity-50"
                    disabled={!selectedBrandId || intelMut.isPending}
                    onClick={() => intelMut.mutate()}
                  >
                    <RefreshCw size={16} className={intelMut.isPending ? 'animate-spin' : ''} aria-hidden />
                    Recompute alerts &amp; launch intel
                  </button>
                </div>

                {(intelMut.isError || alertsQ.isError || candidatesQ.isError) && (
                  <div className="card border-red-900/40 text-red-300 text-sm">
                    {intelMut.isError
                      ? errMessage(intelMut.error)
                      : alertsQ.isError
                        ? errMessage(alertsQ.error)
                        : errMessage(candidatesQ.error)}
                  </div>
                )}

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  <div className="card lg:col-span-2">
                    <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                      <Bell size={16} className="text-amber-400" />
                      Scale alerts feed
                    </h3>
                    {alertsQ.isLoading && <p className="text-gray-500 text-sm">Loading alerts…</p>}
                    {!alertsQ.isLoading && alerts.length === 0 && (
                      <p className="text-gray-500 text-sm">No alerts — run recompute.</p>
                    )}
                    <ul className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
                      {alerts.map((a) => (
                        <li
                          key={a.id}
                          className="rounded-lg border border-gray-800 bg-gray-950/40 p-3 text-sm"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="badge-yellow text-[10px]">{humanizeKey(a.alert_type)}</span>
                            {a.severity && (
                              <span className="text-[10px] uppercase text-gray-500">{a.severity}</span>
                            )}
                            <span className="text-gray-500 text-xs">Urgency {Number(a.urgency ?? 0).toFixed(0)}</span>
                          </div>
                          <p className="text-white font-medium mt-1">{a.title}</p>
                          <p className="text-gray-500 text-xs mt-1">{a.summary}</p>
                          <p className="text-[11px] text-gray-600 mt-2 flex items-center gap-3 flex-wrap">
                            <span className="flex items-center gap-1">
                              <Clock size={12} /> TTS {a.expected_time_to_signal_days}d
                            </span>
                            <span>
                              Upside ${Number(a.expected_upside).toFixed(0)} · Cost $
                              {Number(a.expected_cost).toFixed(0)}
                            </span>
                          </p>
                          <div className="flex flex-wrap gap-2 mt-3">
                            <button
                              type="button"
                              className="text-xs px-2 py-1 rounded bg-gray-800 text-gray-200 border border-gray-700 disabled:opacity-40"
                              disabled={a.status !== 'unread' || ackMut.isPending}
                              onClick={() => ackMut.mutate(a.id)}
                            >
                              Acknowledge
                            </button>
                            <button
                              type="button"
                              className="text-xs px-2 py-1 rounded bg-gray-900 text-gray-300 border border-gray-800 disabled:opacity-40"
                              disabled={a.status === 'resolved' || resolveMut.isPending}
                              onClick={() => resolveMut.mutate({ id: a.id })}
                            >
                              Resolve
                            </button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="card space-y-4">
                    <div>
                      <h3 className="text-sm font-semibold text-white mb-2 flex items-center gap-2">
                        <Rocket size={16} className="text-emerald-400" />
                        Launch readiness
                      </h3>
                      {readinessQ.isLoading && <p className="text-gray-500 text-xs">Loading…</p>}
                      {readinessQ.isError && (
                        <p className="text-gray-500 text-xs">Run recompute to generate readiness.</p>
                      )}
                      {readiness && (
                        <>
                          <p className="text-3xl font-bold text-white">
                            {Number(readiness.launch_readiness_score ?? 0).toFixed(0)}
                          </p>
                          <p className="text-xs text-gray-400 mt-1">{readiness.explanation}</p>
                          <p className="text-xs text-brand-300 mt-2">
                            Action: {humanizeKey(readiness.recommended_action)}
                          </p>
                        </>
                      )}
                    </div>
                    <div className="border-t border-gray-800 pt-3">
                      <h4 className="text-xs font-medium text-gray-500 uppercase mb-2">Time-to-signal (candidates)</h4>
                      <ul className="text-xs text-gray-400 space-y-1 max-h-28 overflow-y-auto">
                        {candidates.map((cand) => (
                          <li key={cand.id}>
                            {humanizeKey(cand.candidate_type)} · {cand.expected_time_to_signal_days}d
                          </li>
                        ))}
                        {!candidates.length && <li>—</li>}
                      </ul>
                    </div>
                    <div>
                      <h4 className="text-xs font-medium text-gray-500 uppercase mb-2">Notification deliveries</h4>
                      <ul className="text-[11px] text-gray-500 space-y-1 max-h-24 overflow-y-auto font-mono">
                        {notifications.slice(0, 8).map((n) => (
                          <li key={n.id}>
                            {n.channel} · {n.status}
                            {n.attempts ? ` · ${n.attempts} attempts` : ''}
                          </li>
                        ))}
                        {!notifications.length && <li>—</li>}
                      </ul>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="card">
                    <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                      <CheckCircle2 size={16} className="text-emerald-400" />
                      Launch now candidates
                    </h3>
                    <div className="space-y-3 max-h-[360px] overflow-y-auto">
                      {launchNow.map((row) => (
                        <CandidateCard key={row.id} row={row} />
                      ))}
                      {!launchNow.length && (
                        <p className="text-gray-500 text-sm">No unblocked high-urgency candidates.</p>
                      )}
                    </div>
                  </div>
                  <div className="card">
                    <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                      <XCircle size={16} className="text-red-400" />
                      Blocked launches
                    </h3>
                    <div className="space-y-3 max-h-[360px] overflow-y-auto">
                      {blockedLaunches.map((row) => (
                        <CandidateCard key={row.id} row={row} />
                      ))}
                      {!blockedLaunches.length && (
                        <p className="text-gray-500 text-sm">No candidates with active blockers.</p>
                      )}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="card">
                    <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                      <AlertTriangle size={16} className="text-amber-400" />
                      Why not yet
                    </h3>
                    {whyNot.length > 0 ? (
                      <ul className="text-sm text-gray-400 list-disc pl-5 space-y-1">
                        {whyNot.map((g, i) => (
                          <li key={i}>{g}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-gray-500 text-sm">
                        {readiness
                          ? 'No hard gates in latest readiness report, or launch action is favorable.'
                          : 'Run launch readiness recompute.'}
                      </p>
                    )}
                  </div>
                  <div className="card">
                    <h3 className="text-sm font-semibold text-white mb-3">Scale blocker diagnostics</h3>
                    <ul className="text-sm text-gray-400 space-y-2 max-h-[200px] overflow-y-auto">
                      {blockersRows.map((b) => (
                        <li key={b.id} className="border-l-2 border-amber-800/60 pl-3">
                          <span className="text-white">{b.title}</span>
                          <span className="text-gray-600 text-xs ml-2">({b.blocker_type})</span>
                        </li>
                      ))}
                      {!blockersRows.length && <li className="text-gray-500">No open blockers.</li>}
                    </ul>
                  </div>
                </div>

                <div className="card">
                  <h3 className="text-sm font-semibold text-white mb-2">Alert workflow</h3>
                  <p className="text-xs text-gray-500">
                    Acknowledge moves an alert out of the unread queue; resolve closes it for audit. Outbound email,
                    Slack, and SMS use adapter interfaces — deliveries appear in notification log with retry state.
                  </p>
                </div>
              </div>
            );
          })()}

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {/* 1 Portfolio overview */}
            <div className="card xl:col-span-2">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <BarChart3 size={20} className="text-brand-500" />
                Portfolio overview
              </h2>
              <p className="text-sm text-gray-500 mb-4">{c.portfolio_overview?.recommended_structure}</p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead>
                    <tr className="border-b border-gray-800 text-gray-500 text-xs uppercase">
                      <th className="py-2 pr-4">Account</th>
                      <th className="py-2 pr-4">Role</th>
                      <th className="py-2 pr-4">Profit</th>
                      <th className="py-2 pr-4">Profit/post</th>
                      <th className="py-2 pr-4">RPM</th>
                      <th className="py-2 pr-4">CTR</th>
                      <th className="py-2 pr-4">CVR</th>
                      <th className="py-2 pr-4">Fatigue</th>
                      <th className="py-2">Dim. returns</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800">
                    {overviewAccounts.map((row) => (
                      <tr key={String(row.id)} className="text-gray-300">
                        <td className="py-2 pr-4 text-white">{String(row.username)}</td>
                        <td className="py-2 pr-4">
                          <span className="badge-yellow text-[10px]">{String(row.scale_role || '—')}</span>
                        </td>
                        <td className="py-2 pr-4">${Number(row.profit || 0).toFixed(0)}</td>
                        <td className="py-2 pr-4">${Number(row.profit_per_post || 0).toFixed(2)}</td>
                        <td className="py-2 pr-4">${Number(row.revenue_per_mille || 0).toFixed(2)}</td>
                        <td className="py-2 pr-4">{(Number(row.ctr || 0) * 100).toFixed(2)}%</td>
                        <td className="py-2 pr-4">{(Number(row.conversion_rate || 0) * 100).toFixed(2)}%</td>
                        <td className="py-2 pr-4">{Number(row.content_fatigue || 0).toFixed(2)}</td>
                        <td className="py-2">{Number(row.diminishing_returns || 0).toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* 2 + 3 Recommendations + Best next account */}
            <div className="card">
              <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                <Sparkles size={20} className="text-brand-500" />
                AI recommendations
              </h2>
              <ul className="space-y-3 max-h-[320px] overflow-y-auto pr-2">
                {(c.ai_recommendations || []).map((r) => {
                    const rec = r as Record<string, unknown>;
                    return (
                      <li key={String(rec.id)} className="rounded-lg bg-gray-800/50 border border-gray-800 p-3">
                        <p className="text-brand-300 font-medium text-sm">
                          {humanizeKey(String(rec.recommendation_key || ''))}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">{String(rec.explanation || '')}</p>
                      </li>
                    );
                  })}
                {!c.ai_recommendations?.length && (
                  <li className="text-gray-500 text-sm">No persisted recommendations — run recompute scale.</li>
                )}
              </ul>
            </div>

            <div className="card">
              <h2 className="text-lg font-semibold text-white mb-3">Best next account to create</h2>
              <div className="rounded-lg bg-gray-800/40 border border-gray-700 p-4 text-sm text-gray-300 space-y-2">
                {Object.entries(c.best_next_account || {}).map(([k, v]) => (
                  <p key={k}>
                    <span className="text-gray-500">{humanizeKey(k)}:</span> {String(v)}
                  </p>
                ))}
                {!Object.keys(c.best_next_account || {}).length && (
                  <p className="text-gray-500">Run scale recompute to populate blueprint.</p>
                )}
              </div>
              <h3 className="text-sm font-medium text-gray-400 mt-6 mb-2">Recommended account count</h3>
              <p className="text-3xl font-bold text-white">{c.recommended_account_count}</p>
            </div>

            {/* 5 Platform allocation */}
            <div className="card">
              <h2 className="text-lg font-semibold text-white mb-4">Platform allocation view</h2>
              <ul className="space-y-2">
                {Object.entries(c.platform_allocation || {}).map(([plat, blob]) => {
                  const b = blob as { pct: number; accounts: string[] };
                  return (
                    <li key={plat} className="flex justify-between items-center border-b border-gray-800 pb-2">
                      <span className="capitalize text-gray-300">{plat}</span>
                      <span className="text-brand-300 font-mono">{b.pct.toFixed(1)}%</span>
                    </li>
                  );
                })}
              </ul>
              {!Object.keys(c.platform_allocation || {}).length && (
                <p className="text-gray-500 text-sm">Recompute portfolio allocation to populate weights.</p>
              )}
            </div>

            {/* 6 Niche expansion */}
            <div className="card">
              <h2 className="text-lg font-semibold text-white mb-4">Niche expansion view</h2>
              <div className="text-sm text-gray-400 space-y-2 mb-4">
                <p>
                  Expansion readiness:{' '}
                  <span className="text-white">
                    {Number((c.niche_expansion as { expansion_readiness?: number })?.expansion_readiness || 0).toFixed(1)}
                  </span>
                </p>
                <p>
                  Segment separation:{' '}
                  <span className="text-white">
                    {Number((c.niche_expansion as { segment_separation?: number })?.segment_separation || 0).toFixed(2)}
                  </span>
                </p>
              </div>
              <ul className="space-y-1 text-sm text-gray-400 max-h-40 overflow-y-auto">
                {((c.niche_expansion as { clusters?: { label?: string; niche_focus?: string; profit?: number }[] })?.clusters || []).map(
                  (cl, i) => (
                    <li key={i}>
                      {cl.label} — {cl.niche_focus} (${Number(cl.profit || 0).toFixed(0)})
                    </li>
                  )
                )}
              </ul>
            </div>

            {/* 7 Revenue leaks */}
            <div className="card">
              <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                <Wallet size={20} className="text-amber-500" />
                Revenue leak alerts
              </h2>
              <ul className="space-y-2 text-sm max-h-56 overflow-y-auto">
                {(c.revenue_leak_alerts || []).map((L, i) => {
                  const leak = L as Record<string, unknown>;
                  return (
                    <li key={i} className="border-l-2 border-amber-600/60 pl-3 py-1">
                      <p className="text-amber-200/90">{String(leak.entity)}</p>
                      <p className="text-gray-500 text-xs">{String(leak.detail || '')}</p>
                    </li>
                  );
                })}
                {!c.revenue_leak_alerts?.length && (
                  <li className="text-gray-500">No leak preview for this brand.</li>
                )}
              </ul>
            </div>

            {/* 8 Growth blockers */}
            <div className="card">
              <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                <AlertTriangle size={20} className="text-red-400" />
                Growth blockers
              </h2>
              <ul className="space-y-2 text-sm max-h-56 overflow-y-auto">
                {(c.growth_blockers || []).map((B, i) => {
                  const b = B as Record<string, unknown>;
                  return (
                    <li key={i} className="rounded bg-gray-800/40 p-2 border border-gray-800">
                      <p className="text-gray-200">{String(b.username || b.account_id)}</p>
                      <p className="text-xs text-red-300/80">{String(b.primary_bottleneck)}</p>
                      <p className="text-xs text-gray-500">{String(b.explanation || '').slice(0, 160)}</p>
                    </li>
                  );
                })}
                {!c.growth_blockers?.length && <li className="text-gray-500">No bottleneck rows.</li>}
              </ul>
            </div>

            {/* 9 Warnings */}
            <div className="card xl:col-span-2">
              <h2 className="text-lg font-semibold text-white mb-3">Saturation & cannibalization warnings</h2>
              <div className="grid md:grid-cols-2 gap-3">
                {(c.saturation_cannibalization_warnings || []).map((w, i) => {
                  const x = w as Record<string, unknown>;
                  return (
                    <div key={i} className="rounded-lg border border-amber-900/40 bg-amber-950/20 p-3 text-sm">
                      <span className="badge-yellow text-[10px]">{String(x.type)}</span>
                      <p className="text-gray-200 mt-2">{String(x.account)}</p>
                      <p className="text-gray-500 text-xs mt-1">{String(x.detail)}</p>
                    </div>
                  );
                })}
                {!c.saturation_cannibalization_warnings?.length && (
                  <p className="text-gray-500 text-sm">No active warnings.</p>
                )}
              </div>
            </div>

            {/* 10 Weekly plan */}
            <div className="card xl:col-span-2">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Calendar size={20} className="text-brand-500" />
                Weekly action plan
              </h2>
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                {(c.weekly_action_plan || []).map((day, i) => (
                  <div key={i} className="rounded-lg border border-gray-800 bg-gray-900/40 p-4">
                    <p className="text-brand-300 font-medium">{day.day}</p>
                    <p className="text-xs text-gray-500 mt-1">{day.theme}</p>
                    <ul className="mt-3 space-y-2 text-xs text-gray-400 list-disc pl-4">
                      {(day.actions || []).map((a, j) => (
                        <li key={j}>{a}</li>
                      ))}
                    </ul>
                  </div>
                ))}
                {!c.weekly_action_plan?.length && (
                  <p className="text-gray-500 text-sm">Run scale recompute to generate the plan.</p>
                )}
              </div>
              {c.computed_at && (
                <p className="text-[10px] text-gray-600 mt-4">Snapshot: {c.computed_at}</p>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
