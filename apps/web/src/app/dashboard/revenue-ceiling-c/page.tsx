'use client';

import { useEffect, useState } from 'react';
import Link from "next/link";
import {
  Handshake,
  Megaphone,
  PieChart,
  Repeat,
  ShieldCheck,
} from "lucide-react";
import { useBrandId } from '@/hooks/useBrandId';
import { revenueCeilingPhaseCApi } from '@/lib/revenue-ceiling-phase-c-api';

const CARDS = [
  {
    href: "/dashboard/revenue-ceiling-c/recurring",
    label: "Recurring Revenue",
    desc: "Subscription potential scoring, best recurring offer type, audience fit, churn risk proxy, and projected monthly/annual recurring values.",
    Icon: Repeat,
  },
  {
    href: "/dashboard/revenue-ceiling-c/sponsors",
    label: "Sponsor Inventory",
    desc: "Per-content sponsor fit scoring, estimated package pricing, sponsor categories, and brand-level package recommendations.",
    Icon: Handshake,
  },
  {
    href: "/dashboard/revenue-ceiling-c/trust",
    label: "Trust Conversion",
    desc: "Trust deficit scoring, missing trust elements, recommended proof blocks with prioritised actions, and expected conversion uplift.",
    Icon: ShieldCheck,
  },
  {
    href: "/dashboard/revenue-ceiling-c/mix",
    label: "Monetization Mix",
    desc: "Revenue concentration risk (HHI), current vs recommended mix allocation, underused monetization paths, and expected margin/LTV uplift.",
    Icon: PieChart,
  },
  {
    href: "/dashboard/revenue-ceiling-c/promotion",
    label: "Paid Promotion Gate",
    desc: "Strict four-condition organic-winner gate — paid promotion is only allowed when organic winner evidence is strong.",
    Icon: Megaphone,
  },
] as const;

export default function RevenueCeilingPhaseCHub() {
  const brandId = useBrandId();
  const [stats, setStats] = useState({ recurring: 0, sponsors: 0, promotions: 0 });

  useEffect(() => {
    if (!brandId) return;
    Promise.all([
      revenueCeilingPhaseCApi.recurringRevenue(brandId).then(r => (r.data ?? r) as unknown[]).catch(() => []),
      revenueCeilingPhaseCApi.sponsorInventory(brandId).then(r => (r.data ?? r) as unknown[]).catch(() => []),
      revenueCeilingPhaseCApi.paidPromotionCandidates(brandId).then(r => (r.data ?? r) as unknown[]).catch(() => []),
    ]).then(([recurring, sponsors, promotions]) => {
      setStats({ recurring: recurring.length, sponsors: sponsors.length, promotions: promotions.length });
    });
  }, [brandId]);

  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Repeat className="text-violet-400" size={28} />
          Revenue Ceiling — Phase C
        </h1>
        <p className="text-gray-400 mt-1 max-w-2xl">
          Recurring revenue, sponsor inventory, trust conversion, monetization
          mix, and paid-promotion gate — persisted and recomputed from your
          catalog, content, and performance signals.
        </p>
      </div>

      {brandId && (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-white">{stats.recurring}</p>
            <p className="text-xs text-gray-500">Recurring Models</p>
          </div>
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-white">{stats.sponsors}</p>
            <p className="text-xs text-gray-500">Sponsor Inventory</p>
          </div>
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-white">{stats.promotions}</p>
            <p className="text-xs text-gray-500">Promotion Candidates</p>
          </div>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {CARDS.map(({ href, label, desc, Icon }) => (
          <Link
            key={href}
            href={href}
            className="card border border-gray-800 hover:border-violet-700 transition-colors group"
          >
            <div className="flex items-center gap-2 mb-2">
              <Icon
                size={20}
                className="text-violet-400 group-hover:text-violet-300 transition-colors"
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
