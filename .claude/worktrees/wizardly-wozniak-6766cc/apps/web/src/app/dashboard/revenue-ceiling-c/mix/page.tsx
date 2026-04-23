'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { revenueCeilingPhaseCApi } from '@/lib/revenue-ceiling-phase-c-api';
import { PieChart, RefreshCw } from 'lucide-react';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Error';
}

function pct(v: number) {
  return `${(v * 100).toFixed(1)}%`;
}

function MixBar({ mix, colorClass }: { mix: Record<string, number>; colorClass: string }) {
  return (
    <div className="space-y-2">
      {Object.entries(mix).map(([k, v]) => (
        <div key={k} className="flex items-center gap-3 text-xs">
          <span className="text-gray-400 w-36 truncate shrink-0">{k}</span>
          <div className="flex-1 bg-gray-800 rounded-full h-2 overflow-hidden">
            <div
              className={`h-2 rounded-full ${colorClass}`}
              style={{ width: `${Math.min(Math.max(Number(v) * 100, 0), 100)}%` }}
            />
          </div>
          <span className="text-gray-400 w-10 text-right shrink-0">{(Number(v) * 100).toFixed(0)}%</span>
        </div>
      ))}
    </div>
  );
}

export default function MonetizationMixDashboard() {
  const qc = useQueryClient();
  const [brandId, setBrandId] = useState('');

  const { data: brands } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(String(brands[0].id));
  }, [brands, brandId]);

  const mmQ = useQuery({
    queryKey: ['rc-c-mix', brandId],
    queryFn: () => revenueCeilingPhaseCApi.monetizationMix(brandId).then((r) => r.data),
    enabled: Boolean(brandId),
  });

  const recompute = useMutation({
    mutationFn: () => revenueCeilingPhaseCApi.recomputeMonetizationMix(brandId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rc-c-mix', brandId] }),
  });

  const selected = useMemo(() => brands?.find((b) => String(b.id) === brandId), [brands, brandId]);

  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <PieChart className="text-violet-400" size={28} />
          Monetization Mix Dashboard
        </h1>
        <p className="text-gray-400 mt-1 max-w-2xl">
          Revenue concentration risk (HHI), current vs recommended mix allocation,
          underused monetization paths, and expected margin/LTV uplift.
        </p>
      </div>

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          aria-label="Brand for Monetization Mix"
          value={brandId}
          onChange={(e) => setBrandId(e.target.value)}
        >
          {(brands ?? []).map((b) => (
            <option key={b.id} value={String(b.id)}>{b.name}</option>
          ))}
        </select>
        {selected && <p className="text-sm text-gray-500 mt-2">{selected.name}</p>}
      </div>

      <div className="flex justify-end">
        <button
          type="button"
          disabled={!brandId || recompute.isPending}
          onClick={() => recompute.mutate()}
          className="btn-primary flex items-center gap-2 disabled:opacity-50"
        >
          <RefreshCw size={16} className={recompute.isPending ? 'animate-spin' : ''} />
          Recompute
        </button>
      </div>
      {recompute.isError && (
        <div className="card border-red-900/50 text-red-300 text-sm">{errMessage(recompute.error)}</div>
      )}

      {(mmQ.data as any[] | undefined)?.[0] ? (
        (() => {
          const M = (mmQ.data as any[])[0] as Record<string, unknown>;
          const depRisk = Number(M.dependency_risk ?? 0);
          const depColor = depRisk > 0.6 ? 'text-red-400' : depRisk > 0.35 ? 'text-yellow-400' : 'text-emerald-400';
          const currentMix = M.current_revenue_mix as Record<string, number> | undefined;
          const nextMix = M.next_best_mix as Record<string, number> | undefined;
          const underused = M.underused_monetization_paths as Array<Record<string, unknown>> | undefined;

          return (
            <div className="space-y-4">
              <div className="card border border-gray-800">
                <div className="flex flex-wrap gap-8 items-start mb-4">
                  <div>
                    <p className="stat-label">Dependency Risk</p>
                    <p className={`text-3xl font-bold ${depColor}`}>{pct(depRisk)}</p>
                  </div>
                  <div>
                    <p className="stat-label">Expected Margin Uplift</p>
                    <p className="text-2xl font-semibold text-emerald-300">
                      {pct(Number(M.expected_margin_uplift ?? 0))}
                    </p>
                  </div>
                  <div>
                    <p className="stat-label">Expected LTV Uplift</p>
                    <p className="text-2xl font-semibold text-violet-300">
                      {pct(Number(M.expected_ltv_uplift ?? 0))}
                    </p>
                  </div>
                  <div>
                    <p className="stat-label">Confidence</p>
                    <p className="text-gray-300 text-lg">{pct(Number(M.confidence ?? 0))}</p>
                  </div>
                </div>
                {typeof M.explanation === 'string' && (
                  <p className="text-xs text-gray-500 border-t border-gray-800 pt-3">{M.explanation}</p>
                )}
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                {currentMix && Object.keys(currentMix).length > 0 && (
                  <div className="card border border-gray-800">
                    <p className="stat-label mb-4">Current Revenue Mix</p>
                    <MixBar mix={currentMix} colorClass="bg-violet-500" />
                  </div>
                )}
                {nextMix && Object.keys(nextMix).length > 0 && (
                  <div className="card border border-gray-800">
                    <p className="stat-label mb-4">Next Best Mix</p>
                    <MixBar mix={nextMix} colorClass="bg-emerald-500" />
                  </div>
                )}
              </div>

              {underused && underused.length > 0 && (
                <div className="card border border-gray-800">
                  <p className="stat-label mb-3">Underused Monetization Paths</p>
                  <div className="space-y-3">
                    {underused.map((u, i) => (
                      <div key={i} className="flex items-start gap-3 text-sm">
                        <span className="text-violet-300 font-medium shrink-0 w-44 truncate">
                          {String(u.path ?? u.name ?? '—')}
                        </span>
                        <span className="text-emerald-300 shrink-0 w-12">
                          {pct(Number(u.potential_score ?? 0))}
                        </span>
                        <p className="text-gray-500 text-xs">{String(u.rationale ?? '')}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })()
      ) : (
        !mmQ.isLoading && <p className="text-gray-500">No data — recompute to generate.</p>
      )}
    </div>
  );
}
