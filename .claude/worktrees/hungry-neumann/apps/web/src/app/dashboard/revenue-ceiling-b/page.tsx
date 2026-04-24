'use client';

import Link from 'next/link';
import {
  BarChart3,
  Gem,
  Package,
  TrendingUp,
} from 'lucide-react';

const PAGES = [
  {
    href: '/dashboard/revenue-ceiling-b/high-ticket',
    label: 'High-Ticket Conversion Dashboard',
    description: 'Eligibility scoring, recommended offer paths, CTAs, close-rate proxies, deal values, and profit estimates.',
    icon: Gem,
  },
  {
    href: '/dashboard/revenue-ceiling-b/productization',
    label: 'Productization Opportunities Dashboard',
    description: 'Product recommendations by type, price range, launch value, recurring potential, build complexity.',
    icon: Package,
  },
  {
    href: '/dashboard/revenue-ceiling-b/revenue-density',
    label: 'Revenue Density Dashboard',
    description: 'Per-content-item density: rev per 1k impressions, profit per audience member, ceiling score, recommendations.',
    icon: BarChart3,
  },
  {
    href: '/dashboard/revenue-ceiling-b/upsell',
    label: 'Upsell / Cross-Sell Dashboard',
    description: 'Pairwise upsell recommendations: best next offer, timing, channel, take rate, incremental value, sequencing.',
    icon: TrendingUp,
  },
];

export default function RevenueCeilingPhaseBHub() {
  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Gem className="text-violet-400" size={28} />
          Revenue Ceiling — Phase B
        </h1>
        <p className="text-gray-400 mt-1 max-w-2xl">
          High-ticket conversion, productization, revenue density, and upsell — persisted and recomputed from your
          catalog, content, and performance signals.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {PAGES.map(({ href, label, description, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className="card border border-gray-800 hover:border-violet-800/60 transition-colors group"
          >
            <div className="flex items-center gap-3 mb-2">
              <Icon size={20} className="text-violet-400 group-hover:text-violet-300 transition-colors" />
              <h2 className="text-white font-semibold group-hover:text-violet-200 transition-colors">{label}</h2>
            </div>
            <p className="text-sm text-gray-400">{description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
