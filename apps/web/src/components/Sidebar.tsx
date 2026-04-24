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
  ClipboardList,
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

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// CORE: proven, wired, daily-use pages only. Everything else is in "More".
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const NAV_SECTIONS: NavSection[] = [
  {
    id: "gm",
    label: "GM",
    icon: Brain,
    items: [
      { href: "/dashboard/gm", label: "Strategic GM", icon: Brain },
    ],
  },
  {
    id: "home",
    label: "Home",
    icon: LayoutDashboard,
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/dashboard/brain-ops", label: "Brain Operations", icon: Brain },
      { href: "/dashboard/cockpit", label: "Operator Cockpit", icon: Target },
      { href: "/dashboard/replies", label: "Reply Drafts", icon: MessageSquare },
      { href: "/dashboard/retention", label: "Retention", icon: ShieldCheck },
      { href: "/dashboard/intakes", label: "Client Intakes", icon: ClipboardList },
    ],
  },
  {
    id: "studio",
    label: "Studio",
    icon: Film,
    subGroups: [
      {
        label: "Brands & Accounts",
        defaultOpen: true,
        items: [
          { href: "/dashboard/brands", label: "Brands", icon: Megaphone },
          { href: "/dashboard/accounts", label: "Creator Accounts", icon: Users },
          { href: "/dashboard/avatars", label: "Avatars", icon: Palette },
        ],
      },
      {
        label: "Content Pipeline",
        defaultOpen: true,
        items: [
          { href: "/dashboard/content", label: "Content", icon: FileText },
          { href: "/dashboard/publishing", label: "Script Review", icon: MonitorPlay },
          { href: "/dashboard/memory", label: "Media Jobs", icon: Video },
          { href: "/dashboard/qa", label: "QA Center", icon: Shield },
          { href: "/dashboard/approval", label: "Approvals", icon: ClipboardCheck },
          { href: "/dashboard/library", label: "Content Library", icon: Library },
          { href: "/dashboard/calendar", label: "Publishing Calendar", icon: Calendar },
        ],
      },
      {
        label: "Cinema Studio",
        items: [
          { href: "/dashboard/studio", label: "Studio Dashboard", icon: Film },
          { href: "/dashboard/studio/projects", label: "Projects", icon: Clapperboard },
          { href: "/dashboard/studio/scenes", label: "Scenes", icon: Camera },
          { href: "/dashboard/studio/characters", label: "Characters", icon: Users },
          { href: "/dashboard/studio/styles", label: "Style Presets", icon: Palette },
          { href: "/dashboard/studio/generations", label: "Generations", icon: Video },
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
        defaultOpen: true,
        items: [
          { href: "/dashboard/revenue", label: "Revenue Attribution", icon: Wallet },
          { href: "/dashboard/offers", label: "Offer Catalog", icon: ShoppingBag },
          { href: "/dashboard/monetization", label: "Monetization Center", icon: CreditCard },
          { href: "/dashboard/sponsors", label: "Sponsor Deals", icon: HandCoins },
        ],
      },
      {
        label: "Distribution",
        items: [
          { href: "/dashboard/buffer-readiness", label: "Channel Readiness", icon: CheckCircle2 },
          { href: "/dashboard/buffer-truth", label: "Execution Audit", icon: Shield },
          { href: "/dashboard/buffer-retry", label: "Retry & Failures", icon: RotateCcw },
        ],
      },
    ],
  },
  {
    id: "intelligence",
    label: "Intelligence",
    icon: Brain,
    items: [
      { href: "/dashboard/analytics", label: "Analytics", icon: BarChart3 },
      { href: "/dashboard/decisions", label: "Decision Log", icon: GitBranch },
      { href: "/dashboard/trend-scanner", label: "Trend Scanner", icon: TrendingUp },
      { href: "/dashboard/experiments", label: "Experiments", icon: FlaskConical },
      { href: "/dashboard/knowledge-graph", label: "Knowledge Graph", icon: Network },
    ],
  },
  {
    id: "system",
    label: "System",
    icon: Shield,
    items: [
      { href: "/dashboard/jobs", label: "Jobs & Workers", icon: Shield },
      { href: "/dashboard/gatekeeper", label: "Gatekeeper", icon: Shield },
      { href: "/dashboard/settings", label: "Settings & API Keys", icon: Settings },
      { href: "/dashboard/integrations", label: "Integrations", icon: Network },
      { href: "/dashboard/payment-connectors", label: "Payment Connectors", icon: CreditCard },
    ],
  },

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // EXTENDED: All other pages, collapsed by default. Not removed, just quiet.
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  {
    id: "more",
    label: "More",
    icon: Layers,
    subGroups: [
      {
        label: "Growth & Scale",
        defaultOpen: false,
        items: [
          { href: "/dashboard/scale", label: "Scale Command", icon: TrendingUp },
          { href: "/dashboard/growth", label: "Growth Intel", icon: Sparkles },
          { href: "/dashboard/scale-alerts", label: "Scale Alerts", icon: Target },
          { href: "/dashboard/growth-commander", label: "Growth Commander", icon: Command },
          { href: "/dashboard/growth-command-center", label: "Growth Command Center", icon: Radio },
          { href: "/dashboard/executive-intel", label: "Executive Dashboard", icon: Crown },
          { href: "/dashboard/revenue-intelligence", label: "Revenue Intelligence", icon: TrendingUp },
          { href: "/dashboard/revenue-machine", label: "Revenue Machine", icon: Zap },
          { href: "/dashboard/ai-command-center", label: "AI Command Center", icon: Brain },
        ],
      },
      {
        label: "Operator Panels",
        defaultOpen: false,
        items: [
          { href: "/dashboard/command-center", label: "System Command Center", icon: Radio },
          { href: "/dashboard/copilot", label: "Operator Copilot", icon: MessageCircle },
          { href: "/dashboard/copilot-missing", label: "Missing Items", icon: AlertTriangle },
          { href: "/dashboard/copilot-actions", label: "Operator Actions", icon: ClipboardCheck },
          { href: "/dashboard/copilot-status", label: "Quick Status", icon: Activity },
          { href: "/dashboard/copilot-providers", label: "Provider Stack", icon: Server },
        ],
      },
      {
        label: "Revenue Extended",
        defaultOpen: false,
        items: [
          { href: "/dashboard/revenue-avenues", label: "Revenue Avenues", icon: TrendingUp },
          { href: "/dashboard/revenue-intel", label: "Revenue Intel", icon: Layers },
          { href: "/dashboard/revenue-ceiling", label: "Revenue Ceiling", icon: TrendingUp },
          { href: "/dashboard/revenue-leaks", label: "Revenue Leaks", icon: AlertTriangle },
          { href: "/dashboard/offer-lab", label: "Offer Lab", icon: Gem },
          { href: "/dashboard/offer-lifecycle", label: "Offer Lifecycle", icon: Recycle },
          { href: "/dashboard/deal-desk", label: "Deal Desk", icon: Handshake },
          { href: "/dashboard/comment-cash", label: "Comment Conversion", icon: MessageSquare },
          { href: "/dashboard/landing-pages", label: "Landing Pages", icon: FileText },
          { href: "/dashboard/campaigns", label: "Campaigns", icon: Briefcase },
          { href: "/dashboard/affiliate-intel", label: "Affiliate Intel", icon: HandCoins },
        ],
      },
      {
        label: "Distribution Extended",
        defaultOpen: false,
        items: [
          { href: "/dashboard/webhook-ingestion", label: "Webhook & Events", icon: Webhook },
          { href: "/dashboard/sequence-triggers", label: "Sequence Triggers", icon: Zap },
          { href: "/dashboard/analytics-sync", label: "Analytics Sync", icon: BarChart3 },
          { href: "/dashboard/ad-reporting", label: "Ad Reporting", icon: Megaphone },
          { href: "/dashboard/account-warmup", label: "Account Activation", icon: TrendingUp },
          { href: "/dashboard/account-state-intel", label: "Account Health Intel", icon: Gauge },
        ],
      },
      {
        label: "System Extended",
        defaultOpen: false,
        items: [
          { href: "/dashboard/provider-registry", label: "Provider Inventory", icon: Database },
          { href: "/dashboard/provider-dependencies", label: "Dependency Map", icon: GitBranch },
          { href: "/dashboard/gatekeeper-ledger", label: "Audit Ledger", icon: ScrollText },
          { href: "/dashboard/quality-governor", label: "Quality Governor", icon: ShieldCheck },
          { href: "/dashboard/brand-governance", label: "Brand Governance", icon: Shield },
          { href: "/dashboard/roadmap", label: "Autonomous Roadmap", icon: Map },
          { href: "/dashboard/portfolio", label: "Portfolio Allocation", icon: Scale },
          { href: "/dashboard/capital", label: "Capital Strategy", icon: DollarSign },
          { href: "/dashboard/pattern-memory", label: "Pattern Memory", icon: Sparkles },
          { href: "/dashboard/recovery", label: "Recovery Engine", icon: ShieldAlert },
        ],
      },
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
