'use client';

import { useEffect, useState } from 'react';
import Link from "next/link";
import { Compass, HandCoins, Shield, Target, Users } from "lucide-react";
import { useBrandId } from '@/hooks/useBrandId';
import { expansionPack2PhaseCApi } from '@/lib/expansion-pack2-phase-c-api';

const CARDS = [
  {
    href: "/dashboard/expansion-pack2-c/referral",
    label: "Referral & Ambassador",
    desc: "Identify high-value customer segments for referral programs — recommend optimal incentive types, bonus amounts, and estimated revenue impact.",
    Icon: Users,
  },
  {
    href: "/dashboard/expansion-pack2-c/competitive-gap",
    label: "Competitive Gap Hunter",
    desc: "Analyze pricing, feature, and satisfaction gaps against competitors — surface monetization opportunities with severity and estimated upside.",
    Icon: Target,
  },
  {
    href: "/dashboard/expansion-pack2-c/sponsor-sales",
    label: "Outbound Sponsor Sales",
    desc: "Rank sponsor targets by audience fit, generate tailored outreach sequences, and forecast expected deal value and response rates.",
    Icon: HandCoins,
  },
  {
    href: "/dashboard/expansion-pack2-c/profit-guardrails",
    label: "Profit Guardrails",
    desc: "Monitor profit margin, CAC, burn rate, refund rate, and LTV-to-CAC ratio against thresholds — trigger throttle recommendations on violations.",
    Icon: Shield,
  },
] as const;

export default function ExpansionPack2PhaseCHub() {
  const brandId = useBrandId();
  const [stats, setStats] = useState({ referrals: 0, gaps: 0, sponsors: 0, guardrails: 0 });

  useEffect(() => {
    if (!brandId) return;
    Promise.all([
      expansionPack2PhaseCApi.referralPrograms(brandId).then(r => (r.data ?? r) as unknown[]).catch(() => []),
      expansionPack2PhaseCApi.competitiveGaps(brandId).then(r => (r.data ?? r) as unknown[]).catch(() => []),
      expansionPack2PhaseCApi.sponsorTargets(brandId).then(r => (r.data ?? r) as unknown[]).catch(() => []),
      expansionPack2PhaseCApi.profitGuardrails(brandId).then(r => (r.data ?? r) as unknown[]).catch(() => []),
    ]).then(([referrals, gaps, sponsors, guardrails]) => {
      setStats({ referrals: referrals.length, gaps: gaps.length, sponsors: sponsors.length, guardrails: guardrails.length });
    });
  }, [brandId]);

  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Compass className="text-violet-400" size={28} />
          Expansion Pack 2 — Advanced Revenue Optimization
        </h1>
        <p className="text-gray-400 mt-1 max-w-2xl">
          Referral programs, competitive intelligence, outbound sponsor sales
          pipelines, and profit guardrails that keep your revenue engine
          healthy and growing.
        </p>
      </div>

      {brandId && (
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-white">{stats.referrals}</p>
            <p className="text-xs text-gray-500">Referral Programs</p>
          </div>
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-white">{stats.gaps}</p>
            <p className="text-xs text-gray-500">Competitive Gaps</p>
          </div>
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-white">{stats.sponsors}</p>
            <p className="text-xs text-gray-500">Sponsor Targets</p>
          </div>
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-white">{stats.guardrails}</p>
            <p className="text-xs text-gray-500">Guardrail Reports</p>
          </div>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
