'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { GrowthIntelDashboard, growthApi } from '@/lib/growth-api';
import {
  DollarSign,
  Globe2,
  LayoutGrid,
  LineChart,
  Megaphone,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  SplitSquareHorizontal,
  Wallet,
} from 'lucide-react';

type Brand = { id: string; name: string };

type TabId = 'overview' | 'segments' | 'ltv' | 'leaks' | 'expansion' | 'paid' | 'trust' | 'flow';

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

export default function GrowthIntelPage() {
  const queryClient = useQueryClient();
  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [tab, setTab] = useState<TabId>('overview');

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) {
      setSelectedBrandId(String(brands[0].id));
    }
  }, [brands, selectedBrandId]);

  const { data: intel, isLoading, isError, error } = useQuery({
    queryKey: ['growth-intel', selectedBrandId],
    queryFn: () => growthApi.growthIntel(selectedBrandId).then((r) => r.data),
    enabled: Boolean(selectedBrandId),
  });

  const recomputeMut = useMutation({
    mutationFn: () => growthApi.recompute(selectedBrandId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['growth-intel', selectedBrandId] });
    },
  });

  const g = intel as GrowthIntelDashboard | undefined;
  const funnel = (g?.leaks?.funnel || {}) as Record<string, unknown>;
  const funnelStages = (funnel.funnel_stages || {}) as Record<string, { count?: number }>;

  const selectedBrand = useMemo(
    () => brands?.find((b) => String(b.id) === selectedBrandId),
    [brands, selectedBrandId]
  );

  const tabs: { id: TabId; label: string; icon: typeof LayoutGrid }[] = [
    { id: 'overview', label: 'Funnel & summary', icon: LineChart },
    { id: 'segments', label: 'Segments', icon: LayoutGrid },
    { id: 'ltv', label: 'LTV', icon: DollarSign },
    { id: 'leaks', label: 'Revenue leaks', icon: Wallet },
    { id: 'expansion', label: 'Geo / language', icon: Globe2 },
    { id: 'flow', label: 'Cross-platform flow', icon: SplitSquareHorizontal },
    { id: 'paid', label: 'Paid amplification', icon: Megaphone },
    { id: 'trust', label: 'Trust & authority', icon: ShieldCheck },
  ];

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
    return (
      <div className="card text-center py-12 text-gray-500">Create a brand to open Growth Intelligence.</div>
    );
  }

  return (
    <div className="space-y-8 pb-16">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Sparkles className="text-brand-500" size={28} aria-hidden />
            Growth Intelligence
          </h1>
          <p className="text-gray-400 mt-1 max-w-3xl">
            Phase 6 rules engines: audience clustering, LTV heuristics, leak detection, expansion, winner-only paid
            candidates, trust scoring, and cross-platform derivative planning.
          </p>
        </div>
        <button
          type="button"
          className="btn-primary flex items-center gap-2 disabled:opacity-50 shrink-0"
          disabled={!selectedBrandId || recomputeMut.isPending}
          onClick={() => recomputeMut.mutate()}
        >
          <RefreshCw size={16} className={recomputeMut.isPending ? 'animate-spin' : ''} />
          Recompute growth intel
        </button>
      </div>

      {recomputeMut.isError && (
        <div className="card border-amber-900/50 text-amber-200 text-sm">{errMessage(recomputeMut.error)}</div>
      )}
      {recomputeMut.isSuccess && (
        <div className="card border-emerald-900/50 text-emerald-300 text-sm">Recompute complete — data refreshed.</div>
      )}

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          value={selectedBrandId}
          onChange={(e) => setSelectedBrandId(e.target.value)}
          aria-label="Select brand for growth intelligence"
        >
          {brands.map((b) => (
            <option key={b.id} value={String(b.id)}>
              {b.name}
            </option>
          ))}
        </select>
        {selectedBrand && <p className="text-sm text-gray-500 mt-2">Viewing: {selectedBrand.name}</p>}
      </div>

      <div className="flex flex-wrap gap-2 border-b border-gray-800 pb-2">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
              tab === t.id
                ? 'bg-brand-600/25 text-brand-300 border border-brand-600/40'
                : 'text-gray-400 hover:bg-gray-800'
            }`}
          >
            <t.icon size={16} />
            {t.label}
          </button>
        ))}
      </div>

      {isLoading && <div className="card py-12 text-center text-gray-500">Computing growth intel…</div>}
      {isError && <div className="card border-red-900/50 text-red-300 py-6">{errMessage(error)}</div>}

      {g && !isLoading && (
        <>
          {tab === 'overview' && (
            <div className="grid gap-6 lg:grid-cols-2">
              <div className="card lg:col-span-2">
                <h2 className="text-lg font-semibold text-white mb-3">Funnel performance</h2>
                <div className="grid sm:grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div className="rounded-lg bg-gray-800/40 p-4 border border-gray-800">
                    <p className="text-gray-500 text-xs uppercase">Impressions</p>
                    <p className="text-xl text-white mt-1">{String(funnel.impressions ?? '—')}</p>
                  </div>
                  <div className="rounded-lg bg-gray-800/40 p-4 border border-gray-800">
                    <p className="text-gray-500 text-xs uppercase">Clicks</p>
                    <p className="text-xl text-white mt-1">{String(funnel.total_clicks ?? '—')}</p>
                  </div>
                  <div className="rounded-lg bg-gray-800/40 p-4 border border-gray-800">
                    <p className="text-gray-500 text-xs uppercase">Revenue (attrib.)</p>
                    <p className="text-xl text-emerald-300 mt-1">
                      ${Number(funnel.revenue ?? 0).toLocaleString()}
                    </p>
                  </div>
                  <div className="rounded-lg bg-gray-800/40 p-4 border border-gray-800">
                    <p className="text-gray-500 text-xs uppercase">Open leaks</p>
                    <p className="text-xl text-amber-300 mt-1">{String(g.leaks.summary?.open_leaks ?? 0)}</p>
                  </div>
                </div>
                {Object.keys(funnelStages).length > 0 && (
                  <div className="mt-6">
                    <p className="text-xs text-gray-500 uppercase mb-2">Stages</p>
                    <ul className="space-y-1 text-sm text-gray-300">
                      {Object.entries(funnelStages).map(([k, v]) => (
                        <li key={k} className="flex justify-between border-b border-gray-800 py-1">
                          <span>{k}</span>
                          <span>{v.count ?? 0}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
              <div className="card">
                <h3 className="text-white font-medium mb-2">Snapshot</h3>
                <ul className="text-sm text-gray-400 space-y-1">
                  <li>Audience segments: {g.audience_segments.length}</li>
                  <li>LTV model rows: {g.ltv_models.length}</li>
                  <li>Geo/lang recs: {g.expansion.geo_language_recommendations.length}</li>
                  <li>Cross-platform plans: {g.expansion.cross_platform_flow_plans.length}</li>
                  <li>Paid jobs (incl. candidates): {g.paid_amplification.jobs.length}</li>
                  <li>Trust reports: {g.trust_signals.reports.length}</li>
                </ul>
              </div>
              <div className="card">
                <h3 className="text-white font-medium mb-2">Leak est.</h3>
                <p className="text-3xl font-bold text-amber-200">
                  ${Number(g.leaks.summary?.total_leaked_est ?? 0).toLocaleString()}
                </p>
                <p className="text-xs text-gray-500 mt-2">Heuristic rolled-up leak $ from rules engine.</p>
              </div>
            </div>
          )}

          {tab === 'segments' && (
            <div className="card overflow-x-auto">
              <h2 className="text-lg font-semibold text-white mb-4">Audience segments (rules clusters)</h2>
              <table className="w-full text-sm text-left">
                <thead>
                  <tr className="text-gray-500 text-xs border-b border-gray-800">
                    <th className="py-2 pr-4">Name</th>
                    <th className="py-2 pr-4">Est. size</th>
                    <th className="py-2 pr-4">Revenue</th>
                    <th className="py-2">Criteria</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800 text-gray-300">
                  {g.audience_segments.map((s) => (
                    <tr key={s.id}>
                      <td className="py-2 pr-4 text-white">{s.name}</td>
                      <td className="py-2 pr-4">{s.estimated_size}</td>
                      <td className="py-2 pr-4">${s.revenue_contribution.toFixed(2)}</td>
                      <td className="py-2 font-mono text-xs max-w-md truncate">
                        {JSON.stringify(s.segment_criteria)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!g.audience_segments.length && (
                <p className="text-gray-500 text-sm">No active accounts — add accounts to build clusters.</p>
              )}
            </div>
          )}

          {tab === 'ltv' && (
            <div className="card overflow-x-auto">
              <h2 className="text-lg font-semibold text-white mb-4">LTV estimates (rules)</h2>
              <table className="w-full text-sm text-left">
                <thead>
                  <tr className="text-gray-500 text-xs border-b border-gray-800">
                    <th className="py-2 pr-4">Segment key</th>
                    <th className="py-2 pr-4">30d</th>
                    <th className="py-2 pr-4">90d</th>
                    <th className="py-2 pr-4">365d</th>
                    <th className="py-2">Confidence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800 text-gray-300">
                  {g.ltv_models.map((m) => (
                    <tr key={m.id}>
                      <td className="py-2 pr-4 text-white max-w-xs truncate">{m.segment_name}</td>
                      <td className="py-2 pr-4">${m.estimated_ltv_30d.toFixed(2)}</td>
                      <td className="py-2 pr-4">${m.estimated_ltv_90d.toFixed(2)}</td>
                      <td className="py-2 pr-4">${m.estimated_ltv_365d.toFixed(2)}</td>
                      <td className="py-2">{(m.confidence * 100).toFixed(0)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!g.ltv_models.length && (
                <p className="text-gray-500 text-sm">Add offers to generate LTV rows per platform slice.</p>
              )}
            </div>
          )}

          {tab === 'leaks' && (
            <div className="card space-y-4">
              <h2 className="text-lg font-semibold text-white">Revenue leak detector</h2>
              <ul className="space-y-3 max-h-[520px] overflow-y-auto">
                {g.leaks.leaks.map((L) => (
                  <li key={L.id} className="rounded-lg border border-amber-900/30 bg-amber-950/10 p-4 text-sm">
                    <div className="flex justify-between gap-4">
                      <span className="text-amber-200 font-medium">{L.leak_type}</span>
                      <span className="text-gray-500">{L.severity}</span>
                    </div>
                    <p className="text-gray-400 mt-1">{L.root_cause}</p>
                    <p className="text-xs text-gray-500 mt-2">
                      Est. leak ${L.estimated_leaked_revenue.toFixed(2)} · recoverable $
                      {L.estimated_recoverable.toFixed(2)}
                    </p>
                    {L.recommended_fix && (
                      <p className="text-xs text-brand-300 mt-2">Fix: {L.recommended_fix}</p>
                    )}
                  </li>
                ))}
              </ul>
              {!g.leaks.leaks.length && (
                <p className="text-gray-500 text-sm">No open leaks matched rules for this brand.</p>
              )}
            </div>
          )}

          {tab === 'expansion' && (
            <div className="card space-y-4">
              <h2 className="text-lg font-semibold text-white">Geo & language expansion</h2>
              <ul className="space-y-3">
                {g.expansion.geo_language_recommendations.map((r) => (
                  <li key={r.id} className="rounded-lg border border-gray-800 bg-gray-900/40 p-4 text-sm">
                    <p className="text-white font-medium">
                      {r.target_geography} · {r.target_language} · {r.target_platform || '—'}
                    </p>
                    <p className="text-gray-400 mt-1">{r.rationale}</p>
                    <p className="text-xs text-gray-500 mt-2">
                      Rev pot. ${r.estimated_revenue_potential.toFixed(0)} · entry ~$
                      {r.entry_cost_estimate.toFixed(0)}
                    </p>
                  </li>
                ))}
              </ul>
              {!g.expansion.geo_language_recommendations.length && (
                <p className="text-gray-500 text-sm">No expansion rows — rules may already cover diversity.</p>
              )}
            </div>
          )}

          {tab === 'flow' && (
            <div className="card space-y-4">
              <h2 className="text-lg font-semibold text-white">Cross-platform flow (winners)</h2>
              <ul className="space-y-2 max-h-[560px] overflow-y-auto text-sm">
                {g.expansion.cross_platform_flow_plans.map((p, i) => (
                  <li key={i} className="flex flex-wrap justify-between gap-2 border-b border-gray-800 py-2 text-gray-300">
                    <span className="text-white">{String(p.title || '')}</span>
                    <span className="text-brand-300">
                      {String(p.source_platform)} → {String(p.target_platform)}
                    </span>
                    <span className="text-gray-500 text-xs">prio {String(p.priority)}</span>
                  </li>
                ))}
              </ul>
              {!g.expansion.cross_platform_flow_plans.length && (
                <p className="text-gray-500 text-sm">
                  No derivative plans yet — need winning content across rollups (Phase 6 winner gate).
                </p>
              )}
            </div>
          )}

          {tab === 'paid' && (
            <div className="card space-y-4">
              <h2 className="text-lg font-semibold text-white">Paid amplification</h2>
              <p className="text-sm text-gray-500">{g.paid_amplification.note}</p>
              <ul className="space-y-2">
                {g.paid_amplification.jobs.map((j) => (
                  <li
                    key={j.id}
                    className={`rounded-lg border p-3 text-sm ${j.is_candidate ? 'border-brand-600/40 bg-brand-950/20' : 'border-gray-800'}`}
                  >
                    <div className="flex justify-between">
                      <span className="text-gray-300">
                        {j.platform} · budget ${j.budget.toFixed(0)}
                      </span>
                      {j.is_candidate && <span className="badge-yellow text-[10px]">candidate</span>}
                    </div>
                    <p className="text-xs text-gray-500 mt-1 font-mono">{j.content_item_id}</p>
                    {j.explanation && <p className="text-xs text-gray-400 mt-2">{j.explanation}</p>}
                  </li>
                ))}
              </ul>
              {!g.paid_amplification.jobs.length && <p className="text-gray-500 text-sm">No paid jobs stored.</p>}
            </div>
          )}

          {tab === 'trust' && (
            <div className="card space-y-4">
              <h2 className="text-lg font-semibold text-white">Trust & authority</h2>
              <ul className="space-y-3">
                {g.trust_signals.reports.map((t) => (
                  <li key={t.id} className="rounded-lg border border-gray-800 p-4 text-sm">
                    <div className="flex justify-between items-center">
                      <span className="text-2xl font-bold text-emerald-300">{t.trust_score}</span>
                      <span className="text-xs text-gray-500">{t.confidence_label}</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-2 font-mono">{t.creator_account_id}</p>
                    <ul className="mt-2 text-xs text-gray-400 list-disc pl-4">
                      {t.recommendations.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
              {!g.trust_signals.reports.length && (
                <p className="text-gray-500 text-sm">No accounts for trust scoring.</p>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
