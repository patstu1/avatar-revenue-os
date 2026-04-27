'use client';

import { useEffect, useState, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { growthPackApi } from '@/lib/growth-pack-api';
import {
  AlertTriangle,
  BarChart3,
  Coins,
  Command,
  Layers,
  Map,
  RefreshCw,
  Rocket,
  Scale,
  Target,
  TrendingUp,
  Zap,
} from 'lucide-react';

type Brand = { id: string; name: string };

export default function GrowthCommandCenterPage() {
  const qc = useQueryClient();
  const [brandId, setBrandId] = useState('');
  const { data: brands } = useQuery({ queryKey: ['brands'], queryFn: () => brandsApi.list().then((r) => r.data as Brand[]) });
  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(String(brands[0].id));
  }, [brands, brandId]);

  const enabled = Boolean(brandId);
  const useQ = (key: string, fn: () => Promise<unknown>) =>
    useQuery({ queryKey: [key, brandId], queryFn: fn, enabled });

  const cmds = useQ('gc-cmds', () => growthPackApi.growthCommands(brandId).then((r) => r.data));
  const plan = useQ('gc-plan', () => growthPackApi.portfolioLaunchPlan(brandId).then((r) => r.data));
  const blueprints = useQ('gc-bp', () => growthPackApi.accountBlueprints(brandId).then((r) => r.data));
  const plat = useQ('gc-plat', () => growthPackApi.platformAllocation(brandId).then((r) => r.data));
  const niche = useQ('gc-niche', () => growthPackApi.nicheDeployment(brandId).then((r) => r.data));
  const blockers = useQ('gc-block', () => growthPackApi.growthBlockers(brandId).then((r) => r.data));
  const capital = useQ('gc-cap', () => growthPackApi.capitalDeployment(brandId).then((r) => r.data));
  const cann = useQ('gc-can', () => growthPackApi.crossCannibalization(brandId).then((r) => r.data));
  const output = useQ('gc-out', () => growthPackApi.portfolioOutput(brandId).then((r) => r.data));

  const recomputeAll = useMutation({
    mutationFn: async () => {
      await growthPackApi.growthCommandsRecompute(brandId);
      await growthPackApi.portfolioLaunchRecompute(brandId);
      await growthPackApi.accountBlueprintsRecompute(brandId);
      await growthPackApi.platformAllocationRecompute(brandId);
      await growthPackApi.nicheDeploymentRecompute(brandId);
      await growthPackApi.growthBlockersRecompute(brandId);
      await growthPackApi.capitalDeploymentRecompute(brandId);
      await growthPackApi.crossCannibalizationRecompute(brandId);
      await growthPackApi.portfolioOutputRecompute(brandId);
    },
    onSuccess: () => {
      ['gc-cmds', 'gc-plan', 'gc-bp', 'gc-plat', 'gc-niche', 'gc-block', 'gc-cap', 'gc-can', 'gc-out'].forEach((k) =>
        qc.invalidateQueries({ queryKey: [k, brandId] })
      );
    },
  });

  if (!brands?.length) {
    return (
      <div className="min-h-screen bg-gray-900 text-white p-8">
        <p className="text-gray-400">Create a brand first.</p>
      </div>
    );
  }

  const Card = ({ title, icon: Icon, children }: { title: string; icon: typeof Command; children: ReactNode }) => (
    <section className="rounded-xl border border-gray-800 bg-gray-900/60 p-5">
      <h2 className="text-sm font-semibold text-brand-300 mb-3 flex items-center gap-2">
        <Icon size={18} aria-hidden />
        {title}
      </h2>
      {children}
    </section>
  );

  return (
    <div className="min-h-screen bg-gray-900 text-white pb-20">
      <div className="border-b border-gray-800 px-6 py-6 max-w-7xl mx-auto flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Command className="text-brand-400" size={28} aria-hidden />
            Operator Growth Command Center
          </h1>
          <p className="text-gray-400 mt-1 text-sm max-w-2xl">
            Persisted portfolio launch plans, platform allocation, blueprints, blockers, capital, cannibalization, and
            output — all from the same deterministic engines as the API.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <select
            className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm"
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
            disabled={!enabled || recomputeAll.isPending}
            onClick={() => recomputeAll.mutate()}
            className="inline-flex items-center gap-2 rounded-lg bg-brand-600 hover:bg-brand-500 px-4 py-2 text-sm font-medium disabled:opacity-50"
          >
            <RefreshCw size={16} className={recomputeAll.isPending ? 'animate-spin' : ''} aria-hidden />
            Recompute full pack
          </button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        <Card title="1. Portfolio snapshot & launch plan" icon={Rocket}>
          {plan.isLoading ? (
            <p className="text-gray-500 text-sm">Loading…</p>
          ) : plan.data ? (
            <pre className="text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap">{JSON.stringify(plan.data, null, 2)}</pre>
          ) : (
            <p className="text-gray-500 text-sm">No plan yet — run recompute.</p>
          )}
        </Card>

        <Card title="2. Platform allocation view" icon={BarChart3}>
          {plat.isLoading ? (
            <p className="text-gray-500 text-sm">Loading…</p>
          ) : (
            <pre className="text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap">
              {JSON.stringify(plat.data ?? [], null, 2)}
            </pre>
          )}
        </Card>

        <Card title="3. Next accounts to launch (blueprints)" icon={Layers}>
          {blueprints.isLoading ? (
            <p className="text-gray-500 text-sm">Loading…</p>
          ) : (
            <pre className="text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap">
              {JSON.stringify(blueprints.data ?? [], null, 2)}
            </pre>
          )}
        </Card>

        <Card title="4. Exact launch commands" icon={Command}>
          {cmds.isLoading ? (
            <p className="text-gray-500 text-sm">Loading…</p>
          ) : (
            <div className="space-y-4">
              {(Array.isArray(cmds.data) ? cmds.data : []).map((c: Record<string, unknown>) => (
                <article key={String(c.id)} className="rounded-lg border border-gray-800 p-4 space-y-2 text-sm">
                  <div className="font-medium text-brand-200">{String(c.title ?? '')}</div>
                  <p className="text-gray-400">{String(c.exact_instruction ?? '')}</p>
                  <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-2 text-xs text-gray-500">
                    <span>Platform: {String(c.platform ?? '—')}</span>
                    <span>By: {String(c.action_deadline ?? '—')}</span>
                    <span>Rev: {String(c.expected_revenue_min ?? '—')}–{String(c.expected_revenue_max ?? '—')}</span>
                    <span>Cost: {String(c.expected_cost ?? '—')}</span>
                  </div>
                  <details className="text-xs">
                    <summary className="cursor-pointer text-brand-400">Consequence if ignored</summary>
                    <pre className="mt-2 text-gray-500 whitespace-pre-wrap">{JSON.stringify(c.consequence_if_ignored_json, null, 2)}</pre>
                  </details>
                </article>
              ))}
            </div>
          )}
        </Card>

        <Card title="5. Niche deployment map" icon={Map}>
          {niche.isLoading ? (
            <p className="text-gray-500 text-sm">Loading…</p>
          ) : (
            <pre className="text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap">
              {JSON.stringify(niche.data ?? [], null, 2)}
            </pre>
          )}
        </Card>

        <Card title="6. Growth blockers" icon={AlertTriangle}>
          {blockers.isLoading ? (
            <p className="text-gray-500 text-sm">Loading…</p>
          ) : (
            <pre className="text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap">
              {JSON.stringify(blockers.data ?? [], null, 2)}
            </pre>
          )}
        </Card>

        <Card title="7. Capital deployment plan" icon={Coins}>
          {capital.isLoading ? (
            <p className="text-gray-500 text-sm">Loading…</p>
          ) : (
            <pre className="text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap">
              {JSON.stringify(capital.data ?? [], null, 2)}
            </pre>
          )}
        </Card>

        <Card title="8. Cross-account cannibalization" icon={Scale}>
          {cann.isLoading ? (
            <p className="text-gray-500 text-sm">Loading…</p>
          ) : (
            <pre className="text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap">
              {JSON.stringify(cann.data ?? [], null, 2)}
            </pre>
          )}
        </Card>

        <Card title="9. Portfolio output governor" icon={TrendingUp}>
          {output.isLoading ? (
            <p className="text-gray-500 text-sm">Loading…</p>
          ) : (
            <pre className="text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap">
              {JSON.stringify(output.data ?? [], null, 2)}
            </pre>
          )}
        </Card>

        <Card title="10. 30-day growth plan (from blueprints + commands)" icon={Zap}>
          <p className="text-gray-500 text-sm">
            Derived from first-week plans on active commands and blueprint content beats — see Growth Commander command
            cards for day-by-day steps.
          </p>
        </Card>

        <Card title="11. 90-day expansion roadmap (from portfolio launch plan)" icon={Target}>
          <p className="text-gray-500 text-sm">
            90-day revenue/cost envelope lives in <code className="text-brand-400">portfolio_launch_plans</code> (
            estimated_first_90_day_cost, expected_first_90_day_revenue_*).
          </p>
        </Card>
      </div>
    </div>
  );
}
