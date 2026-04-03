'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { phase7Api } from '@/lib/phase7-api';
import {
  Activity,
  AlertTriangle,
  DollarSign,
  Handshake,
  Map,
  MessageSquareDot,
  PiggyBank,
  RefreshCw,
  Shield,
  Target,
  TrendingUp,
  Globe2,
} from 'lucide-react';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

export default function OperatorCockpitPage() {
  const queryClient = useQueryClient();
  const [selectedBrandId, setSelectedBrandId] = useState('');

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) {
      setSelectedBrandId(String(brands[0].id));
    }
  }, [brands, selectedBrandId]);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['operator-cockpit', selectedBrandId],
    queryFn: () => phase7Api.operatorCockpit(selectedBrandId).then((r) => r.data),
    enabled: Boolean(selectedBrandId),
  });

  const recomputeMut = useMutation({
    mutationFn: () => phase7Api.recompute(selectedBrandId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['operator-cockpit', selectedBrandId] });
    },
  });

  const selectedBrand = useMemo(
    () => brands?.find((b) => String(b.id) === selectedBrandId),
    [brands, selectedBrandId]
  );

  const roadmapItems = (data?.top_roadmap_items || data?.roadmap || []) as any[];
  const capitalSummary = (data?.capital_allocation_summary || data?.capital || []) as any[];
  const openLeaks = (data?.open_leaks || []) as any[];
  const scaleActions = (data?.scale_actions || data?.scale_action || []) as any[];
  const growthBlockers = (data?.growth_blockers || []) as any[];
  const trustAvg = data?.trust_average ?? data?.trust_avg ?? null;
  const sponsorPackages = (data?.sponsor_packages || []) as any[];
  const commentCashSignals = (data?.comment_cash_signals || []) as any[];
  const expansionTargets = (data?.expansion_targets || []) as any[];

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
    return <div className="card text-center py-12 text-gray-500">Create a brand to open the Operator Cockpit.</div>;
  }

  return (
    <div className="space-y-8 pb-16">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Activity className="text-brand-500" size={28} aria-hidden />
            Operator Cockpit
          </h1>
          <p className="text-gray-400 mt-1 max-w-3xl">
            Phase 7 unified command center — complete operational view across all intelligence engines.
          </p>
        </div>
        <button
          type="button"
          className="btn-primary flex items-center gap-2 disabled:opacity-50 shrink-0"
          disabled={!selectedBrandId || recomputeMut.isPending}
          onClick={() => recomputeMut.mutate()}
        >
          <RefreshCw size={16} className={recomputeMut.isPending ? 'animate-spin' : ''} />
          Recompute All Intelligence
        </button>
      </div>

      {recomputeMut.isError && (
        <div className="card border-amber-900/50 text-amber-200 text-sm">{errMessage(recomputeMut.error)}</div>
      )}
      {recomputeMut.isSuccess && (
        <div className="card border-emerald-900/50 text-emerald-300 text-sm">
          Recompute complete — all intelligence data refreshed.
        </div>
      )}

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          value={selectedBrandId}
          onChange={(e) => setSelectedBrandId(e.target.value)}
          aria-label="Select brand for operator cockpit"
        >
          {brands.map((b) => (
            <option key={b.id} value={String(b.id)}>
              {b.name}
            </option>
          ))}
        </select>
        {selectedBrand && <p className="text-sm text-gray-500 mt-2">Viewing: {selectedBrand.name}</p>}
      </div>

      {isLoading && <div className="card py-12 text-center text-gray-500">Loading cockpit data…</div>}
      {isError && <div className="card border-red-900/50 text-red-300 py-6">{errMessage(error)}</div>}

      {data && !isLoading && (
        <>
          {/* Revenue & Fleet Status */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-lg bg-gradient-to-br from-emerald-900/30 to-gray-900 p-4 border border-emerald-800/30">
              <p className="text-gray-400 text-xs uppercase flex items-center gap-1">
                <DollarSign size={12} aria-hidden /> Monthly Revenue (MTD)
              </p>
              <p className="text-3xl font-bold text-emerald-300 mt-1">
                ${(data?.revenue?.mtd_revenue ?? data?.revenue?.month_revenue ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
              {data?.revenue?.revenue_forecast?.summary && (
                <p className="text-xs text-gray-500 mt-2">{data.revenue.revenue_forecast.summary}</p>
              )}
            </div>
            <div className="rounded-lg bg-gray-800/40 p-4 border border-gray-800">
              <p className="text-gray-400 text-xs uppercase flex items-center gap-1">
                <TrendingUp size={12} aria-hidden /> Today Revenue
              </p>
              <p className="text-3xl font-bold text-emerald-300 mt-1">
                ${(data?.revenue?.today_revenue ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </p>
            </div>
            <div className="rounded-lg bg-gray-800/40 p-4 border border-gray-800">
              <p className="text-gray-400 text-xs uppercase flex items-center gap-1">
                <Activity size={12} aria-hidden /> Fleet Accounts
              </p>
              <p className="text-3xl font-bold text-blue-300 mt-1">{data?.revenue?.fleet_status?.total ?? 0}</p>
              <p className="text-xs text-gray-500 mt-1">
                {data?.revenue?.fleet_status?.scaling ?? 0} scaling · {data?.revenue?.fleet_status?.warming ?? 0} warming
              </p>
            </div>
            <div className="rounded-lg bg-gray-800/40 p-4 border border-gray-800">
              <p className="text-gray-400 text-xs uppercase flex items-center gap-1">
                <PiggyBank size={12} aria-hidden /> Lifetime Revenue
              </p>
              <p className="text-3xl font-bold text-white mt-1">
                ${(data?.revenue?.lifetime_revenue ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </p>
            </div>
          </div>

          {data?.revenue?.fleet_status?.expansion_recommended && (
            <div className="card border-blue-900/40 bg-blue-900/10 text-blue-200 text-sm flex items-center gap-2">
              <Globe2 size={16} aria-hidden />
              <span className="font-medium">Expansion Recommended:</span> The system recommends adding new accounts based on fleet performance.
            </div>
          )}

          {trustAvg != null && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-lg bg-gray-800/40 p-4 border border-gray-800">
                <p className="text-gray-500 text-xs uppercase flex items-center gap-1">
                  <Shield size={12} aria-hidden /> Trust Average
                </p>
                <p className="text-3xl font-bold text-emerald-300 mt-1">{Number(trustAvg).toFixed(1)}</p>
              </div>
              <div className="rounded-lg bg-gray-800/40 p-4 border border-gray-800">
                <p className="text-gray-500 text-xs uppercase">Open Leaks</p>
                <p className="text-3xl font-bold text-amber-300 mt-1">{openLeaks.length}</p>
              </div>
              <div className="rounded-lg bg-gray-800/40 p-4 border border-gray-800">
                <p className="text-gray-500 text-xs uppercase">Roadmap Items</p>
                <p className="text-3xl font-bold text-white mt-1">{roadmapItems.length}</p>
              </div>
              <div className="rounded-lg bg-gray-800/40 p-4 border border-gray-800">
                <p className="text-gray-500 text-xs uppercase">Sponsor Packages</p>
                <p className="text-3xl font-bold text-white mt-1">{sponsorPackages.length}</p>
              </div>
            </div>
          )}

          {roadmapItems.length > 0 && (
            <div className="card">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Map size={18} className="text-brand-400" aria-hidden />
                Top Roadmap Items
              </h2>
              <ul className="space-y-2">
                {roadmapItems.slice(0, 8).map((item: any, i: number) => (
                  <li key={item.id || i} className="flex items-start justify-between gap-4 border-b border-gray-800 py-2 last:border-0">
                    <div className="flex items-start gap-3">
                      <span className="text-xs text-gray-500 mt-0.5 shrink-0">#{i + 1}</span>
                      <div>
                        <p className="text-white text-sm font-medium">{item.title || '—'}</p>
                        {item.description && <p className="text-xs text-gray-400 mt-0.5">{item.description}</p>}
                      </div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0 text-xs">
                      {item.category && (
                        <span className="px-2 py-0.5 rounded bg-brand-600/25 text-brand-300 uppercase tracking-wide">
                          {item.category}
                        </span>
                      )}
                      {item.priority_score != null && (
                        <span className="text-gray-400">P:{Number(item.priority_score).toFixed(1)}</span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {capitalSummary.length > 0 && (
            <div className="card">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <PiggyBank size={18} className="text-emerald-400" aria-hidden />
                Capital Allocation Summary
              </h2>
              <div className="space-y-3">
                {capitalSummary.map((a: any, i: number) => {
                  const pct = Number(a.percentage ?? a.allocation_pct ?? 0);
                  return (
                    <div key={a.id || i} className="flex items-center gap-4">
                      <span className="text-sm text-white w-32 shrink-0 truncate">{a.target || a.category || a.channel || '—'}</span>
                      <div className="flex-1 bg-gray-800 rounded-full h-2">
                        <div className="bg-brand-500 h-2 rounded-full transition-all" style={{ width: `${Math.min(pct, 100)}%` }} />
                      </div>
                      <span className="text-xs text-gray-400 w-12 text-right">{pct.toFixed(0)}%</span>
                      <span className="text-xs text-emerald-300 w-20 text-right">${Number(a.amount ?? a.dollar_amount ?? 0).toLocaleString()}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {openLeaks.length > 0 && (
            <div className="card">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <AlertTriangle size={18} className="text-amber-400" aria-hidden />
                Open Leaks
              </h2>
              <ul className="space-y-2">
                {openLeaks.map((leak: any, i: number) => (
                  <li key={leak.id || i} className="rounded-lg border border-amber-900/30 bg-amber-950/10 p-3 text-sm">
                    <div className="flex justify-between gap-4">
                      <span className="text-amber-200 font-medium">{leak.leak_type || leak.type || '—'}</span>
                      <span className="text-gray-500">{leak.severity || ''}</span>
                    </div>
                    {leak.root_cause && <p className="text-gray-400 mt-1">{leak.root_cause}</p>}
                    {leak.estimated_leaked_revenue != null && (
                      <p className="text-xs text-gray-500 mt-1">
                        Est. leak: ${Number(leak.estimated_leaked_revenue).toFixed(2)}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {(Array.isArray(scaleActions) ? scaleActions : [scaleActions]).filter(Boolean).length > 0 && (
            <div className="card">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <TrendingUp size={18} className="text-brand-400" aria-hidden />
                Scale Actions
              </h2>
              <ul className="space-y-2">
                {(Array.isArray(scaleActions) ? scaleActions : [scaleActions]).filter(Boolean).map((action: any, i: number) => (
                  <li key={action.id || i} className="rounded-lg border border-gray-800 p-3 text-sm">
                    <p className="text-white font-medium">{action.title || action.action || JSON.stringify(action)}</p>
                    {action.description && <p className="text-gray-400 mt-1 text-xs">{action.description}</p>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {growthBlockers.length > 0 && (
            <div className="card">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <AlertTriangle size={18} className="text-red-400" aria-hidden />
                Growth Blockers
              </h2>
              <ul className="space-y-2">
                {growthBlockers.map((b: any, i: number) => (
                  <li key={b.id || i} className="rounded-lg border border-red-900/30 bg-red-950/10 p-3 text-sm">
                    <p className="text-red-200 font-medium">{b.blocker || b.title || b.description || '—'}</p>
                    {b.impact && <p className="text-gray-400 mt-1 text-xs">Impact: {b.impact}</p>}
                    {b.recommended_action && <p className="text-xs text-brand-300 mt-1">Action: {b.recommended_action}</p>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {sponsorPackages.length > 0 && (
            <div className="card">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Handshake size={18} className="text-amber-400" aria-hidden />
                Sponsor Packages
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead>
                    <tr className="text-gray-500 text-xs border-b border-gray-800">
                      <th className="py-2 pr-4">Package</th>
                      <th className="py-2 pr-4">Rate</th>
                      <th className="py-2">Priority</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800 text-gray-300">
                    {sponsorPackages.map((p: any, i: number) => (
                      <tr key={p.id || i}>
                        <td className="py-2 pr-4 text-white">{p.package_name || p.name || '—'}</td>
                        <td className="py-2 pr-4 text-emerald-300">${Number(p.suggested_rate || 0).toLocaleString()}</td>
                        <td className="py-2">{p.priority || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {commentCashSignals.length > 0 && (
            <div className="card">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <MessageSquareDot size={18} className="text-brand-400" aria-hidden />
                Comment-to-Cash Signals
              </h2>
              <ul className="space-y-2">
                {commentCashSignals.slice(0, 6).map((s: any, i: number) => (
                  <li key={s.id || i} className="flex items-center justify-between gap-4 border-b border-gray-800 py-2 last:border-0 text-sm">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded text-xs bg-brand-600/25 text-brand-300 uppercase">
                        {s.signal_type || s.type || 'signal'}
                      </span>
                      <span className="text-white">{s.suggested_content_angle || s.content_angle || '—'}</span>
                    </div>
                    {s.revenue_potential != null && (
                      <span className="text-emerald-300 text-xs shrink-0">${Number(s.revenue_potential).toLocaleString()}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {expansionTargets.length > 0 && (
            <div className="card">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Globe2 size={18} className="text-cyan-400" aria-hidden />
                Expansion Targets
              </h2>
              <ul className="space-y-2">
                {expansionTargets.map((t: any, i: number) => (
                  <li key={t.id || i} className="rounded-lg border border-gray-800 bg-gray-900/40 p-3 text-sm">
                    <div className="flex justify-between items-start gap-4">
                      <div>
                        <p className="text-white font-medium">
                          {t.target_geography || t.geography || t.market || '—'}
                          {(t.target_language || t.language) && ` · ${t.target_language || t.language}`}
                          {(t.target_platform || t.platform) && ` · ${t.target_platform || t.platform}`}
                        </p>
                        {t.rationale && <p className="text-gray-400 mt-1 text-xs">{t.rationale}</p>}
                      </div>
                      {t.estimated_revenue_potential != null && (
                        <span className="text-emerald-300 text-xs shrink-0">
                          ${Number(t.estimated_revenue_potential).toLocaleString()} potential
                        </span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {!roadmapItems.length && !capitalSummary.length && !openLeaks.length && !sponsorPackages.length && !commentCashSignals.length && (
            <div className="card text-center py-12">
              <Target size={48} className="mx-auto text-gray-600 mb-4" aria-hidden />
              <p className="text-gray-400">No cockpit data yet. Click &ldquo;Recompute All Intelligence&rdquo; to populate.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
