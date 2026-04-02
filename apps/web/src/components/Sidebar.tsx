"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/lib/store";
import {
  LayoutDashboard,
  Users,
  Megaphone,
  Palette,
  ShoppingBag,
  MonitorPlay,
  FileText,
  BarChart3,
  GitBranch,
  Brain,
  Shield,
  Settings,
  LogOut,
  Wallet,
  TrendingUp,
  Target,
  Zap,
  Scale,
  Video,
  CheckCircle2,
  Library,
  Calendar,
  ClipboardCheck,
  Sparkles,
  MessageSquare,
  Map,
  DollarSign,
  Network,
  HandCoins,
  Compass,
  Layers,
  Command,
  Radio,
  Gem,
  Repeat,
  Mail,
  AlertTriangle,
  Package,
  PieChart,
  FlaskConical,
  Gauge,
  Recycle,
  ShieldAlert,
  Handshake,
  Clock,
  Skull,
  Bot,
  Flame,
  ShieldCheck,
  Ban,
  Bell,
  Send,
  RefreshCw,
  Database,
  TestTube2,
  Contact,
  MessageCircle,
  Briefcase,
  Crown,
  Receipt,
  PenTool,
  FileKey,
  Newspaper,
  Database as DatabaseIcon,
  Webhook,
  CreditCard,
  RotateCcw,
  Activity,
  Server,
  CheckSquare,
  Eye,
  GitMerge,
  Link2,
  AlertOctagon,
  Terminal,
  Lock,
  ScrollText,
  Film,
  Camera,
  Clapperboard,
} from "lucide-react";

const NAV_SECTIONS = [
  {
    label: "Account Management",
    items: [
      { href: "/dashboard/accounts", label: "All Accounts", icon: Users },
      { href: "/dashboard/account-state-intel", label: "Account Health Intel", icon: Gauge },
      { href: "/dashboard/account-warmup", label: "Account Warm-Up", icon: TrendingUp },
      { href: "/dashboard/account-maturity", label: "Account Maturity", icon: CheckCircle2 },
    ],
  },
  {
    label: "Command Center",
    items: [
      { href: "/dashboard/command-center", label: "System Command Center", icon: Radio },
      { href: '/dashboard/copilot', label: 'Operator Copilot', icon: MessageCircle },
      { href: "/dashboard", label: "Revenue Dashboard", icon: LayoutDashboard },
      { href: "/dashboard/cockpit", label: "Operator Cockpit", icon: Target },
      { href: "/dashboard/scale", label: "Scale Command", icon: TrendingUp },
      { href: "/dashboard/growth", label: "Growth Intel", icon: Sparkles },
      { href: "/dashboard/scale-alerts", label: "Scale Alerts", icon: Target },
      {
        href: "/dashboard/growth-commander",
        label: "Growth Commander",
        icon: Command,
      },
      {
        href: "/dashboard/growth-command-center",
        label: "Growth Command Center",
        icon: Radio,
      },
      {
        href: "/dashboard/autonomous-execution",
        label: "Autonomous Execution",
        icon: Zap,
      },
      {
        href: "/dashboard/signal-scanner",
        label: "Signal Scanner",
        icon: Radio,
      },
      {
        href: "/dashboard/auto-queue",
        label: "Auto Queue",
        icon: Layers,
      },
      {
        href: "/dashboard/account-warmup",
        label: "Account Warm-Up",
        icon: TrendingUp,
      },
      {
        href: "/dashboard/max-output",
        label: "Max Output",
        icon: Gauge,
      },
      {
        href: "/dashboard/account-maturity",
        label: "Account Maturity",
        icon: CheckCircle2,
      },
      {
        href: "/dashboard/platform-warmup-policies",
        label: "Platform Policies",
        icon: Shield,
      },
      {
        href: "/dashboard/execution-policies",
        label: "Execution Policies",
        icon: Shield,
      },
      {
        href: "/dashboard/content-runner",
        label: "Content Runner",
        icon: Zap,
      },
      {
        href: "/dashboard/distribution-plans",
        label: "Distribution Plans",
        icon: Layers,
      },
      {
        href: "/dashboard/monetization-router",
        label: "Monetization Router",
        icon: TrendingUp,
      },
      {
        href: "/dashboard/suppression-engine",
        label: "Suppression Engine",
        icon: Shield,
      },
      {
        href: "/dashboard/funnel-runner",
        label: "Funnel Runner",
        icon: GitBranch,
      },
      {
        href: "/dashboard/paid-operator",
        label: "Paid Operator",
        icon: HandCoins,
      },
      {
        href: "/dashboard/sponsor-autonomy",
        label: "Sponsor Autonomy",
        icon: Handshake,
      },
      {
        href: "/dashboard/retention-autonomy",
        label: "Retention + LTV",
        icon: Repeat,
      },
      {
        href: "/dashboard/recovery-autonomy",
        label: "Recovery + Self-Heal",
        icon: Recycle,
      },
      {
        href: "/dashboard/agent-orchestration",
        label: "Agent Orchestration",
        icon: Bot,
      },
      {
        href: "/dashboard/revenue-pressure",
        label: "Revenue Pressure",
        icon: Flame,
      },
      {
        href: "/dashboard/override-policies",
        label: "Override / Approval",
        icon: ShieldCheck,
      },
      {
        href: "/dashboard/blocker-detection",
        label: "Blocker Detection",
        icon: Ban,
      },
      {
        href: "/dashboard/operator-escalations",
        label: "Operator Escalations",
        icon: Bell,
      },
      {
        href: "/dashboard/brain-memory",
        label: "Brain Memory",
        icon: Brain,
      },
      {
        href: "/dashboard/account-states",
        label: "Account States",
        icon: Users,
      },
      {
        href: "/dashboard/opportunity-states",
        label: "Opportunity States",
        icon: Compass,
      },
      {
        href: "/dashboard/execution-states",
        label: "Execution States",
        icon: Zap,
      },
      {
        href: "/dashboard/audience-states-v2",
        label: "Audience States V2",
        icon: Users,
      },
      {
        href: "/dashboard/brain-decisions",
        label: "Brain Decisions",
        icon: Brain,
      },
      {
        href: "/dashboard/policy-evaluations",
        label: "Policy Evaluations",
        icon: Shield,
      },
      {
        href: "/dashboard/confidence-reports",
        label: "Confidence Reports",
        icon: Gauge,
      },
      {
        href: "/dashboard/upside-cost",
        label: "Cost / Upside",
        icon: DollarSign,
      },
      {
        href: "/dashboard/arbitration",
        label: "Priority Arbitration",
        icon: Scale,
      },
      {
        href: "/dashboard/agent-mesh",
        label: "Agent Mesh",
        icon: Bot,
      },
      {
        href: "/dashboard/workflow-coordination",
        label: "Workflow Coordination",
        icon: GitBranch,
      },
      {
        href: "/dashboard/shared-context",
        label: "Shared Context Bus",
        icon: Radio,
      },
      {
        href: "/dashboard/agent-memory",
        label: "Agent Memory",
        icon: Library,
      },
      {
        href: "/dashboard/meta-monitoring",
        label: "Meta-Monitoring",
        icon: Gauge,
      },
      {
        href: "/dashboard/self-corrections",
        label: "Self-Corrections",
        icon: Recycle,
      },
      {
        href: "/dashboard/readiness-brain",
        label: "Readiness Brain",
        icon: ShieldCheck,
      },
      {
        href: "/dashboard/brain-escalations",
        label: "Brain Escalations",
        icon: AlertTriangle,
      },
    ],
  },
  {
    label: "Content Form",
    items: [
      { href: "/dashboard/content-forms", label: "Form Recommendations", icon: Layers },
      { href: "/dashboard/content-form-mix", label: "Form Mix", icon: PieChart },
      { href: "/dashboard/content-form-blockers", label: "Form Blockers", icon: AlertTriangle },
    ],
  },
  {
    label: "Copilot Panels",
    items: [
      { href: '/dashboard/copilot-status', label: 'Quick Status', icon: Activity },
      { href: '/dashboard/copilot-actions', label: 'Operator Actions', icon: ClipboardCheck },
      { href: '/dashboard/copilot-missing', label: 'Missing Items', icon: AlertTriangle },
      { href: '/dashboard/copilot-providers', label: 'Provider Stack', icon: Server },
      { href: '/dashboard/copilot-readiness', label: 'Provider Readiness', icon: ShieldCheck },
    ],
  },
  {
    label: "Cinema Studio",
    items: [
      { href: "/dashboard/studio", label: "Studio Dashboard", icon: Film },
      { href: "/dashboard/studio/projects", label: "Projects", icon: Clapperboard },
      { href: "/dashboard/studio/scenes", label: "Scenes", icon: Camera },
      { href: "/dashboard/studio/scenes/new", label: "Scene Builder", icon: Sparkles },
      { href: "/dashboard/studio/characters", label: "Characters", icon: Users },
      { href: "/dashboard/studio/styles", label: "Style Presets", icon: Palette },
      { href: "/dashboard/studio/generations", label: "Generations", icon: Video },
    ],
  },
  {
    label: "Content Engine",
    items: [
      { href: "/dashboard/brands", label: "Brands", icon: Megaphone },
      { href: "/dashboard/avatars", label: "Avatars", icon: Palette },
      { href: "/dashboard/content", label: "Content Briefs", icon: FileText },
      {
        href: "/dashboard/publishing",
        label: "Script Review",
        icon: MonitorPlay,
      },
      { href: "/dashboard/memory", label: "Media Jobs", icon: Video },
      { href: "/dashboard/qa", label: "QA Center", icon: Shield },
      { href: "/dashboard/approval", label: "Approvals", icon: ClipboardCheck },
      { href: "/dashboard/library", label: "Content Library", icon: Library },
      {
        href: "/dashboard/calendar",
        label: "Publishing Calendar",
        icon: Calendar,
      },
    ],
  },
  {
    label: "Distribution",
    items: [
      {
        href: "/dashboard/buffer-profiles",
        label: "Buffer Profiles",
        icon: Send,
      },
      {
        href: "/dashboard/buffer-publish",
        label: "Buffer Publish Queue",
        icon: Send,
      },
      {
        href: "/dashboard/buffer-status",
        label: "Buffer Status",
        icon: RefreshCw,
      },
      {
        href: "/dashboard/buffer-blockers",
        label: "Buffer Blockers",
        icon: AlertTriangle,
      },
    ],
  },
  {
    label: "Live Execution Phase 2",
    items: [
      {
        href: "/dashboard/webhook-ingestion",
        label: "Webhook & Event Ingestion",
        icon: Webhook,
      },
      {
        href: "/dashboard/sequence-triggers",
        label: "Sequence Triggers",
        icon: Zap,
      },
      {
        href: "/dashboard/payment-connectors",
        label: "Payment Connectors",
        icon: CreditCard,
      },
      {
        href: "/dashboard/analytics-sync",
        label: "Analytics Sync",
        icon: BarChart3,
      },
      {
        href: "/dashboard/ad-reporting",
        label: "Ad Reporting",
        icon: Megaphone,
      },
    ],
  },
  {
    label: "Buffer Expansion",
    items: [
      {
        href: "/dashboard/buffer-truth",
        label: "Buffer Execution Truth",
        icon: Shield,
      },
      {
        href: "/dashboard/buffer-retry",
        label: "Buffer Retry / Failure",
        icon: RotateCcw,
      },
      {
        href: "/dashboard/buffer-readiness",
        label: "Buffer Readiness",
        icon: CheckCircle2,
      },
    ],
  },
  {
    label: "Live Execution",
    items: [
      {
        href: "/dashboard/analytics-truth",
        label: "Analytics / Attribution",
        icon: Database,
      },
      {
        href: "/dashboard/experiment-truth",
        label: "Experiment Truth",
        icon: TestTube2,
      },
      {
        href: "/dashboard/crm-sync",
        label: "CRM / Audience Sync",
        icon: Contact,
      },
      {
        href: "/dashboard/email-sms-execution",
        label: "Email & SMS Execution",
        icon: MessageCircle,
      },
      {
        href: "/dashboard/messaging-blockers",
        label: "Messaging Blockers",
        icon: AlertTriangle,
      },
    ],
  },
  {
    label: "Creator Revenue",
    items: [
      {
        href: "/dashboard/creator-revenue-hub",
        label: "Revenue Hub",
        icon: Briefcase,
      },
      {
        href: "/dashboard/ugc-services",
        label: "UGC / Creative Services",
        icon: PenTool,
      },
      {
        href: "/dashboard/service-consulting",
        label: "Services / Consulting",
        icon: Briefcase,
      },
      {
        href: "/dashboard/premium-access",
        label: "Premium Access",
        icon: Crown,
      },
      {
        href: "/dashboard/creator-revenue-blockers",
        label: "Revenue Blockers",
        icon: AlertTriangle,
      },
      {
        href: "/dashboard/creator-revenue-events",
        label: "Revenue Events",
        icon: Receipt,
      },
      {
        href: "/dashboard/creator-revenue-truth",
        label: "Execution Truth",
        icon: Shield,
      },
      {
        href: "/dashboard/licensing",
        label: "Licensing",
        icon: FileKey,
      },
      {
        href: "/dashboard/syndication",
        label: "Syndication",
        icon: Newspaper,
      },
      {
        href: "/dashboard/data-products",
        label: "Data Products",
        icon: DatabaseIcon,
      },
      {
        href: "/dashboard/merch",
        label: "Merch / Physical",
        icon: ShoppingBag,
      },
      {
        href: "/dashboard/live-events",
        label: "Live Events",
        icon: Video,
      },
      {
        href: "/dashboard/owned-affiliate-program",
        label: "Affiliate Program",
        icon: Users,
      },
    ],
  },
  {
    label: "Monetization",
    items: [
      { href: "/dashboard/offers", label: "Offer Catalog", icon: ShoppingBag },
      {
        href: "/dashboard/revenue",
        label: "Revenue Attribution",
        icon: Wallet,
      },
      { href: "/dashboard/sponsors", label: "Sponsor Deals", icon: HandCoins },
      {
        href: "/dashboard/revenue-intel",
        label: "Revenue Intel",
        icon: Layers,
      },
      {
        href: "/dashboard/revenue-ceiling",
        label: "Revenue Ceiling (A)",
        icon: TrendingUp,
      },
      {
        href: "/dashboard/revenue-ceiling/offer-ladders",
        label: "Offer Ladders",
        icon: Layers,
      },
      {
        href: "/dashboard/revenue-ceiling/owned-audience",
        label: "Owned Audience",
        icon: Users,
      },
      {
        href: "/dashboard/revenue-ceiling/sequences",
        label: "Sequences",
        icon: Mail,
      },
      {
        href: "/dashboard/revenue-ceiling/funnel-leaks",
        label: "Funnel Leaks",
        icon: AlertTriangle,
      },
      {
        href: "/dashboard/revenue-ceiling-b",
        label: "Revenue Ceiling (B)",
        icon: Gem,
      },
      {
        href: "/dashboard/revenue-ceiling-b/high-ticket",
        label: "High-Ticket",
        icon: Gem,
      },
      {
        href: "/dashboard/revenue-ceiling-b/productization",
        label: "Productization",
        icon: Package,
      },
      {
        href: "/dashboard/revenue-ceiling-b/revenue-density",
        label: "Revenue Density",
        icon: BarChart3,
      },
      {
        href: "/dashboard/revenue-ceiling-b/upsell",
        label: "Upsell / Cross-Sell",
        icon: TrendingUp,
      },
      {
        href: "/dashboard/revenue-ceiling-c",
        label: "Revenue Ceiling (C)",
        icon: Repeat,
      },
      {
        href: "/dashboard/revenue-ceiling-c/recurring",
        label: "Recurring Revenue",
        icon: Repeat,
      },
      {
        href: "/dashboard/revenue-ceiling-c/sponsors",
        label: "Sponsor Inventory",
        icon: HandCoins,
      },
      {
        href: "/dashboard/revenue-ceiling-c/trust",
        label: "Trust Conversion",
        icon: Shield,
      },
      {
        href: "/dashboard/revenue-ceiling-c/mix",
        label: "Monetization Mix",
        icon: BarChart3,
      },
      {
        href: "/dashboard/revenue-ceiling-c/promotion",
        label: "Paid Promotion Gate",
        icon: Megaphone,
      },
      {
        href: "/dashboard/expansion-pack2-a",
        label: "Sales & Offer Engine",
        icon: Target,
      },
      {
        href: "/dashboard/expansion-pack2-a/leads",
        label: "Lead Qualification",
        icon: Users,
      },
      {
        href: "/dashboard/expansion-pack2-a/closer",
        label: "Sales Closer",
        icon: Target,
      },
      {
        href: "/dashboard/expansion-pack2-a/offers",
        label: "Owned Offers",
        icon: Package,
      },
      {
        href: "/dashboard/expansion-pack2-b",
        label: "Pricing & Retention",
        icon: Layers,
      },
      {
        href: "/dashboard/expansion-pack2-b/pricing",
        label: "Pricing Intelligence",
        icon: DollarSign,
      },
      {
        href: "/dashboard/expansion-pack2-b/bundling",
        label: "Bundles & Packaging",
        icon: Package,
      },
      {
        href: "/dashboard/expansion-pack2-b/retention",
        label: "Retention & Reactivation",
        icon: Repeat,
      },
      {
        href: "/dashboard/expansion-pack2-c",
        label: "Advanced Revenue",
        icon: Compass,
      },
      {
        href: "/dashboard/expansion-pack2-c/referral",
        label: "Referral & Ambassador",
        icon: Users,
      },
      {
        href: "/dashboard/expansion-pack2-c/competitive-gap",
        label: "Competitive Gaps",
        icon: Target,
      },
      {
        href: "/dashboard/expansion-pack2-c/sponsor-sales",
        label: "Sponsor Sales",
        icon: HandCoins,
      },
      {
        href: "/dashboard/expansion-pack2-c/profit-guardrails",
        label: "Profit Guardrails",
        icon: Shield,
      },
      { href: "/dashboard/experiments", label: "Experiments", icon: Zap },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { href: "/dashboard/roadmap", label: "Autonomous Roadmap", icon: Map },
      {
        href: "/dashboard/capital",
        label: "Capital Allocation",
        icon: DollarSign,
      },
      {
        href: "/dashboard/comment-cash",
        label: "Comment-to-Cash",
        icon: MessageSquare,
      },
      {
        href: "/dashboard/knowledge-graph",
        label: "Knowledge Graph",
        icon: Network,
      },
      {
        href: "/dashboard/portfolio",
        label: "Portfolio Allocation",
        icon: Scale,
      },
      {
        href: "/dashboard/trend-scanner",
        label: "Trend Scanner",
        icon: TrendingUp,
      },
      { href: "/dashboard/decisions", label: "Decision Log", icon: GitBranch },
      { href: "/dashboard/analytics", label: "Analytics", icon: BarChart3 },
      { href: "/dashboard/learning", label: "Memory / Learning", icon: Brain },
    ],
  },
  {
    label: "Maximum Strength",
    items: [
      {
        href: "/dashboard/experiment-decisions",
        label: "Experiment Engine",
        icon: FlaskConical,
      },
      {
        href: "/dashboard/contribution",
        label: "Attribution",
        icon: GitBranch,
      },
      { href: "/dashboard/capacity", label: "Capacity", icon: Gauge },
      {
        href: "/dashboard/offer-lifecycle",
        label: "Offer Lifecycle",
        icon: Recycle,
      },
      {
        href: "/dashboard/creative-memory",
        label: "Creative Memory",
        icon: Library,
      },
      {
        href: "/dashboard/recovery",
        label: "Recovery Engine",
        icon: ShieldAlert,
      },
      { href: "/dashboard/deal-desk", label: "Deal Desk", icon: Handshake },
      {
        href: "/dashboard/audience-state",
        label: "Audience State",
        icon: Users,
      },
      {
        href: "/dashboard/reputation-monitor",
        label: "Reputation",
        icon: Shield,
      },
      {
        href: "/dashboard/market-timing",
        label: "Market Timing",
        icon: Clock,
      },
      {
        href: "/dashboard/kill-ledger",
        label: "Kill Ledger",
        icon: Skull,
      },
    ],
  },
  {
    label: "Provider Registry",
    items: [
      { href: "/dashboard/provider-registry", label: "Provider Inventory", icon: Database },
      { href: "/dashboard/provider-readiness", label: "Provider Readiness", icon: Activity },
      { href: "/dashboard/provider-dependencies", label: "Dependency Map", icon: GitBranch },
      { href: "/dashboard/provider-blockers", label: "Provider Blockers", icon: AlertTriangle },
    ],
  },
  {
    label: "Pattern Memory",
    items: [
      { href: "/dashboard/pattern-memory", label: "Winning Patterns", icon: Sparkles },
    ],
  },
  {
    label: "Experiments",
    items: [
      { href: "/dashboard/experiments", label: "Active Experiments", icon: FlaskConical },
    ],
  },
  {
    label: "Capital Allocator",
    items: [
      { href: "/dashboard/capital-allocation", label: "Allocation Dashboard", icon: Wallet },
    ],
  },
  {
    label: "Quality Governor",
    items: [
      { href: "/dashboard/quality-governor", label: "Quality Reports", icon: ShieldCheck },
    ],
  },
  {
    label: "Objection Mining",
    items: [
      { href: "/dashboard/objection-mining", label: "Objection Intel", icon: MessageSquare },
    ],
  },
  {
    label: "Opportunity Cost",
    items: [
      { href: "/dashboard/opportunity-cost", label: "Action Rankings", icon: Target },
    ],
  },
  {
    label: "Failure Suppression",
    items: [
      { href: "/dashboard/failure-families", label: "Failure Families", icon: Ban },
    ],
  },
  {
    label: "Landing Pages",
    items: [
      { href: "/dashboard/landing-pages", label: "Landing Pages", icon: FileText },
    ],
  },
  {
    label: "Campaigns",
    items: [
      { href: "/dashboard/campaigns", label: "Campaign Center", icon: Briefcase },
    ],
  },
  {
    label: "Offer Lab",
    items: [
      { href: "/dashboard/offer-lab", label: "Offer Lab", icon: Gem },
    ],
  },
  {
    label: "Revenue Leaks",
    items: [
      { href: "/dashboard/revenue-leaks", label: "Leak Detector", icon: AlertTriangle },
    ],
  },
  {
    label: "Digital Twin",
    items: [
      { href: "/dashboard/simulations", label: "Simulations", icon: GitBranch },
    ],
  },
  {
    label: "Permissions",
    items: [
      { href: "/dashboard/permissions", label: "Autonomy Matrix", icon: Lock },
    ],
  },
  {
    label: "Causal Attribution",
    items: [
      { href: "/dashboard/causal-attribution", label: "Attribution Engine", icon: Compass },
    ],
  },
  {
    label: "Trends / Viral",
    items: [
      { href: "/dashboard/trend-viral", label: "Trend Engine", icon: Flame },
    ],
  },
  {
    label: "Affiliate Intel",
    items: [
      { href: "/dashboard/affiliate-intel", label: "Affiliate Dashboard", icon: HandCoins },
      { href: "/dashboard/affiliate-governance", label: "Affiliate Governance", icon: Shield },
    ],
  },
  {
    label: "Brand Governance",
    items: [
      { href: "/dashboard/brand-governance", label: "Governance Center", icon: Shield },
    ],
  },
  {
    label: "Enterprise Security",
    items: [
      { href: "/dashboard/enterprise-security", label: "Security & Compliance", icon: ShieldAlert },
    ],
  },
  {
    label: "Workflows",
    items: [
      { href: "/dashboard/workflows", label: "Workflow Center", icon: ClipboardCheck },
    ],
  },
  {
    label: "Scale Ops",
    items: [
      { href: "/dashboard/hyperscale", label: "Scale Health", icon: Activity },
    ],
  },
  {
    label: "Integrations",
    items: [
      { href: "/dashboard/integrations", label: "Connectors & Listening", icon: Network },
    ],
  },
  {
    label: "Executive Intel",
    items: [
      { href: "/dashboard/executive-intel", label: "Executive Dashboard", icon: Crown },
    ],
  },
  {
    label: "AI Gatekeeper",
    items: [
      { href: "/dashboard/gatekeeper", label: "Gatekeeper Overview", icon: Shield },
      { href: "/dashboard/gatekeeper-completion", label: "Completion Gate", icon: CheckSquare },
      { href: "/dashboard/gatekeeper-truth", label: "Truth Gate", icon: Eye },
      { href: "/dashboard/gatekeeper-closure", label: "Execution Closure", icon: GitMerge },
      { href: "/dashboard/gatekeeper-tests", label: "Test Sufficiency", icon: TestTube2 },
      { href: "/dashboard/gatekeeper-dependencies", label: "Dependencies", icon: Link2 },
      { href: "/dashboard/gatekeeper-contradictions", label: "Contradictions", icon: AlertOctagon },
      { href: "/dashboard/gatekeeper-commands", label: "Command Quality", icon: Terminal },
      { href: "/dashboard/gatekeeper-expansion", label: "Expansion Perms", icon: Lock },
      { href: "/dashboard/gatekeeper-alerts", label: "Gatekeeper Alerts", icon: Bell },
      { href: "/dashboard/gatekeeper-ledger", label: "Audit Ledger", icon: ScrollText },
    ],
  },
  {
    label: "System",
    items: [
      { href: "/dashboard/jobs", label: "Jobs & Workers", icon: Shield },
      { href: "/dashboard/settings", label: "Settings", icon: Settings },
    ],
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const logout = useAuthStore((s) => s.logout);
  const user = useAuthStore((s) => s.user);

  return (
    <aside className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col h-screen sticky top-0">
      <div className="p-5 border-b border-gray-800">
        <h1 className="text-lg font-bold bg-gradient-to-r from-brand-400 to-brand-600 bg-clip-text text-transparent">
          Revenue OS
        </h1>
        <p className="text-xs text-gray-500 mt-0.5">AI Avatar Platform</p>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label}>
            <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-widest px-3 mb-2">
              {section.label}
            </p>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const isActive =
                  item.href === "/dashboard"
                    ? pathname === "/dashboard"
                    : pathname === item.href || pathname.startsWith(item.href + "/");
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                      isActive
                        ? "bg-brand-600/20 text-brand-300 font-medium"
                        : "text-gray-400 hover:text-gray-200 hover:bg-gray-800"
                    }`}
                  >
                    <item.icon size={16} />
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="p-4 border-t border-gray-800">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-brand-600 flex items-center justify-center text-white text-xs font-bold">
            {user?.full_name?.charAt(0) || "U"}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-200 truncate">
              {user?.full_name || "User"}
            </p>
            <p className="text-xs text-gray-500 truncate">
              {user?.email || ""}
            </p>
          </div>
          <button
            onClick={logout}
            aria-label="Log out"
            className="text-gray-500 hover:text-red-400 transition-colors"
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </aside>
  );
}
