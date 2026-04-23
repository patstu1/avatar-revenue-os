"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageCircle, Bell, ClipboardCheck, Activity } from "lucide-react";

const ROUTE_LABELS: Record<string, string> = {
  "dashboard": "Home",
  "command-center": "System Command Center",
  "revenue-intelligence": "Revenue Intelligence",
  "ai-command-center": "AI Command Center",
  "executive-intel": "Executive Dashboard",
  "copilot": "Operator Copilot",
  "cockpit": "Operator Cockpit",
  "copilot-status": "Quick Status",
  "copilot-actions": "Operator Actions",
  "copilot-missing": "Missing Items",
  "copilot-providers": "Provider Stack",
  "copilot-readiness": "Provider Readiness",
  "accounts": "All Accounts",
  "brands": "Brands",
  "account-state-intel": "Account Health Intel",
  "account-warmup": "Account Warm-Up",
  "account-maturity": "Account Maturity",
  "account-states": "Account States",
  "audience-states-v2": "Audience States V2",
  "scale": "Scale Command",
  "growth": "Growth Intel",
  "scale-alerts": "Scale Alerts",
  "growth-commander": "Growth Commander",
  "growth-command-center": "Growth Command Center",
  "hyperscale": "Scale Health",
  "max-output": "Max Output",
  "content": "Content Briefs",
  "avatars": "Avatars",
  "publishing": "Script Review",
  "memory": "Media Jobs",
  "qa": "QA Center",
  "approval": "Approvals",
  "library": "Content Library",
  "calendar": "Publishing Calendar",
  "content-runner": "Content Runner",
  "content-forms": "Form Recommendations",
  "content-form-mix": "Form Mix",
  "content-form-blockers": "Form Blockers",
  "landing-pages": "Landing Pages",
  "campaigns": "Campaigns",
  "studio": "Studio Dashboard",
  "projects": "Projects",
  "scenes": "Scenes",
  "new": "Scene Builder",
  "characters": "Characters",
  "styles": "Style Presets",
  "generations": "Generations",
  "buffer-profiles": "Buffer Profiles",
  "buffer-publish": "Buffer Publish Queue",
  "buffer-status": "Buffer Status",
  "buffer-blockers": "Buffer Blockers",
  "buffer-truth": "Buffer Execution Truth",
  "buffer-retry": "Buffer Retry / Failure",
  "buffer-readiness": "Buffer Readiness",
  "distribution-plans": "Distribution Plans",
  "revenue-machine": "Revenue Machine",
  "monetization": "Monetization Center",
  "revenue-avenues": "Revenue Avenues",
  "revenue": "Revenue Attribution",
  "revenue-intel": "Revenue Intel",
  "offers": "Offer Catalog",
  "offer-lab": "Offer Lab",
  "offer-lifecycle": "Offer Lifecycle",
  "sponsors": "Sponsors",
  "revenue-leaks": "Revenue Leaks",
  "capital-allocation": "Capital Allocation",
  "revenue-pressure": "Revenue Pressure",
  "experiments": "Experiments",
  "comment-cash": "Comment-to-Cash",
  "revenue-ceiling": "Revenue Ceiling (A)",
  "offer-ladders": "Offer Ladders",
  "owned-audience": "Owned Audience",
  "sequences": "Sequences",
  "funnel-leaks": "Funnel Leaks",
  "revenue-ceiling-b": "Revenue Ceiling (B)",
  "high-ticket": "High-Ticket",
  "productization": "Productization",
  "revenue-density": "Revenue Density",
  "upsell": "Upsell / Cross-Sell",
  "revenue-ceiling-c": "Revenue Ceiling (C)",
  "recurring": "Recurring Revenue",
  "trust": "Trust Conversion",
  "mix": "Monetization Mix",
  "promotion": "Paid Promotion Gate",
  "expansion-pack2-a": "Sales & Offer Engine",
  "leads": "Lead Qualification",
  "closer": "Sales Closer",
  "expansion-pack2-b": "Pricing & Retention",
  "pricing": "Pricing Intelligence",
  "bundling": "Bundles & Packaging",
  "retention": "Retention & Reactivation",
  "expansion-pack2-c": "Advanced Revenue",
  "referral": "Referral & Ambassador",
  "competitive-gap": "Competitive Gaps",
  "sponsor-sales": "Sponsor Sales",
  "profit-guardrails": "Profit Guardrails",
  "creator-revenue-hub": "Revenue Hub",
  "ugc-services": "UGC / Creative Services",
  "service-consulting": "Services / Consulting",
  "premium-access": "Premium Access",
  "creator-revenue-blockers": "Revenue Blockers",
  "creator-revenue-events": "Revenue Events",
  "creator-revenue-truth": "Execution Truth",
  "licensing": "Licensing",
  "syndication": "Syndication",
  "data-products": "Data Products",
  "merch": "Merch / Physical",
  "live-events": "Live Events",
  "owned-affiliate-program": "Affiliate Program",
  "affiliate-intel": "Affiliate Dashboard",
  "affiliate-governance": "Affiliate Governance",
  "experiment-decisions": "Experiment Engine",
  "experiment-truth": "Experiment Truth",
  "pattern-memory": "Winning Patterns",
  "simulations": "Simulations",
  "causal-attribution": "Causal Attribution",
  "trend-viral": "Trends & Viral",
  "analytics": "Analytics",
  "trend-scanner": "Trend Scanner",
  "knowledge-graph": "Knowledge Graph",
  "roadmap": "Autonomous Roadmap",
  "capital": "Capital Strategy",
  "portfolio": "Portfolio Allocation",
  "decisions": "Decision Log",
  "learning": "Memory / Learning",
  "quality-governor": "Quality Governor",
  "objection-mining": "Objection Mining",
  "opportunity-cost": "Opportunity Cost",
  "failure-families": "Failure Suppression",
  "brand-governance": "Brand Governance",
  "contribution": "Attribution",
  "capacity": "Capacity",
  "creative-memory": "Creative Memory",
  "recovery": "Recovery Engine",
  "deal-desk": "Deal Desk",
  "audience-state": "Audience State",
  "reputation-monitor": "Reputation Monitor",
  "market-timing": "Market Timing",
  "kill-ledger": "Kill Ledger",
  "autonomous-execution": "Autonomous Execution",
  "signal-scanner": "Signal Scanner",
  "auto-queue": "Auto Queue",
  "platform-warmup-policies": "Platform Policies",
  "execution-policies": "Execution Policies",
  "monetization-router": "Monetization Router",
  "suppression-engine": "Suppression Engine",
  "funnel-runner": "Funnel Runner",
  "paid-operator": "Paid Operator",
  "sponsor-autonomy": "Sponsor Autonomy",
  "retention-autonomy": "Retention + LTV",
  "recovery-autonomy": "Recovery + Self-Heal",
  "override-policies": "Override / Approval",
  "blocker-detection": "Blocker Detection",
  "operator-escalations": "Operator Escalations",
  "opportunity-states": "Opportunity States",
  "execution-states": "Execution States",
  "workflows": "Workflows",
  "permissions": "Autonomy Matrix",
  "brain-memory": "Brain Memory",
  "brain-decisions": "Brain Decisions",
  "policy-evaluations": "Policy Evaluations",
  "confidence-reports": "Confidence Reports",
  "upside-cost": "Cost / Upside",
  "arbitration": "Priority Arbitration",
  "readiness-brain": "Readiness Brain",
  "brain-escalations": "Brain Escalations",
  "agent-orchestration": "Agent Orchestration",
  "agent-mesh": "Agent Mesh",
  "agent-memory": "Agent Memory",
  "workflow-coordination": "Workflow Coordination",
  "shared-context": "Shared Context Bus",
  "meta-monitoring": "Meta-Monitoring",
  "self-corrections": "Self-Corrections",
  "analytics-truth": "Analytics / Attribution",
  "crm-sync": "CRM / Audience Sync",
  "email-sms-execution": "Email & SMS Execution",
  "messaging-blockers": "Messaging Blockers",
  "webhook-ingestion": "Webhook & Event Ingestion",
  "sequence-triggers": "Sequence Triggers",
  "payment-connectors": "Payment Connectors",
  "analytics-sync": "Analytics Sync",
  "ad-reporting": "Ad Reporting",
  "integrations": "Connectors & Listening",
  "gatekeeper": "Gatekeeper Overview",
  "gatekeeper-completion": "Completion Gate",
  "gatekeeper-truth": "Truth Gate",
  "gatekeeper-closure": "Execution Closure",
  "gatekeeper-tests": "Test Sufficiency",
  "gatekeeper-dependencies": "Dependencies",
  "gatekeeper-contradictions": "Contradictions",
  "gatekeeper-commands": "Command Quality",
  "gatekeeper-expansion": "Expansion Perms",
  "gatekeeper-alerts": "Gatekeeper Alerts",
  "gatekeeper-ledger": "Audit Ledger",
  "provider-registry": "Provider Inventory",
  "provider-readiness": "Provider Readiness",
  "provider-dependencies": "Dependency Map",
  "provider-blockers": "Provider Blockers",
  "enterprise-security": "Security & Compliance",
  "jobs": "Jobs & Workers",
  "settings": "Settings & API Keys",
  "onboarding": "Onboarding",
};

const UTILITY_ITEMS = [
  { href: "/dashboard/copilot", icon: MessageCircle, label: "Copilot" },
  { href: "/dashboard/scale-alerts", icon: Bell, label: "Alerts" },
  { href: "/dashboard/approval", icon: ClipboardCheck, label: "Approvals" },
] as const;

function formatSegment(seg: string): string {
  return (
    ROUTE_LABELS[seg] ||
    seg
      .replace(/-/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

export default function TopBar() {
  const pathname = usePathname();
  const segments = pathname?.split("/").filter(Boolean) || [];
  const crumbs = segments.slice(1);

  return (
    <div className="h-12 bg-gray-900/80 backdrop-blur-sm border-b border-gray-800/60 flex items-center justify-between px-6 sticky top-0 z-40">
      <nav className="flex items-center gap-1.5 text-xs text-gray-500 min-w-0 overflow-hidden">
        {crumbs.map((seg, i) => (
          <span key={i} className="flex items-center gap-1.5 shrink-0">
            {i > 0 && <span className="text-gray-700">/</span>}
            <span className={i === crumbs.length - 1 ? "text-gray-300 font-medium" : ""}>
              {formatSegment(seg)}
            </span>
          </span>
        ))}
        {crumbs.length === 0 && <span className="text-gray-300 font-medium">Home</span>}
      </nav>

      <div className="flex items-center gap-1">
        {UTILITY_ITEMS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs text-gray-400 hover:text-gray-200 hover:bg-gray-800/60 transition-colors"
          >
            <item.icon size={14} />
            <span className="hidden sm:inline">{item.label}</span>
          </Link>
        ))}

        <Link
          href="/dashboard/copilot-status"
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs text-gray-400 hover:text-gray-200 hover:bg-gray-800/60 transition-colors ml-1"
        >
          <span className="relative">
            <Activity size={14} />
            <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          </span>
          <span className="hidden sm:inline">Status</span>
        </Link>
      </div>
    </div>
  );
}
