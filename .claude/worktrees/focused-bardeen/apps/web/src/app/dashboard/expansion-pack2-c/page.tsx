import Link from "next/link";
import { Compass, HandCoins, Shield, Target, Users } from "lucide-react";

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
