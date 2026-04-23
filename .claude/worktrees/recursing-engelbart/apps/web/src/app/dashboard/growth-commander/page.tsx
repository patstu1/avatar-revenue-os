'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { growthCommanderApi } from '@/lib/growth-commander-api';
import {
  BarChart3,
  Command,
  RefreshCw,
  Shield,
  Sparkles,
  Target,
  TrendingUp,
} from 'lucide-react';

type Brand = { id: string; name: string };

type GrowthCommand = {
  id: string;
  command_type: string;
  priority: number;
  title: string;
  exact_instruction: string;
  execution_spec?: Record<string, unknown> | null;
  required_resources?: Record<string, unknown> | null;
  comparison?: {
    incremental_new?: number;
    incremental_existing?: number;
    winner?: string;
  } | null;
  platform_fit?: { platform?: string; fit_score?: number; reason?: string } | null;
  niche_fit?: { niche?: string; sub_niche?: string; fit_score?: number; reason?: string } | null;
  cannibalization_analysis?: {
    risk?: number;
    overlap_accounts?: string[];
    mitigation?: string;
  } | null;
  success_threshold?: Record<string, unknown> | null;
  failure_threshold?: Record<string, unknown> | null;
  expected_upside: number;
  expected_cost: number;
  expected_time_to_signal_days: number;
  expected_time_to_profit_days: number;
  confidence: number;
  urgency: number;
  blocking_factors?: string[] | null;
  first_week_plan?: { day?: string; action?: string }[] | null;
  evidence?: Record<string, unknown> | null;
};

type PortfolioBalance = {
  total_accounts?: number;
  platform_distribution?: Record<string, number>;
  overbuilt?: { platform: string; count?: number; share?: number; reason?: string }[];
  underbuilt?: { platform: string; count?: number; reason?: string }[];
  absent_platforms?: string[];
};

type WhitespaceOpp = {
  platform?: string;
  niche?: string;
  geography?: string;
  reason?: string;
  estimated_opportunity_score?: number;
  language?: string;
};

type PortfolioAssessment = {
  balance: PortfolioBalance;
  whitespace: WhitespaceOpp[];
  latest_portfolio_directive?: Record<string, unknown> | null;
};

type GrowthCommandRun = {
  id: string;
  created_at: string;
  status: string;
  commands_generated: number;
  command_types: string[];
  whitespace_count: number;
};

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

function commandTypeBadgeClass(t: string) {
  switch (t) {
    case 'launch_account':
      return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
    case 'increase_output':
      return 'bg-sky-500/20 text-sky-300 border-sky-500/40';
    case 'fix_funnel_first':
      return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
    case 'suppress_account':
    case 'pause_account':
      return 'bg-red-500/20 text-red-300 border-red-500/40';
    case 'do_nothing':
      return 'bg-gray-600/40 text-gray-300 border-gray-600';
    default:
      return 'bg-violet-500/15 text-violet-300 border-violet-500/30';
  }
}

function pct01(n: number | undefined) {
  if (n == null || Number.isNaN(n)) return 0;
  return n <= 1 ? n * 100 : Math.min(100, n);
}

function ScoreBar({ label, value, accent }: { label: string; value: number; accent: string }) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div>
      <div className="flex justify-between text-xs text-gray-400 mb-1">
        <span>{label}</span>
        <span className="text-brand-300">{pct.toFixed(0)}%</span>
      </div>
      <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
        <div className={`h-full rounded-full transition-all ${accent}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function ThresholdCard({ title, data }: { title: string; data: Record<string, unknown> | null | undefined }) {
  if (!data || typeof data !== 'object') {
    return (
      <div className="rounded-lg border border-gray-800 bg-gray-800/40 p-3 text-sm text-gray-500">
        {title}: —
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-800/40 p-3 text-sm">
      <div className="text-xs font-semibold uppercase tracking-wide text-brand-300 mb-2">{title}</div>
      <dl className="space-y-1 text-gray-300">
        {Object.entries(data).map(([k, v]) => (
          <div key={k} className="flex justify-between gap-2">
            <dt className="text-gray-500 shrink-0">{k.replace(/_/g, ' ')}</dt>
            <dd className="text-right break-all">{typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

type TabId = 'commands' | 'portfolio' | 'whitespace';

export default function GrowthCommanderPage() {
  const queryClient = useQueryClient();
  const [brandId, setBrandId] = useState('');
  const [tab, setTab] = useState<TabId>('commands');

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) {
      setBrandId(String(brands[0].id));
    }
  }, [brands, brandId]);

  const {
    data: commandsRaw,
    isLoading: commandsLoading,
    isError: commandsError,
    error: commandsErr,
  } = useQuery({
    queryKey: ['growth-commands', brandId],
    queryFn: () => growthCommanderApi.commands(brandId).then((r) => r.data as GrowthCommand[]),
    enabled: Boolean(brandId),
  });

  const {
    data: portfolioRaw,
    isLoading: portfolioLoading,
    isError: portfolioError,
    error: portfolioErr,
  } = useQuery({
    queryKey: ['portfolio-assessment', brandId],
    queryFn: () => growthCommanderApi.portfolioAssessment(brandId).then((r) => r.data as PortfolioAssessment),
    enabled: Boolean(brandId),
  });

  const { data: runsRaw } = useQuery({
    queryKey: ['growth-command-runs', brandId],
    queryFn: () => growthCommanderApi.runs(brandId).then((r) => r.data as GrowthCommandRun[]),
    enabled: Boolean(brandId),
  });

  const recomputeMut = useMutation({
    mutationFn: () => growthCommanderApi.recompute(brandId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['growth-commands', brandId] });
      queryClient.invalidateQueries({ queryKey: ['portfolio-assessment', brandId] });
      queryClient.invalidateQueries({ queryKey: ['growth-command-runs', brandId] });
    },
  });

  const commands = commandsRaw ?? [];
  const balance = portfolioRaw?.balance ?? {};
  const whitespace = portfolioRaw?.whitespace ?? [];

  const platformDist = balance.platform_distribution ?? {};
  const totalPlat = useMemo(() => {
    const vals = Object.values(platformDist);
    return vals.reduce((a, b) => a + b, 0) || 1;
  }, [platformDist]);

  const selectedBrand = useMemo(
    () => brands?.find((b) => String(b.id) === brandId),
    [brands, brandId]
  );

  const tabs: { id: TabId; label: string; short: string; icon: typeof Command }[] = [
    { id: 'commands', label: 'Active Commands', short: 'commands', icon: Command },
    { id: 'portfolio', label: 'Portfolio Balance', short: 'portfolio', icon: BarChart3 },
    { id: 'whitespace', label: 'Whitespace Opportunities', short: 'whitespace', icon: Target },
  ];

  if (brandsLoading) {
    return (
      <div className="min-h-screen bg-gray-900 text-white p-6">
        <div className="h-8 w-96 bg-gray-800 rounded animate-pulse mb-6" />
        <div className="rounded-xl border border-gray-800 bg-gray-900 py-16 text-center text-brand-300">Loading…</div>
      </div>
    );
  }

  if (brandsError) {
    return (
      <div className="min-h-screen bg-gray-900 text-white p-6">
        <div className="rounded-xl border border-red-900/50 text-red-300 py-8 text-center">{errMessage(brandsErr)}</div>
      </div>
    );
  }

  if (!brands?.length) {
    return (
      <div className="min-h-screen bg-gray-900 text-white p-6">
        <div className="rounded-xl border border-gray-800 py-12 text-center text-gray-400">
          Create a brand to use Growth Commander.
        </div>
      </div>
    );
  }

  const dataPending = tab === 'commands' ? commandsLoading : tab === 'portfolio' ? portfolioLoading : portfolioLoading;
  const dataErr = tab === 'commands' ? commandsError : portfolioError;
  const dataErrObj = tab === 'commands' ? commandsErr : portfolioErr;

  return (
    <div className="min-h-screen bg-gray-900 text-white pb-16">
      <div className="border-b border-gray-800 bg-gray-900/95 px-6 py-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between max-w-7xl mx-auto">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Sparkles className="text-brand-300" size={28} aria-hidden />
              Growth Commander
            </h1>
            <p className="text-gray-400 mt-1 max-w-3xl">
              Exact portfolio-expansion commands from scale signals, launch candidates, and portfolio balance.
            </p>
          </div>
          <div className="flex flex-col sm:flex-row gap-3 shrink-0">
            <label className="sr-only" htmlFor="gc-brand-select">
              Brand
            </label>
            <select
              id="gc-brand-select"
              aria-label="Select brand for growth commander"
              className="rounded-lg border border-gray-800 bg-gray-800/80 text-white px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/50 min-w-[200px]"
              value={brandId}
              onChange={(e) => setBrandId(e.target.value)}
            >
              {brands.map((b) => (
                <option key={b.id} value={String(b.id)}>
                  {b.name}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-gray-700 bg-gray-800 px-4 py-2.5 text-sm font-medium text-brand-300 hover:bg-gray-700 disabled:opacity-50"
              disabled={!brandId || recomputeMut.isPending}
              onClick={() => recomputeMut.mutate()}
            >
              <RefreshCw size={16} className={recomputeMut.isPending ? 'animate-spin' : ''} aria-hidden />
              Recompute Growth Commands
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 pt-6">
        {runsRaw && runsRaw.length > 0 && (
          <div className="mb-6 rounded-xl border border-gray-800 bg-gray-900/50 p-4">
            <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-3">
              Recent recomputes
            </h2>
            <ul className="space-y-2 text-sm">
              {runsRaw.slice(0, 5).map((run) => (
                <li
                  key={run.id}
                  className="flex flex-wrap items-baseline justify-between gap-2 border-b border-gray-800/80 pb-2 last:border-0 last:pb-0"
                >
                  <span className="text-gray-400 font-mono text-xs">{run.created_at.slice(0, 19)}</span>
                  <span className="text-gray-300">
                    {run.commands_generated} command{run.commands_generated === 1 ? '' : 's'} ·{' '}
                    {(run.command_types ?? []).slice(0, 4).join(', ')}
                    {(run.command_types?.length ?? 0) > 4 ? '…' : ''}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex flex-wrap gap-2 border-b border-gray-800 pb-3 mb-6">
          {tabs.map((t) => {
            const Icon = t.icon;
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                className={`inline-flex items-center gap-2 rounded-t-lg border px-4 py-2.5 text-sm font-medium transition-colors ${
                  active
                    ? 'border-gray-700 border-b-transparent bg-gray-800 text-brand-300'
                    : 'border-transparent text-gray-400 hover:text-white hover:bg-gray-800/50'
                }`}
              >
                <Icon size={16} aria-hidden />
                {t.label}
              </button>
            );
          })}
        </div>

        {recomputeMut.isError && (
          <div className="mb-4 rounded-lg border border-red-900/50 bg-red-950/30 px-4 py-3 text-sm text-red-300">
            {errMessage(recomputeMut.error)}
          </div>
        )}

        {dataPending && (
          <div className="rounded-xl border border-gray-800 py-20 text-center text-brand-300">
            {tab === 'commands' ? 'Loading commands…' : 'Loading portfolio…'}
          </div>
        )}

        {dataErr && !dataPending && (
          <div className="rounded-xl border border-red-900/50 text-red-300 py-10 text-center">{errMessage(dataErrObj)}</div>
        )}

        {!dataPending && !dataErr && tab === 'commands' && (
          <div className="space-y-6">
            {commands.length === 0 ? (
              <div className="rounded-xl border border-gray-800 py-16 text-center text-gray-500">
                No growth commands yet. Run recompute to generate commands for {selectedBrand?.name ?? 'this brand'}.
              </div>
            ) : (
              commands.map((cmd) => {
                const comp = cmd.comparison;
                const winner = comp?.winner;
                const incNew = comp?.incremental_new ?? 0;
                const incEx = comp?.incremental_existing ?? 0;
                const newWins = winner === 'new_account';
                const exWins = winner === 'more_output';
                const pf = cmd.platform_fit;
                const nf = cmd.niche_fit;
                const can = cmd.cannibalization_analysis;
                const risk = typeof can?.risk === 'number' ? can.risk : 0;
                const overlaps = can?.overlap_accounts ?? [];
                const blockers = cmd.blocking_factors ?? [];
                const week = cmd.first_week_plan ?? [];

                return (
                  <article
                    key={cmd.id}
                    className="rounded-xl border border-gray-800 bg-gray-900/80 p-5 shadow-lg space-y-4"
                  >
                    <div className="flex flex-wrap items-start gap-3 justify-between">
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide ${commandTypeBadgeClass(cmd.command_type)}`}
                        >
                          {cmd.command_type.replace(/_/g, ' ')}
                        </span>
                        <span className="text-xs text-gray-500 tabular-nums">P{cmd.priority}</span>
                      </div>
                      <div className="flex items-center gap-2 text-brand-300">
                        <Shield size={14} aria-hidden />
                        <span className="text-xs">confidence & urgency</span>
                      </div>
                    </div>
                    <h2 className="text-lg font-bold text-white leading-snug">{cmd.title}</h2>
                    <p className="text-sm text-gray-300 whitespace-pre-wrap leading-relaxed">{cmd.exact_instruction}</p>

                    {comp && (
                      <div className="rounded-lg border border-gray-800 bg-gray-800/30 p-4">
                        <div className="text-xs font-semibold uppercase text-brand-300 mb-3 flex items-center gap-2">
                          <TrendingUp size={14} aria-hidden />
                          Comparison
                        </div>
                        <div className="grid sm:grid-cols-2 gap-3">
                          <div
                            className={`rounded-lg p-3 border ${
                              newWins ? 'border-emerald-500/60 bg-emerald-500/10 ring-1 ring-emerald-500/30' : 'border-gray-700 bg-gray-800/40'
                            }`}
                          >
                            <div className="text-xs text-gray-500 mb-1">incremental_new</div>
                            <div className="text-xl font-semibold text-white tabular-nums">${incNew.toLocaleString()}</div>
                          </div>
                          <div
                            className={`rounded-lg p-3 border ${
                              exWins ? 'border-sky-500/60 bg-sky-500/10 ring-1 ring-sky-500/30' : 'border-gray-700 bg-gray-800/40'
                            }`}
                          >
                            <div className="text-xs text-gray-500 mb-1">incremental_existing</div>
                            <div className="text-xl font-semibold text-white tabular-nums">${incEx.toLocaleString()}</div>
                          </div>
                        </div>
                        {winner === 'tie' && (
                          <p className="text-xs text-amber-300/90 mt-2">Winner: tie — evaluate context.</p>
                        )}
                      </div>
                    )}

                    <div className="grid md:grid-cols-2 gap-4">
                      <div className="space-y-3">
                        <div className="text-xs font-semibold text-brand-300 uppercase tracking-wide">Platform fit</div>
                        {pf && (
                          <>
                            <p className="text-xs text-gray-400">
                              {pf.platform} — {pf.reason}
                            </p>
                            <ScoreBar label="Fit score" value={pct01(pf.fit_score)} accent="bg-sky-500" />
                          </>
                        )}
                      </div>
                      <div className="space-y-3">
                        <div className="text-xs font-semibold text-brand-300 uppercase tracking-wide">Niche fit</div>
                        {nf && (
                          <>
                            <p className="text-xs text-gray-400">
                              {(nf.niche || '') + (nf.sub_niche ? ` · ${nf.sub_niche}` : '')} — {nf.reason}
                            </p>
                            <ScoreBar label="Fit score" value={pct01(nf.fit_score)} accent="bg-violet-500" />
                          </>
                        )}
                      </div>
                    </div>

                    <div className="rounded-lg border border-gray-800 p-4 space-y-3">
                      <div className="text-xs font-semibold text-brand-300 uppercase tracking-wide flex items-center gap-2">
                        <Target size={14} aria-hidden />
                        Cannibalization analysis
                      </div>
                      <ScoreBar label="Risk" value={pct01(risk)} accent="bg-amber-500" />
                      {overlaps.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {overlaps.map((o, i) => (
                            <span
                              key={`${o}-${i}`}
                              className="inline-flex rounded-md bg-gray-800 border border-gray-700 px-2 py-0.5 text-xs text-gray-300"
                            >
                              {o}
                            </span>
                          ))}
                        </div>
                      )}
                      <p className="text-sm text-gray-400">{can?.mitigation ?? '—'}</p>
                    </div>

                    <div className="grid md:grid-cols-2 gap-3">
                      <ThresholdCard title="Success threshold" data={cmd.success_threshold as Record<string, unknown>} />
                      <ThresholdCard title="Failure threshold" data={cmd.failure_threshold as Record<string, unknown>} />
                    </div>

                    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
                      <div className="rounded-lg border border-gray-800 bg-gray-800/30 p-3">
                        <div className="text-gray-500 text-xs">Expected upside</div>
                        <div className="text-brand-300 font-semibold tabular-nums">${cmd.expected_upside.toLocaleString()}</div>
                      </div>
                      <div className="rounded-lg border border-gray-800 bg-gray-800/30 p-3">
                        <div className="text-gray-500 text-xs">Cost</div>
                        <div className="text-white font-semibold tabular-nums">${cmd.expected_cost.toLocaleString()}</div>
                      </div>
                      <div className="rounded-lg border border-gray-800 bg-gray-800/30 p-3">
                        <div className="text-gray-500 text-xs">Time to signal</div>
                        <div className="text-white font-semibold tabular-nums">{cmd.expected_time_to_signal_days} d</div>
                      </div>
                      <div className="rounded-lg border border-gray-800 bg-gray-800/30 p-3">
                        <div className="text-gray-500 text-xs">Time to profit</div>
                        <div className="text-white font-semibold tabular-nums">{cmd.expected_time_to_profit_days} d</div>
                      </div>
                    </div>

                    <div className="grid md:grid-cols-2 gap-4">
                      <ScoreBar label="Confidence" value={pct01(cmd.confidence)} accent="bg-emerald-500" />
                      <ScoreBar label="Urgency" value={pct01(cmd.urgency)} accent="bg-orange-500" />
                    </div>

                    {week.length > 0 && (
                      <div className="rounded-lg border border-gray-800 p-4">
                        <div className="text-xs font-semibold text-brand-300 uppercase tracking-wide mb-3">First week plan</div>
                        <ol className="space-y-2">
                          {week.map((d, i) => (
                            <li key={i} className="flex gap-3 text-sm">
                              <span className="shrink-0 font-medium text-gray-500 w-16">{d.day ?? `Day ${i + 1}`}</span>
                              <span className="text-gray-300">{d.action}</span>
                            </li>
                          ))}
                        </ol>
                      </div>
                    )}

                    {blockers.length > 0 && (
                      <div>
                        <div className="text-xs font-semibold text-red-400/90 uppercase tracking-wide mb-2">Blocking factors</div>
                        <div className="flex flex-wrap gap-2">
                          {blockers.map((b, i) => (
                            <span
                              key={`${b}-${i}`}
                              className="inline-flex rounded-full border border-red-900/60 bg-red-950/40 px-3 py-1 text-xs text-red-200"
                            >
                              {b}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {(cmd.execution_spec && Object.keys(cmd.execution_spec).length > 0) ||
                    (cmd.required_resources && Object.keys(cmd.required_resources).length > 0) ? (
                      <div className="grid md:grid-cols-2 gap-3">
                        {cmd.execution_spec && Object.keys(cmd.execution_spec).length > 0 && (
                          <details className="rounded-lg border border-gray-800 bg-gray-800/20 p-3 group">
                            <summary className="cursor-pointer text-sm font-medium text-brand-300 list-none flex items-center gap-2">
                              <span className="group-open:rotate-90 transition-transform">▸</span>
                              Execution spec (platform · niche · role)
                            </summary>
                            <pre className="mt-3 text-xs text-gray-400 overflow-x-auto whitespace-pre-wrap break-words">
                              {JSON.stringify(cmd.execution_spec, null, 2)}
                            </pre>
                          </details>
                        )}
                        {cmd.required_resources && Object.keys(cmd.required_resources).length > 0 && (
                          <details className="rounded-lg border border-gray-800 bg-gray-800/20 p-3 group">
                            <summary className="cursor-pointer text-sm font-medium text-brand-300 list-none flex items-center gap-2">
                              <span className="group-open:rotate-90 transition-transform">▸</span>
                              Required resources
                            </summary>
                            <pre className="mt-3 text-xs text-gray-400 overflow-x-auto whitespace-pre-wrap break-words">
                              {JSON.stringify(cmd.required_resources, null, 2)}
                            </pre>
                          </details>
                        )}
                      </div>
                    ) : null}

                    {cmd.evidence && Object.keys(cmd.evidence).length > 0 && (
                      <details className="rounded-lg border border-gray-800 bg-gray-800/20 p-3 group">
                        <summary className="cursor-pointer text-sm font-medium text-brand-300 list-none flex items-center gap-2">
                          <span className="group-open:rotate-90 transition-transform">▸</span>
                          Supporting evidence
                        </summary>
                        <pre className="mt-3 text-xs text-gray-400 overflow-x-auto whitespace-pre-wrap break-words">
                          {JSON.stringify(cmd.evidence, null, 2)}
                        </pre>
                      </details>
                    )}
                  </article>
                );
              })
            )}
          </div>
        )}

        {!dataPending && !dataErr && tab === 'portfolio' && (
          <div className="space-y-8">
            {portfolioRaw?.latest_portfolio_directive &&
              typeof portfolioRaw.latest_portfolio_directive === 'object' &&
              Object.keys(portfolioRaw.latest_portfolio_directive).length > 0 && (
                <div className="rounded-xl border border-brand-700/40 bg-brand-950/25 p-5 space-y-4">
                  <h3 className="text-sm font-semibold text-brand-300 flex items-center gap-2">
                    <TrendingUp size={16} aria-hidden />
                    Portfolio control directive
                  </h3>
                  <p className="text-sm text-gray-300 leading-relaxed">
                    {String(portfolioRaw.latest_portfolio_directive.explanation ?? '—')}
                  </p>
                  <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
                    <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
                      <div className="text-gray-500 text-xs">Current accounts</div>
                      <div className="text-white font-semibold tabular-nums">
                        {String(portfolioRaw.latest_portfolio_directive.current_account_count ?? '—')}
                      </div>
                    </div>
                    <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
                      <div className="text-gray-500 text-xs">Target count (scale)</div>
                      <div className="text-brand-300 font-semibold tabular-nums">
                        {String(portfolioRaw.latest_portfolio_directive.recommended_account_count ?? '—')}
                      </div>
                    </div>
                    <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
                      <div className="text-gray-500 text-xs">Stance</div>
                      <div className="text-amber-200 font-medium capitalize">
                        {String(portfolioRaw.latest_portfolio_directive.hold_vs_expand ?? '—')}
                      </div>
                    </div>
                    <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
                      <div className="text-gray-500 text-xs">Next command type</div>
                      <div className="text-gray-200 font-mono text-xs">
                        {String(portfolioRaw.latest_portfolio_directive.next_best_command_type ?? '—')}
                      </div>
                    </div>
                  </div>
                  <p className="text-xs text-gray-500">
                    Downstream: {String(portfolioRaw.latest_portfolio_directive.downstream_action ?? '—')}
                  </p>
                  <details className="text-xs text-gray-500">
                    <summary className="cursor-pointer text-brand-400/90">Evidence snapshot</summary>
                    <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words">
                      {JSON.stringify(portfolioRaw.latest_portfolio_directive.evidence ?? {}, null, 2)}
                    </pre>
                  </details>
                </div>
              )}

            <div>
              <h3 className="text-sm font-semibold text-brand-300 mb-4 flex items-center gap-2">
                <BarChart3 size={16} aria-hidden />
                Platform distribution
              </h3>
              {Object.keys(platformDist).length === 0 ? (
                <p className="text-gray-500 text-sm">No account data for distribution.</p>
              ) : (
                <div className="space-y-3 max-w-xl">
                  {Object.entries(platformDist)
                    .sort((a, b) => b[1] - a[1])
                    .map(([plat, count]) => {
                      const pct = (count / totalPlat) * 100;
                      return (
                        <div key={plat}>
                          <div className="flex justify-between text-xs text-gray-400 mb-1">
                            <span className="capitalize">{plat}</span>
                            <span className="text-brand-300 tabular-nums">
                              {count} ({pct.toFixed(0)}%)
                            </span>
                          </div>
                          <div className="h-3 rounded-full bg-gray-800 overflow-hidden">
                            <div className="h-full rounded-full bg-brand-600/70" style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                      );
                    })}
                </div>
              )}
            </div>

            {(balance.overbuilt?.length ?? 0) > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-amber-300 mb-3">Overbuilt</h3>
                <ul className="space-y-2">
                  {balance.overbuilt!.map((o) => (
                    <li
                      key={o.platform}
                      className="rounded-lg border border-amber-900/40 bg-amber-950/20 px-4 py-3 text-sm text-gray-300"
                    >
                      <span className="font-medium text-amber-200 capitalize">{o.platform}</span>
                      <span className="text-gray-500"> — {o.count} accounts, share {o.share}</span>
                      <p className="text-xs text-gray-500 mt-1">{o.reason}</p>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {(balance.underbuilt?.length ?? 0) > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-sky-300 mb-3">Underbuilt</h3>
                <ul className="space-y-2">
                  {balance.underbuilt!.map((u) => (
                    <li
                      key={u.platform}
                      className="rounded-lg border border-sky-900/40 bg-sky-950/20 px-4 py-3 text-sm text-gray-300"
                    >
                      <span className="font-medium text-sky-200 capitalize">{u.platform}</span>
                      <span className="text-gray-500"> — {u.count} account(s)</span>
                      <p className="text-xs text-gray-500 mt-1">{u.reason}</p>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {(balance.absent_platforms?.length ?? 0) > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-gray-400 mb-3">Absent platforms</h3>
                <div className="flex flex-wrap gap-2">
                  {balance.absent_platforms!.map((p) => (
                    <span
                      key={p}
                      className="inline-flex rounded-md border border-gray-700 bg-gray-800/60 px-3 py-1.5 text-xs text-gray-400 capitalize"
                    >
                      {p}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {!dataPending && !dataErr && tab === 'whitespace' && (
          <div>
            {whitespace.length === 0 ? (
              <div className="rounded-xl border border-gray-800 py-16 text-center text-gray-500">
                No whitespace opportunities identified for this portfolio.
              </div>
            ) : (
              <ul className="space-y-3">
                {whitespace.map((w, i) => (
                  <li
                    key={`${w.platform}-${w.geography}-${i}`}
                    className="rounded-xl border border-gray-800 bg-gray-900/80 p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
                  >
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold text-white capitalize">{w.platform}</span>
                        <span className="text-gray-600">·</span>
                        <span className="text-brand-300 text-sm">{w.niche}</span>
                        <span className="text-gray-600">·</span>
                        <span className="text-gray-400 text-sm">{w.geography}</span>
                        {w.language && (
                          <>
                            <span className="text-gray-600">·</span>
                            <span className="text-gray-500 text-sm">{w.language}</span>
                          </>
                        )}
                      </div>
                      <p className="text-sm text-gray-400">{w.reason}</p>
                    </div>
                    <div className="shrink-0 text-right">
                      <div className="text-xs text-gray-500 uppercase tracking-wide">Opportunity score</div>
                      <div className="text-xl font-bold text-brand-300 tabular-nums">
                        {typeof w.estimated_opportunity_score === 'number'
                          ? w.estimated_opportunity_score.toFixed(1)
                          : '—'}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
