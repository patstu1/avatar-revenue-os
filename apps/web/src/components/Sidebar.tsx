"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/lib/store";
import { useState } from "react";
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
  ChevronDown,
  ChevronRight,
  type LucideIcon,
} from "lucide-react";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

interface SubGroup {
  label: string;
  items: NavItem[];
  defaultOpen?: boolean;
}

interface NavSection {
  id: string;
  label: string;
  icon: LucideIcon;
  items?: NavItem[];
  subGroups?: SubGroup[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    id: "home",
    label: "Home",
    icon: LayoutDashboard,
    items: [
      { href: "/dashboard", label: "Revenue Dashboard", icon: LayoutDashboard },
      { href: "/dashboard/executive-intel", label: "Executive Dashboard", icon: Crown },
      { href: "/dashboard/revenue-intelligence", label: "Revenue Intelligence", icon: TrendingUp },
      { href: "/dashboard/revenue-machine", label: "Revenue Machine", icon: Zap },
      { href: "/dashboard/ai-command-center", label: "AI Command Center", icon: Brain },
      { href: "/dashboard/hyperscale", label: "Scale Health", icon: Activity },
      { href: "/dashboard/revenue-ceiling", label: "Revenue Ceiling", icon: TrendingUp },
      { href: "/dashboard/revenue-leaks", label: "Revenue Leaks", icon: AlertTriangle },
      { href: "/dashboard/creator-revenue-blockers", label: "Revenue Blockers", icon: AlertTriangle },
    ],
    subGroups: [
      {
        label: "Growth & Scale",
        items: [
          { href: "/dashboard/scale", label: "Scale Command", icon: TrendingUp },
          { href: "/dashboard/growth", label: "Growth Intel", icon: Sparkles },
          { href: "/dashboard/scale-alerts", label: "Scale Alerts", icon: Target },
          { href: "/dashboard/growth-commander", label: "Growth Commander", icon: Command },
          { href: "/dashboard/growth-command-center", label: "Growth Command Center", icon: Radio },
          { href: "/dashboard/max-output", label: "Output Scaling", icon: Gauge },
        ],
      },
      {
        label: "Operator Panels",
        items: [
          { href: "/dashboard/command-center", label: "System Command Center", icon: Radio },
          { href: "/dashboard/cockpit", label: "Operator Cockpit", icon: Target },
          { href: "/dashboard/copilot", label: "Operator Copilot", icon: MessageCircle },
          { href: "/dashboard/copilot-missing", label: "Missing Items", icon: AlertTriangle },
          { href: "/dashboard/copilot-actions", label: "Operator Actions", icon: ClipboardCheck },
          { href: "/dashboard/copilot-status", label: "Quick Status", icon: Activity },
          { href: "/dashboard/upside-cost", label: "Cost / Upside", icon: DollarSign },
        ],
      },
    ],
  },

  {
    id: "studio",
    label: "Studio",
    icon: Film,
    subGroups: [
      {
        label: "Production",
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
        label: "Brands & Accounts",
        items: [
          { href: "/dashboard/brands", label: "Brands", icon: Megaphone },
          { href: "/dashboard/avatars", label: "Avatars", icon: Palette },
          { href: "/dashboard/accounts", label: "Creator Accounts", icon: Users },
        ],
      },
      {
        label: "Content Pipeline",
        items: [
          { href: "/dashboard/content", label: "Content Briefs", icon: FileText },
          { href: "/dashboard/publishing", label: "Script Review", icon: MonitorPlay },
          { href: "/dashboard/memory", label: "Media Jobs", icon: Video },
          { href: "/dashboard/qa", label: "QA Center", icon: Shield },
          { href: "/dashboard/approval", label: "Approvals", icon: ClipboardCheck },
          { href: "/dashboard/library", label: "Content Library", icon: Library },
          { href: "/dashboard/calendar", label: "Publishing Calendar", icon: Calendar },
        ],
      },
      {
        label: "Content Forms",
        items: [
          { href: "/dashboard/content-forms", label: "Form Recommendations", icon: Layers },
          { href: "/dashboard/content-form-mix", label: "Form Mix", icon: PieChart },
          { href: "/dashboard/content-form-blockers", label: "Form Blockers", icon: AlertTriangle },
        ],
      },
    ],
  },

  {
    id: "distribution",
    label: "Distribution",
    icon: Send,
    subGroups: [
      {
        label: "Publishing",
        items: [
          { href: "/dashboard/distribution-plans", label: "Distribution Plans", icon: Layers },
          { href: "/dashboard/content-runner", label: "Content Runner", icon: Zap },
          { href: "/dashboard/auto-queue", label: "Publish Queue", icon: Layers },
          { href: "/dashboard/buffer-profiles", label: "Buffer Profiles", icon: Send },
          { href: "/dashboard/buffer-publish", label: "Buffer Publish Queue", icon: Send },
          { href: "/dashboard/buffer-status", label: "Buffer Status", icon: RefreshCw },
          { href: "/dashboard/buffer-readiness", label: "Channel Readiness", icon: CheckCircle2 },
        ],
      },
      {
        label: "Execution",
        items: [
          { href: "/dashboard/webhook-ingestion", label: "Webhook & Event Ingestion", icon: Webhook },
          { href: "/dashboard/sequence-triggers", label: "Sequence Triggers", icon: Zap },
          { href: "/dashboard/crm-sync", label: "CRM / Audience Sync", icon: Contact },
          { href: "/dashboard/email-sms-execution", label: "Email & SMS Execution", icon: MessageCircle },
          { href: "/dashboard/analytics-sync", label: "Analytics Sync", icon: BarChart3 },
          { href: "/dashboard/ad-reporting", label: "Ad Reporting", icon: Megaphone },
        ],
      },
      {
        label: "Channels",
        items: [
          { href: "/dashboard/account-warmup", label: "Account Activation", icon: TrendingUp },
          { href: "/dashboard/account-maturity", label: "Account Health", icon: CheckCircle2 },
          { href: "/dashboard/account-state-intel", label: "Account Health Intel", icon: Gauge },
        ],
      },
      {
        label: "Advanced",
        defaultOpen: false,
        items: [
          { href: "/dashboard/buffer-blockers", label: "Buffer Blockers", icon: AlertTriangle },
          { href: "/dashboard/buffer-truth", label: "Execution Audit", icon: Shield },
          { href: "/dashboard/buffer-retry", label: "Retry & Failures", icon: RotateCcw },
          { href: "/dashboard/messaging-blockers", label: "Messaging Blockers", icon: AlertTriangle },
          { href: "/dashboard/analytics-truth", label: "Analytics / Attribution", icon: Database },
        ],
      },
    ],
  },

  {
    id: "revenue",
    label: "Revenue",
    icon: DollarSign,
    subGroups: [
      {
        label: "Core",
        items: [
          { href: "/dashboard/revenue-machine", label: "Revenue Machine", icon: Zap },
          { href: "/dashboard/creator-revenue-hub", label: "Revenue Hub", icon: Briefcase },
          { href: "/dashboard/monetization", label: "Monetization Center", icon: CreditCard },
          { href: "/dashboard/revenue-avenues", label: "Revenue Avenues", icon: TrendingUp },
          { href: "/dashboard/revenue", label: "Revenue Attribution", icon: Wallet },
          { href: "/dashboard/revenue-intel", label: "Revenue Intel", icon: Layers },
        ],
      },
      {
        label: "Offers",
        items: [
          { href: "/dashboard/offers", label: "Offer Catalog", icon: ShoppingBag },
          { href: "/dashboard/offer-lab", label: "Offer Lab", icon: Gem },
          { href: "/dashboard/offer-lifecycle", label: "Offer Lifecycle", icon: Recycle },
          { href: "/dashboard/revenue-ceiling/offer-ladders", label: "Offer Ladders", icon: Layers },
          { href: "/dashboard/expansion-pack2-a/offers", label: "Owned Offers", icon: Package },
        ],
      },
      {
        label: "Sales",
        items: [
          { href: "/dashboard/expansion-pack2-a", label: "Sales Engine", icon: Target },
          { href: "/dashboard/expansion-pack2-a/leads", label: "Lead Qualification", icon: Users },
          { href: "/dashboard/expansion-pack2-a/closer", label: "Sales Closer", icon: Target },
          { href: "/dashboard/revenue-ceiling-b/high-ticket", label: "High-Ticket", icon: Gem },
          { href: "/dashboard/revenue-ceiling-b/upsell", label: "Upsell / Cross-Sell", icon: TrendingUp },
          { href: "/dashboard/deal-desk", label: "Deal Desk", icon: Handshake },
        ],
      },
      {
        label: "Pricing & Retention",
        items: [
          { href: "/dashboard/expansion-pack2-b/pricing", label: "Pricing Intelligence", icon: DollarSign },
          { href: "/dashboard/expansion-pack2-b/bundling", label: "Bundles & Packaging", icon: Package },
          { href: "/dashboard/expansion-pack2-b/retention", label: "Retention & Reactivation", icon: Repeat },
          { href: "/dashboard/revenue-ceiling-c/recurring", label: "Recurring Revenue", icon: Repeat },
        ],
      },
      {
        label: "Sponsors & Affiliates",
        items: [
          { href: "/dashboard/sponsors", label: "Sponsor Deals", icon: HandCoins },
          { href: "/dashboard/revenue-ceiling-c/sponsors", label: "Sponsor Inventory", icon: HandCoins },
          { href: "/dashboard/expansion-pack2-c/sponsor-sales", label: "Sponsor Sales", icon: HandCoins },
          { href: "/dashboard/affiliate-intel", label: "Affiliate Intel", icon: HandCoins },
          { href: "/dashboard/owned-affiliate-program", label: "Affiliate Program", icon: Users },
        ],
      },
      {
        label: "Creator Revenue",
        items: [
          { href: "/dashboard/ugc-services", label: "UGC / Creative Services", icon: PenTool },
          { href: "/dashboard/service-consulting", label: "Services / Consulting", icon: Briefcase },
          { href: "/dashboard/premium-access", label: "Premium Access", icon: Crown },
          { href: "/dashboard/licensing", label: "Licensing", icon: FileKey },
          { href: "/dashboard/syndication", label: "Syndication", icon: Newspaper },
          { href: "/dashboard/data-products", label: "Data Products", icon: DatabaseIcon },
          { href: "/dashboard/merch", label: "Merch / Physical", icon: ShoppingBag },
          { href: "/dashboard/live-events", label: "Live Events", icon: Video },
        ],
      },
      {
        label: "Growth Ops",
        items: [
          { href: "/dashboard/revenue-ceiling/owned-audience", label: "Owned Audience", icon: Users },
          { href: "/dashboard/revenue-ceiling/sequences", label: "Sequences", icon: Mail },
          { href: "/dashboard/revenue-ceiling/funnel-leaks", label: "Funnel Leaks", icon: AlertTriangle },
          { href: "/dashboard/comment-cash", label: "Comment Conversion", icon: MessageSquare },
          { href: "/dashboard/landing-pages", label: "Landing Pages", icon: FileText },
          { href: "/dashboard/campaigns", label: "Campaigns", icon: Briefcase },
          { href: "/dashboard/capital-allocation", label: "Capital Allocation", icon: DollarSign },
        ],
      },
      {
        label: "Advanced",
        defaultOpen: false,
        items: [
          { href: "/dashboard/revenue-pressure", label: "Revenue Performance", icon: Flame },
          { href: "/dashboard/revenue-ceiling-b", label: "Revenue Ceiling (B)", icon: Gem },
          { href: "/dashboard/revenue-ceiling-b/productization", label: "Productization", icon: Package },
          { href: "/dashboard/revenue-ceiling-b/revenue-density", label: "Revenue Density", icon: BarChart3 },
          { href: "/dashboard/revenue-ceiling-c", label: "Revenue Ceiling (C)", icon: Repeat },
          { href: "/dashboard/revenue-ceiling-c/trust", label: "Trust Conversion", icon: Shield },
          { href: "/dashboard/revenue-ceiling-c/mix", label: "Monetization Mix", icon: BarChart3 },
          { href: "/dashboard/revenue-ceiling-c/promotion", label: "Paid Promotion Gate", icon: Megaphone },
          { href: "/dashboard/expansion-pack2-b", label: "Pricing & Retention", icon: Layers },
          { href: "/dashboard/expansion-pack2-c", label: "Advanced Revenue", icon: Compass },
          { href: "/dashboard/expansion-pack2-c/referral", label: "Referral & Ambassador", icon: Users },
          { href: "/dashboard/expansion-pack2-c/competitive-gap", label: "Competitive Gaps", icon: Target },
          { href: "/dashboard/expansion-pack2-c/profit-guardrails", label: "Profit Guardrails", icon: Shield },
          { href: "/dashboard/affiliate-governance", label: "Affiliate Governance", icon: Shield },
          { href: "/dashboard/creator-revenue-truth", label: "Execution Truth", icon: Shield },
          { href: "/dashboard/creator-revenue-events", label: "Revenue Events", icon: Receipt },
          { href: "/dashboard/creator-revenue-blockers", label: "Revenue Blockers", icon: AlertTriangle },
        ],
      },
    ],
  },

  {
    id: "intelligence",
    label: "Intelligence",
    icon: Brain,
    subGroups: [
      {
        label: "Decisions",
        items: [
          { href: "/dashboard/brain-decisions", label: "Decision Engine", icon: Brain },
          { href: "/dashboard/decisions", label: "Decision Log", icon: GitBranch },
          { href: "/dashboard/policy-evaluations", label: "Policy Evaluations", icon: Shield },
          { href: "/dashboard/confidence-reports", label: "Confidence Reports", icon: Gauge },
          { href: "/dashboard/arbitration", label: "Priority Arbitration", icon: Scale },
        ],
      },
      {
        label: "Experiments",
        items: [
          { href: "/dashboard/experiment-decisions", label: "Experiment Engine", icon: FlaskConical },
          { href: "/dashboard/experiments", label: "Experiments", icon: FlaskConical },
        ],
      },
      {
        label: "Attribution",
        items: [
          { href: "/dashboard/contribution", label: "Attribution", icon: GitBranch },
          { href: "/dashboard/causal-attribution", label: "Causal Attribution", icon: Compass },
        ],
      },
      {
        label: "Trends",
        items: [
          { href: "/dashboard/trend-scanner", label: "Trend Scanner", icon: TrendingUp },
          { href: "/dashboard/trend-viral", label: "Trends & Viral", icon: Flame },
          { href: "/dashboard/market-timing", label: "Market Timing", icon: Clock },
        ],
      },
      {
        label: "Memory",
        items: [
          { href: "/dashboard/brain-memory", label: "Brain Memory", icon: Brain },
          { href: "/dashboard/creative-memory", label: "Creative Memory", icon: Library },
          { href: "/dashboard/learning", label: "Memory / Learning", icon: Brain },
          { href: "/dashboard/knowledge-graph", label: "Knowledge Graph", icon: Network },
        ],
      },
      {
        label: "Analytics",
        items: [
          { href: "/dashboard/analytics", label: "Analytics", icon: BarChart3 },
          { href: "/dashboard/portfolio", label: "Portfolio Allocation", icon: Scale },
          { href: "/dashboard/capital", label: "Capital Strategy", icon: DollarSign },
          { href: "/dashboard/objection-mining", label: "Objection Intel", icon: MessageSquare },
          { href: "/dashboard/roadmap", label: "Autonomous Roadmap", icon: Map },
        ],
      },
      {
        label: "Advanced",
        defaultOpen: false,
        items: [
          { href: "/dashboard/opportunity-cost", label: "Opportunity Cost", icon: Target },
          { href: "/dashboard/reputation-monitor", label: "Reputation", icon: Shield },
          { href: "/dashboard/pattern-memory", label: "Pattern Memory", icon: Sparkles },
          { href: "/dashboard/agent-memory", label: "Agent Memory", icon: Library },
          { href: "/dashboard/kill-ledger", label: "Kill Ledger", icon: Skull },
          { href: "/dashboard/simulations", label: "Simulations", icon: GitBranch },
          { href: "/dashboard/experiment-truth", label: "Experiment Truth", icon: TestTube2 },
          { href: "/dashboard/upside-cost", label: "Cost / Upside", icon: DollarSign },
        ],
      },
    ],
  },

  {
    id: "system",
    label: "System",
    icon: Shield,
    subGroups: [
      {
        label: "Orchestration",
        items: [
          { href: "/dashboard/agent-orchestration", label: "Agent Orchestration", icon: Bot },
          { href: "/dashboard/workflow-coordination", label: "Workflow Center", icon: GitBranch },
          { href: "/dashboard/workflows", label: "Workflows", icon: ClipboardCheck },
          { href: "/dashboard/jobs", label: "Jobs & Workers", icon: Shield },
          { href: "/dashboard/autonomous-execution", label: "Autonomous Execution", icon: Zap },
          { href: "/dashboard/signal-scanner", label: "Signal Scanner", icon: Radio },
        ],
      },
      {
        label: "Providers",
        items: [
          { href: "/dashboard/provider-registry", label: "Provider Inventory", icon: Database },
          { href: "/dashboard/provider-dependencies", label: "Dependency Map", icon: GitBranch },
          { href: "/dashboard/copilot-providers", label: "Provider Stack", icon: Server },
        ],
      },
      {
        label: "Governance",
        items: [
          { href: "/dashboard/gatekeeper", label: "Gatekeeper", icon: Shield },
          { href: "/dashboard/gatekeeper-ledger", label: "Audit Ledger", icon: ScrollText },
          { href: "/dashboard/quality-governor", label: "Quality Governor", icon: ShieldCheck },
          { href: "/dashboard/brand-governance", label: "Brand Governance", icon: Shield },
          { href: "/dashboard/permissions", label: "Autonomy Matrix", icon: Lock },
          { href: "/dashboard/override-policies", label: "Overrides & Approvals", icon: ShieldCheck },
        ],
      },
      {
        label: "Recovery",
        items: [
          { href: "/dashboard/recovery", label: "Recovery Engine", icon: ShieldAlert },
          { href: "/dashboard/recovery-autonomy", label: "Recovery + Self-Heal", icon: Recycle },
          { href: "/dashboard/failure-families", label: "Failure Suppression", icon: Ban },
          { href: "/dashboard/blocker-detection", label: "Blocker Detection", icon: Ban },
        ],
      },
      {
        label: "States & Policies",
        items: [
          { href: "/dashboard/account-states", label: "Account States", icon: Users },
          { href: "/dashboard/audience-state", label: "Audience State", icon: Users },
          { href: "/dashboard/execution-policies", label: "Execution Policies", icon: Shield },
          { href: "/dashboard/platform-warmup-policies", label: "Platform Policies", icon: Shield },
          { href: "/dashboard/suppression-engine", label: "Suppression Engine", icon: Shield },
          { href: "/dashboard/enterprise-security", label: "Security & Compliance", icon: ShieldAlert },
        ],
      },
      {
        label: "Autonomous Ops",
        items: [
          { href: "/dashboard/monetization-router", label: "Revenue Router", icon: TrendingUp },
          { href: "/dashboard/funnel-runner", label: "Funnel Runner", icon: GitBranch },
          { href: "/dashboard/paid-operator", label: "Paid Growth", icon: HandCoins },
          { href: "/dashboard/sponsor-autonomy", label: "Sponsor Automation", icon: Handshake },
          { href: "/dashboard/retention-autonomy", label: "Retention + LTV", icon: Repeat },
        ],
      },
      {
        label: "Advanced",
        defaultOpen: false,
        items: [
          { href: "/dashboard/agent-mesh", label: "Agent Mesh", icon: Bot },
          { href: "/dashboard/shared-context", label: "Shared Context Bus", icon: Radio },
          { href: "/dashboard/meta-monitoring", label: "Meta-Monitoring", icon: Gauge },
          { href: "/dashboard/self-corrections", label: "Self-Corrections", icon: Recycle },
          { href: "/dashboard/readiness-brain", label: "Readiness Brain", icon: ShieldCheck },
          { href: "/dashboard/provider-readiness", label: "Provider Readiness", icon: Activity },
          { href: "/dashboard/provider-blockers", label: "Provider Blockers", icon: AlertTriangle },
          { href: "/dashboard/copilot-readiness", label: "Provider Readiness Detail", icon: ShieldCheck },
          { href: "/dashboard/opportunity-states", label: "Opportunity States", icon: Compass },
          { href: "/dashboard/execution-states", label: "Execution States", icon: Zap },
          { href: "/dashboard/audience-states-v2", label: "Audience States V2", icon: Users },
          { href: "/dashboard/brain-escalations", label: "Brain Escalations", icon: AlertTriangle },
          { href: "/dashboard/operator-escalations", label: "Operator Escalations", icon: Bell },
          { href: "/dashboard/capacity", label: "Capacity", icon: Gauge },
          { href: "/dashboard/gatekeeper-completion", label: "Completion Gate", icon: CheckSquare },
          { href: "/dashboard/gatekeeper-truth", label: "Truth Gate", icon: Eye },
          { href: "/dashboard/gatekeeper-tests", label: "Test Sufficiency", icon: TestTube2 },
          { href: "/dashboard/gatekeeper-closure", label: "Execution Signoff", icon: GitMerge },
          { href: "/dashboard/gatekeeper-contradictions", label: "Logic Conflicts", icon: AlertOctagon },
          { href: "/dashboard/gatekeeper-commands", label: "Instruction Quality", icon: Terminal },
          { href: "/dashboard/gatekeeper-dependencies", label: "Dependencies", icon: Link2 },
          { href: "/dashboard/gatekeeper-alerts", label: "Gatekeeper Alerts", icon: Bell },
          { href: "/dashboard/gatekeeper-expansion", label: "Expansion Perms", icon: Lock },
        ],
      },
    ],
  },

  {
    id: "settings",
    label: "Settings",
    icon: Settings,
    items: [
      { href: "/dashboard/settings", label: "Settings & API Keys", icon: Settings },
      { href: "/dashboard/integrations", label: "Integrations", icon: Network },
      { href: "/dashboard/integrations", label: "Connectors & Listening", icon: Network },
      { href: "/dashboard/payment-connectors", label: "Payment Connectors", icon: CreditCard },
    ],
  },
];

function isItemActive(pathname: string, href: string): boolean {
  if (href === "/dashboard") return pathname === "/dashboard";
  return pathname === href || pathname.startsWith(href + "/");
}

function sectionContainsActive(section: NavSection, pathname: string): boolean {
  if (section.items?.some((i) => isItemActive(pathname, i.href))) return true;
  return !!section.subGroups?.some((g) =>
    g.items.some((i) => isItemActive(pathname, i.href)),
  );
}

function NavLink({ item, pathname }: { item: NavItem; pathname: string }) {
  const active = isItemActive(pathname, item.href);
  return (
    <Link
      href={item.href}
      className={`flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm transition-colors ${
        active
          ? "bg-brand-600/20 text-brand-300 font-medium"
          : "text-gray-400 hover:text-gray-200 hover:bg-gray-800"
      }`}
    >
      <item.icon size={15} />
      {item.label}
    </Link>
  );
}

function SidebarSubGroup({
  group,
  pathname,
  initialOpen,
}: {
  group: SubGroup;
  pathname: string;
  initialOpen: boolean;
}) {
  const groupHasActive = group.items.some((i) =>
    isItemActive(pathname, i.href),
  );
  const [open, setOpen] = useState(initialOpen || groupHasActive);

  return (
    <div className="mt-1">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-1 text-[10px] font-semibold text-gray-500 uppercase tracking-widest hover:text-gray-300 transition-colors"
      >
        {group.label}
        {open ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
      </button>
      {open && (
        <div className="space-y-0.5 mt-0.5">
          {group.items.map((item) => (
            <NavLink key={item.href} item={item} pathname={pathname} />
          ))}
        </div>
      )}
    </div>
  );
}

function SidebarSection({
  section,
  pathname,
}: {
  section: NavSection;
  pathname: string;
}) {
  const active = sectionContainsActive(section, pathname);
  const [open, setOpen] = useState(active);

  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs font-bold text-gray-400 uppercase tracking-wider hover:text-gray-200 transition-colors"
      >
        <span className="flex items-center gap-2">
          <section.icon size={16} className={active ? "text-brand-400" : ""} />
          {section.label}
        </span>
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
      </button>

      {open && (
        <div className="space-y-0.5 mt-0.5">
          {section.items?.map((item) => (
            <NavLink key={item.href} item={item} pathname={pathname} />
          ))}
          {section.subGroups?.map((group, idx) => (
            <SidebarSubGroup
              key={group.label}
              group={group}
              pathname={pathname}
              initialOpen={active && idx === 0 && group.defaultOpen !== false}
            />
          ))}
        </div>
      )}
    </div>
  );
}

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

      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-2">
        {NAV_SECTIONS.map((section) => (
          <SidebarSection
            key={section.id}
            section={section}
            pathname={pathname}
          />
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
