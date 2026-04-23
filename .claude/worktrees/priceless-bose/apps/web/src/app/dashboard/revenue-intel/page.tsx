'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { revenueIntelApi } from '@/lib/revenue-api';
import { BarChart3, Layers, Package, RefreshCw, Sparkles, TrendingUp, Users } from 'lucide-react';

type Brand = { id: string; name: string };

type MonetizationRecRow = {
  id: string;
  content_item_id?: string | null;
  recommendation_type: string;
  title: string;
  description?: string | null;
  expected_revenue_uplift: number;
  expected_cost: number;
  confidence: number;
  evidence?: Record<string, unknown> | null;
  is_actioned: boolean;
};

type RevenueIntelDashboard = {
  brand_id: string;
  offer_stacks: MonetizationRecRow[];
  funnel_paths: MonetizationRecRow[];
  owned_audience: MonetizationRecRow[];
  productization: MonetizationRecRow[];
  density_improvements: MonetizationRecRow[];
};

type TabId = 'stacks' | 'funnels' | 'owned' | 'products' | 'density';

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

function evidenceSummary(ev: Record<string, unknown> | null | undefined): string {
  if (!ev || typeof ev !== 'object') return '—';
  const parts: string[] = [];
  for (const [k, v] of Object.entries(ev)) {
    if (v === null || v === undefined) continue;
    if (typeof v === 'object') {
      parts.push(`${k}: ${JSON.stringify(v)}`);
    } else {
      parts.push(`${k}: ${String(v)}`);
    }
  }
  const s = parts.length ? parts.join(' · ') : '—';
  return s.length > 280 ? `${s.slice(0, 277)}…` : s;
}

function aovUpliftPct(description: string | null | undefined): string {
  if (!description) return '—';
  const m = description.match(/AOV uplift\s+([\d.]+)%/i);
  return m ? `${m[1]}%` : '—';
}

function densityLayersFromTitle(title: string): string[] {
  const prefix = 'Add layers:';
  if (!title.toLowerCase().startsWith(prefix.toLowerCase())) return [];
  return title
    .slice(title.indexOf(':') + 1)
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

export default function RevenueIntelPage() {
  const queryClient = useQueryClient();
  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [tab, setTab] = useState<TabId>('stacks');

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) {
      setSelectedBrandId(String(brands[0].id));
    }
  }, [brands, selectedBrandId]);

  const {
    data: dashboard,
    isLoading: dashLoading,
    isError: dashError,
    error: dashErr,
  } = useQuery({
    queryKey: ['revenue-intel', selectedBrandId],
    queryFn: () => revenueIntelApi.dashboard(selectedBrandId).then((r) => r.data as RevenueIntelDashboard),
    enabled: Boolean(selectedBrandId),
  });

  const recomputeMut = useMutation({
    mutationFn: (brandId: string) => revenueIntelApi.recompute(brandId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['revenue-intel', selectedBrandId] });
    },
  });

  const selectedBrand = useMemo(
    () => brands?.find((b) => String(b.id) === selectedBrandId),
    [brands, selectedBrandId]
  );

  const tabs: { id: TabId; label: string; icon: typeof Layers }[] = [
    { id: 'stacks', label: 'Offer Stacks', icon: Layers },
    { id: 'funnels', label: 'Funnel Paths', icon: TrendingUp },
    { id: 'owned', label: 'Owned Audience', icon: Users },
    { id: 'products', label: 'Productization', icon: Package },
    { id: 'density', label: 'Monetization Density', icon: BarChart3 },
  ];

  const rowsForTab = (): MonetizationRecRow[] => {
    const d = dashboard;
    if (!d) return [];
    switch (tab) {
      case 'stacks':
        return d.offer_stacks;
      case 'funnels':
        return d.funnel_paths;
      case 'owned':
        return d.owned_audience;
      case 'products':
        return d.productization;
      case 'density':
        return d.density_improvements;
      default:
        return [];
    }
  };

  if (brandsLoading) {
    return (
      <div className="space-y-6 bg-gray-900 text-white min-h-[50vh]">
        <div className="h-8 w-72 bg-gray-800 rounded animate-pulse" />
        <div className="h-10 w-full max-w-md bg-gray-800 rounded animate-pulse" />
        <div className="flex gap-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-9 w-28 bg-gray-800 rounded-lg animate-pulse" />
          ))}
        </div>
        <div className="card border-gray-800 space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-10 bg-gray-800/80 rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (brandsError) {
    return (
      <div className="card border-gray-800 border-red-900/50 text-red-300 py-8 text-center bg-gray-900">
        {errMessage(brandsErr)}
      </div>
    );
  }

  if (!brands?.length) {
    return (
      <div className="card border-gray-800 text-center py-12 text-gray-400 bg-gray-900">
        Create a brand to open Revenue Intelligence.
      </div>
    );
  }

  const list = rowsForTab();

  return (
    <div className="space-y-8 pb-16 bg-gray-900 text-white min-h-[50vh]">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Sparkles className="text-brand-300" size={28} aria-hidden />
            Revenue Intelligence
          </h1>
          <p className="text-gray-400 mt-1 max-w-3xl">
            Offer stacks, funnel paths, owned audience value, productization, and monetization density — unified
            dashboard.
          </p>
        </div>
        <button
          type="button"
          className="btn-primary flex items-center gap-2 disabled:opacity-50 shrink-0 border border-gray-800"
          disabled={!selectedBrandId || recomputeMut.isPending}
          onClick={() => selectedBrandId && recomputeMut.mutate(selectedBrandId)}
        >
          <RefreshCw size={16} className={recomputeMut.isPending ? 'animate-spin' : ''} />
          Recompute
        </button>
      </div>

      {recomputeMut.isError && (
        <div className="card border-gray-800 border-amber-900/50 text-amber-200 text-sm">
          {errMessage(recomputeMut.error)}
        </div>
      )}
      {recomputeMut.isSuccess && (
        <div className="card border-gray-800 border-emerald-900/50 text-emerald-300 text-sm">
          Recompute complete — data refreshed.
        </div>
      )}

      <div className="card max-w-xl border-gray-800">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full border-gray-800"
          value={selectedBrandId}
          onChange={(e) => setSelectedBrandId(e.target.value)}
          aria-label="Select brand for revenue intelligence"
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
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors border ${
              tab === t.id
                ? 'bg-brand-600/25 text-brand-300 border-brand-600/40'
                : 'text-gray-400 hover:bg-gray-800 border-transparent'
            }`}
          >
            <t.icon size={16} className={tab === t.id ? 'text-brand-300' : ''} />
            {t.label}
          </button>
        ))}
      </div>

      {dashLoading && (
        <div className="card border-gray-800 space-y-3">
          <div className="h-6 w-48 bg-gray-800 rounded animate-pulse" />
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-12 bg-gray-800/80 rounded animate-pulse" />
          ))}
        </div>
      )}
      {dashError && (
        <div className="card border-gray-800 border-red-900/50 text-red-300 py-6">{errMessage(dashErr)}</div>
      )}

      {dashboard && !dashLoading && (
        <>
          {tab === 'density' ? (
            <div className="card border-gray-800 overflow-x-auto">
              <h2 className="text-lg font-semibold text-brand-300 mb-4">Monetization density</h2>
              {list.length === 0 ? (
                <p className="text-gray-500 text-sm">No density improvements yet — run recompute after content and
                  events exist.</p>
              ) : (
                <ul className="space-y-4">
                  {list.map((row) => {
                    const layers = densityLayersFromTitle(row.title);
                    return (
                      <li
                        key={row.id}
                        className="rounded-lg border border-gray-800 bg-gray-950/40 p-4 text-sm"
                      >
                        <div className="flex flex-wrap justify-between gap-2">
                          <span className="text-white font-medium">{row.title}</span>
                          <span className="text-brand-300">
                            +${Number(row.expected_revenue_uplift || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                          </span>
                        </div>
                        {layers.length > 0 && (
                          <div className="mt-3">
                            <p className="text-xs text-gray-500 uppercase mb-1">Layer recommendations</p>
                            <div className="flex flex-wrap gap-2">
                              {layers.map((layer) => (
                                <span
                                  key={layer}
                                  className="text-xs px-2 py-1 rounded-md border border-gray-700 text-brand-300 bg-gray-900"
                                >
                                  {layer.replace(/_/g, ' ')}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                        {row.description && (
                          <p className="text-gray-400 mt-3">{row.description}</p>
                        )}
                        <div className="flex flex-wrap gap-4 mt-3 text-xs text-gray-500">
                          <span>Cost: ${Number(row.expected_cost || 0).toFixed(2)}</span>
                          <span>Confidence: {(Number(row.confidence || 0) * 100).toFixed(0)}%</span>
                        </div>
                        <p className="text-xs text-gray-500 mt-2">
                          <span className="text-gray-600">Evidence: </span>
                          {evidenceSummary(row.evidence ?? undefined)}
                        </p>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          ) : tab === 'stacks' ? (
            <div className="card border-gray-800 overflow-x-auto">
              <h2 className="text-lg font-semibold text-brand-300 mb-4">Offer stacks</h2>
              {list.length === 0 ? (
                <p className="text-gray-500 text-sm">No offer stacks — add offers and content, then recompute.</p>
              ) : (
                <table className="w-full text-sm text-left">
                  <thead>
                    <tr className="text-gray-500 text-xs border-b border-gray-800">
                      <th className="py-2 pr-4">Title</th>
                      <th className="py-2 pr-4">AOV uplift</th>
                      <th className="py-2 pr-4">Rev. uplift</th>
                      <th className="py-2 pr-4">Cost</th>
                      <th className="py-2 pr-4">Confidence</th>
                      <th className="py-2">Evidence</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800 text-gray-300">
                    {list.map((row) => (
                      <tr key={row.id}>
                        <td className="py-2 pr-4 text-white max-w-xs">{row.title}</td>
                        <td className="py-2 pr-4 text-brand-300">{aovUpliftPct(row.description)}</td>
                        <td className="py-2 pr-4">
                          ${Number(row.expected_revenue_uplift || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                        </td>
                        <td className="py-2 pr-4">${Number(row.expected_cost || 0).toFixed(2)}</td>
                        <td className="py-2 pr-4">{(Number(row.confidence || 0) * 100).toFixed(0)}%</td>
                        <td className="py-2 text-xs text-gray-500 max-w-md">
                          {evidenceSummary(row.evidence ?? undefined)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          ) : (
            <div className="card border-gray-800 overflow-x-auto">
              <h2 className="text-lg font-semibold text-brand-300 mb-4">
                {tab === 'funnels' && 'Funnel paths'}
                {tab === 'owned' && 'Owned audience'}
                {tab === 'products' && 'Productization'}
              </h2>
              {list.length === 0 ? (
                <p className="text-gray-500 text-sm">
                  {tab === 'funnels' && 'No funnel fixes — need click volume and attribution events.'}
                  {tab === 'owned' && 'No owned-audience actions — run recompute.'}
                  {tab === 'products' && 'No productization rows — winners and segments drive recs.'}
                </p>
              ) : (
                <table className="w-full text-sm text-left">
                  <thead>
                    <tr className="text-gray-500 text-xs border-b border-gray-800">
                      <th className="py-2 pr-4">Title</th>
                      <th className="py-2 pr-4">Rev. uplift</th>
                      <th className="py-2 pr-4">Cost</th>
                      <th className="py-2 pr-4">Confidence</th>
                      <th className="py-2">Evidence</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800 text-gray-300">
                    {list.map((row) => (
                      <tr key={row.id}>
                        <td className="py-2 pr-4 text-white max-w-xs">
                          <div>{row.title}</div>
                          {row.description && (
                            <div className="text-xs text-gray-500 mt-1 line-clamp-2">{row.description}</div>
                          )}
                        </td>
                        <td className="py-2 pr-4">
                          ${Number(row.expected_revenue_uplift || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                        </td>
                        <td className="py-2 pr-4">${Number(row.expected_cost || 0).toFixed(2)}</td>
                        <td className="py-2 pr-4">{(Number(row.confidence || 0) * 100).toFixed(0)}%</td>
                        <td className="py-2 text-xs text-gray-500 max-w-md">
                          {evidenceSummary(row.evidence ?? undefined)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
