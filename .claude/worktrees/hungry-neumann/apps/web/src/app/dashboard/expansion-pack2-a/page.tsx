import Link from "next/link";
import { Package, Phone, Target, Users } from "lucide-react";

const CARDS = [
  {
    href: "/dashboard/expansion-pack2-a/leads",
    label: "Lead Qualification",
    desc: "Score inbound leads across urgency, budget, sophistication, offer fit, and trust readiness — tier each as hot, warm, or cold with a recommended next action.",
    Icon: Users,
  },
  {
    href: "/dashboard/expansion-pack2-a/closer",
    label: "Sales Closer Actions",
    desc: "AI-generated, prioritised sales actions per lead — discovery calls, proposals, objection handling, case studies, and more.",
    Icon: Phone,
  },
  {
    href: "/dashboard/expansion-pack2-a/offers",
    label: "Owned Offer Opportunities",
    desc: "Detect owned-product opportunities from comment themes, funnel objections, content engagement, and audience segment signals.",
    Icon: Package,
  },
] as const;

export default function ExpansionPack2PhaseAHub() {
  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Target className="text-violet-400" size={28} />
          Expansion Pack 2 — Sales & Offer Engine
        </h1>
        <p className="text-gray-400 mt-1 max-w-2xl">
          Qualify inbound leads, surface AI-generated sales closer actions, and
          discover owned-offer opportunities derived from audience signals and
          content performance.
        </p>
      </div>

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
