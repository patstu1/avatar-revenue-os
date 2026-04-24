'use client';

import Link from 'next/link';
import {
  AlertTriangle,
  Layers,
  Mail,
  TrendingUp,
  Users,
} from 'lucide-react';

const PAGES = [
  {
    href: '/dashboard/revenue-ceiling/offer-ladders',
    label: 'Offer Ladder Dashboard',
    description: 'Monetization ladders per opportunity: top-of-funnel, upsell / retention / fallback paths, LTV economics.',
    icon: Layers,
  },
  {
    href: '/dashboard/revenue-ceiling/owned-audience',
    label: 'Owned Audience Dashboard',
    description: 'Newsletter, lead magnet, waitlist, SMS, community, remarketing — CTA variants, channel value, opt-in events.',
    icon: Users,
  },
  {
    href: '/dashboard/revenue-ceiling/sequences',
    label: 'Email / SMS Sequence Center',
    description: 'Welcome, nurture, objection-handling, conversion, upsell, reactivation, sponsor-safe sequences.',
    icon: Mail,
  },
  {
    href: '/dashboard/revenue-ceiling/funnel-leaks',
    label: 'Funnel Leak Dashboard',
    description: 'Post-click funnel stage metrics and leak detection — severity, cause, fix, upside, confidence, urgency.',
    icon: AlertTriangle,
  },
];

export default function RevenueCeilingPhaseAHub() {
  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <TrendingUp className="text-emerald-400" size={28} />
          Revenue Ceiling — Phase A
        </h1>
        <p className="text-gray-400 mt-1 max-w-2xl">
          Offer ladders, owned audience, email/SMS sequences, and post-click funnel leak diagnostics — persisted
          and recomputed from your catalog and content.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {PAGES.map(({ href, label, description, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className="card border border-gray-800 hover:border-emerald-800/60 transition-colors group"
          >
            <div className="flex items-center gap-3 mb-2">
              <Icon size={20} className="text-emerald-400 group-hover:text-emerald-300 transition-colors" />
              <h2 className="text-white font-semibold group-hover:text-emerald-200 transition-colors">{label}</h2>
            </div>
            <p className="text-sm text-gray-400">{description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
