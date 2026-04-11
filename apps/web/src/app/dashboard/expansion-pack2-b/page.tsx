'use client';

import { useEffect, useState } from 'react';
import Link from "next/link";
import { DollarSign, Layers, Package, Repeat } from "lucide-react";
import { useBrandId } from '@/hooks/useBrandId';
import { expansionPack2PhaseBApi } from '@/lib/expansion-pack2-phase-b-api';

const CARDS = [
  {
    href: "/dashboard/expansion-pack2-b/pricing",
    label: "Pricing Intelligence",
    desc: "Evaluate price elasticity, competitor positioning, and willingness-to-pay to recommend optimal price points for every active offer.",
    Icon: DollarSign,
  },
  {
    href: "/dashboard/expansion-pack2-b/bundling",
    label: "Bundles & Packaging",
    desc: "Generate value-stack, gateway-premium, and complementary bundles from your offer catalog to drive upsell and average order value.",
    Icon: Package,
  },
  {
    href: "/dashboard/expansion-pack2-b/retention",
    label: "Retention & Reactivation",
    desc: "Score churn risk per customer segment, recommend retention strategies, and design reactivation campaigns for lapsed customers.",
    Icon: Repeat,
  },
] as const;

export default function ExpansionPack2PhaseBHub() {
  const brandId = useBrandId();
  const [stats, setStats] = useState({ pricing: 0, bundles: 0, retention: 0 });

  useEffect(() => {
    if (!brandId) return;
    Promise.all([
      expansionPack2PhaseBApi.pricingRecommendations(brandId).then(r => (r.data ?? r) as unknown[]).catch(() => []),
      expansionPack2PhaseBApi.bundleRecommendations(brandId).then(r => (r.data ?? r) as unknown[]).catch(() => []),
      expansionPack2PhaseBApi.retentionRecommendations(brandId).then(r => (r.data ?? r) as unknown[]).catch(() => []),
    ]).then(([pricing, bundles, retention]) => {
      setStats({ pricing: pricing.length, bundles: bundles.length, retention: retention.length });
    });
  }, [brandId]);

  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Layers className="text-emerald-400" size={28} />
          Expansion Pack 2 — Pricing, Bundling & Retention
        </h1>
        <p className="text-gray-400 mt-1 max-w-2xl">
          Optimise pricing across your offer catalog, generate intelligent
          bundles, and reduce churn with AI-driven retention and reactivation
          campaigns.
        </p>
      </div>

      {brandId && (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-white">{stats.pricing}</p>
            <p className="text-xs text-gray-500">Pricing Recommendations</p>
          </div>
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-white">{stats.bundles}</p>
            <p className="text-xs text-gray-500">Bundle Recommendations</p>
          </div>
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-white">{stats.retention}</p>
            <p className="text-xs text-gray-500">Retention Actions</p>
          </div>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {CARDS.map(({ href, label, desc, Icon }) => (
          <Link
            key={href}
            href={href}
            className="card border border-gray-800 hover:border-emerald-700 transition-colors group"
          >
            <div className="flex items-center gap-2 mb-2">
              <Icon
                size={20}
                className="text-emerald-400 group-hover:text-emerald-300 transition-colors"
              />
              <h2 className="text-white font-semibold">{label}</h2>
            </div>
            <p className="text-gray-400 text-sm leading-relaxed">{desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
