'use client';

import { useEffect, useState, useMemo, useCallback, useRef } from 'react';
import Link from 'next/link';
import type { LucideIcon } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch, brandsApi, healthApi } from '@/lib/api';
import { analyticsApi } from '@/lib/analytics-api';
import { controlLayerApi } from '@/lib/control-layer-api';
import { gmApi } from '@/lib/gm-api';
import { pipelineApi } from '@/lib/pipeline-api';
import { SetupChecklist } from '@/components/SetupChecklist';
import type { ChecklistState } from '@/components/SetupChecklist';
import { SystemTerminal } from '@/components/SystemTerminal';
import { ChannelPills } from '@/components/ChannelPills';
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Brain,
  CheckCircle2,
  ChevronRight,
  Clock,
  DollarSign,
  Eye,
  Flame,
  Hash,
  Layers,
  Loader2,
  MessageSquare,
  MousePointerClick,
  Package,
  RefreshCw,
  Send,
  Shield,
  TrendingDown,
  TrendingUp,
  Users,
  XCircle,
  Zap,
} from 'lucide-react';

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

type Brand = {
  id: string;
  name: string;
  niche?: string;
  slug?: string;
};

type SystemHealth = {
  total_brands: number;
  total_accounts: number;
  total_offers: number;
  total_content_items: number;
  content_draft: number;
  content_generating: number;
  content_review: number;
  content_approved: number;
  content_publishing: number;
  content_published: number;
  content_failed: number;
  jobs_pending: number;
  jobs_running: number;
  jobs_completed_24h: number;
  jobs_failed_24h: number;
  jobs_retrying: number;
  actions_pending: number;
  actions_critical: number;
  actions_completed_24h: number;
  active_blockers: number;
  active_alerts: number;
  total_revenue_30d: number;
  total_cost_30d: number;
  providers_healthy: number;
  providers_degraded: number;
  providers_down: number;
};

type OperatorAction = {
  id: string;
  action_type: string;
  title: string;
  description?: string;
  priority: string;
  category: string;
  entity_type?: string;
  entity_id?: string;
  brand_id?: string;
  source_module?: string;
  status: string;
  created_at?: string;
};

type SystemEvent = {
  id: string;
  event_domain: string;
  event_type: string;
  event_severity: string;
  entity_type?: string;
  summary: string;
  previous_state?: string;
  new_state?: string;
  actor_type: string;
  requires_action: boolean;
  created_at?: string;
};

type ControlDashboard = {
  health: SystemHealth;
  pending_actions: OperatorAction[];
  recent_events: SystemEvent[];
  critical_count: number;
  pending_action_count: number;
  failed_jobs_24h: number;
  intelligence?: {
    winning_patterns: number;
    active_decisions: number;
    active_experiments: number;
    active_suppressions: number;
  };
  governance?: {
    pending_approvals: number;
    open_alerts: number;
    memory_entries: number;
    creative_atoms: number;
  };
};

type PortfolioOverview = {
  total_revenue: number;
  total_followers: number;
  content_published: number;
  active_accounts: number;
  pending_actions: number;
  brands: BrandPerf[];
  revenue_series?: RevenuePoint[];
};

type BrandPerf = {
  id: string;
  name: string;
  revenue: number;
  content_count: number;
  account_count: number;
  trajectory?: 'growing' | 'flat' | 'declining';
};

type RevenuePoint = {
  date: string;
  revenue: number;
  brand_id?: string;
  platform?: string;
  source?: string;
};

type GMDirective = {
  directive?: string;
  summary?: string;
  created_at?: string;
};

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

const fmtMoney = (n: number) =>
  `$${Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const fmtCompact = (n: number) => {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n || 0);
};

const fmtNum = (n: number) => Number(n || 0).toLocaleString();

const priorityColors: Record<string, string> = {
  critical: 'text-red-400 bg-red-500/10 border-red-500/30',
  high: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
  medium: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  low: 'text-gray-400 bg-gray-500/10 border-gray-500/30',
};

const severityColors: Record<string, string> = {
  critical: 'text-red-400',
  error: 'text-red-400',
  warning: 'text-yellow-400',
  info: 'text-gray-400',
};

const domainIcons: Record<string, LucideIcon> = {
  content: Layers,
  publishing: ArrowRight,
  monetization: DollarSign,
  intelligence: Zap,
  orchestration: RefreshCw,
  governance: Shield,
  recovery: AlertTriangle,
  account: Users,
  system: Activity,
};

const trajectoryConfig: Record<string, { color: string; bg: string; border: string; label: string; Icon: LucideIcon }> = {
  growing: { color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', label: 'Growing', Icon: TrendingUp },
  flat: { color: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', label: 'Flat', Icon: ArrowRight },
  declining: { color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30', label: 'Declining', Icon: TrendingDown },
};

function timeAgo(dateStr?: string): string {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/* ------------------------------------------------------------------ */
/* Sub-Components                                                      */
/* ------------------------------------------------------------------ */

function MetricCard({
  label,
  value,
  icon: Icon,
  color,
  sublabel,
}: {
  label: string;
  value: string | number;
  icon: LucideIcon;
  color: string;
  sublabel?: string;
}) {
  return (
    <div className="bg-gray-900/80 border border-gray-800/60 rounded px-4 py-4 sm:px-5">
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <p className="metric-label">{label}</p>
          <p className="metric-value text-xl sm:text-2xl mt-1 truncate" style={{ color }}>
            {value}
          </p>
          {sublabel && <p className="text-xs text-gray-600 mt-1 font-mono">{sublabel}</p>}
        </div>
        <div className="p-2 rounded shrink-0" style={{ backgroundColor: `${color}12` }}>
          <Icon size={18} style={{ color }} />
        </div>
      </div>
    </div>
  );
}

/* ---- SVG Revenue Chart ---- */

function RevenueChart({
  data,
  timeRange,
  onTimeRangeChange,
  groupBy,
  onGroupByChange,
}: {
  data: RevenuePoint[];
  timeRange: string;
  onTimeRangeChange: (r: string) => void;
  groupBy: string;
  onGroupByChange: (g: string) => void;
}) {
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return [];
    const now = new Date();
    const cutoff = new Date();
    if (timeRange === '7d') cutoff.setDate(now.getDate() - 7);
    else if (timeRange === '30d') cutoff.setDate(now.getDate() - 30);
    else if (timeRange === '90d') cutoff.setDate(now.getDate() - 90);
    else cutoff.setFullYear(2000);

    return data
      .filter((p) => new Date(p.date) >= cutoff)
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  }, [data, timeRange]);

  if (chartData.length === 0) {
    return (
      <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <BarChart3 size={16} className="text-emerald-400" />
            Revenue Over Time
          </h3>
        </div>
        <div className="flex flex-col items-center justify-center py-12 text-gray-600">
          <BarChart3 size={40} className="mb-3 text-gray-700" />
          <p className="text-sm">No revenue data yet</p>
          <p className="text-xs text-gray-700 mt-1">Revenue will appear here as transactions are recorded</p>
        </div>
      </div>
    );
  }

  const maxRev = Math.max(...chartData.map((d) => d.revenue), 1);
  const W = 600;
  const H = 200;
  const padX = 50;
  const padY = 20;
  const plotW = W - padX - 10;
  const plotH = H - padY * 2;

  const points = chartData.map((d, i) => {
    const x = padX + (chartData.length > 1 ? (i / (chartData.length - 1)) * plotW : plotW / 2);
    const y = padY + plotH - (d.revenue / maxRev) * plotH;
    return { x, y, ...d };
  });

  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');
  const areaPath = `${linePath} L${points[points.length - 1].x},${padY + plotH} L${points[0].x},${padY + plotH} Z`;

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((pct) => ({
    value: maxRev * pct,
    y: padY + plotH - pct * plotH,
  }));

  return (
    <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <BarChart3 size={16} className="text-emerald-400" />
          Revenue Over Time
        </h3>
        <div className="flex items-center gap-2 flex-wrap">
          {/* Group By */}
          <div className="flex bg-gray-800 rounded-lg overflow-hidden text-[11px]">
            {['all', 'brand', 'platform', 'source'].map((g) => (
              <button
                key={g}
                onClick={() => onGroupByChange(g)}
                className={`px-2.5 py-1 capitalize transition ${
                  groupBy === g ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                {g}
              </button>
            ))}
          </div>
          {/* Time Range */}
          <div className="flex bg-gray-800 rounded-lg overflow-hidden text-[11px]">
            {['7d', '30d', '90d', 'all'].map((r) => (
              <button
                key={r}
                onClick={() => onTimeRangeChange(r)}
                className={`px-2.5 py-1 uppercase transition ${
                  timeRange === r ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="w-full overflow-x-auto">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto min-w-[400px]" preserveAspectRatio="xMidYMid meet">
          <defs>
            <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
            </linearGradient>
          </defs>
          {/* Y-axis grid + labels */}
          {yTicks.map((t, i) => (
            <g key={i}>
              <line x1={padX} y1={t.y} x2={W - 10} y2={t.y} stroke="#374151" strokeWidth="0.5" strokeDasharray="4 2" />
              <text x={padX - 6} y={t.y + 4} textAnchor="end" fill="#6b7280" fontSize="9">
                ${fmtCompact(t.value)}
              </text>
            </g>
          ))}
          {/* Area fill */}
          <path d={areaPath} fill="url(#revGrad)" />
          {/* Line */}
          <path d={linePath} fill="none" stroke="#10b981" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
          {/* Data points */}
          {points.map((p, i) => (
            <circle key={i} cx={p.x} cy={p.y} r="3" fill="#10b981" stroke="#064e3b" strokeWidth="1.5">
              <title>{`${p.date}: ${fmtMoney(p.revenue)}`}</title>
            </circle>
          ))}
          {/* X-axis date labels (show a subset) */}
          {points
            .filter((_, i) => {
              const step = Math.max(1, Math.floor(points.length / 6));
              return i % step === 0 || i === points.length - 1;
            })
            .map((p, i) => {
              const d = new Date(p.date);
              const label = `${d.getMonth() + 1}/${d.getDate()}`;
              return (
                <text key={i} x={p.x} y={H - 4} textAnchor="middle" fill="#6b7280" fontSize="9">
                  {label}
                </text>
              );
            })}
        </svg>
      </div>
    </div>
  );
}

/* ---- Brand Performance Card ---- */

function BrandCard({ brand }: { brand: BrandPerf }) {
  const traj = trajectoryConfig[brand.trajectory || 'flat'] || trajectoryConfig.flat;
  const TrajIcon = traj.Icon;

  return (
    <div className={`bg-gray-900/80 border rounded-xl p-4 ${traj.border}`}>
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-white truncate">{brand.name}</h4>
        <span className={`flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${traj.bg} ${traj.color}`}>
          <TrajIcon size={10} />
          {traj.label}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div>
          <p className="text-lg font-bold text-emerald-400">{fmtMoney(brand.revenue)}</p>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">Revenue</p>
        </div>
        <div>
          <p className="text-lg font-bold text-purple-400">{fmtNum(brand.content_count)}</p>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">Content</p>
        </div>
        <div>
          <p className="text-lg font-bold text-blue-400">{fmtNum(brand.account_count)}</p>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">Accounts</p>
        </div>
      </div>
    </div>
  );
}

/* ---- Operator Action Card with Approve/Reject ---- */

function ActionCard({
  action,
  onApprove,
  onReject,
  isApproving,
  isRejecting,
}: {
  action: OperatorAction;
  onApprove: () => void;
  onReject: () => void;
  isApproving: boolean;
  isRejecting: boolean;
}) {
  const colorClass = priorityColors[action.priority] || priorityColors.medium;
  return (
    <div className={`border rounded-lg px-4 py-3 ${colorClass}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="text-[10px] font-bold uppercase tracking-wider opacity-80">
              {action.priority}
            </span>
            <span className="text-[10px] text-gray-500">{action.action_type}</span>
            {action.category && (
              <span className="text-[10px] text-gray-600 bg-gray-800 rounded px-1.5 py-0.5">
                {action.category}
              </span>
            )}
          </div>
          <p className="text-sm font-medium text-white">{action.title}</p>
          {action.description && (
            <p className="text-xs text-gray-500 mt-1 line-clamp-2">{action.description}</p>
          )}
          <div className="flex items-center gap-2 mt-1.5">
            {action.source_module && (
              <span className="text-[10px] text-gray-600">from {action.source_module}</span>
            )}
            <span className="text-[10px] text-gray-600">{timeAgo(action.created_at)}</span>
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={onApprove}
            disabled={isApproving}
            className="px-2.5 py-1.5 rounded-md bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 text-xs font-medium transition disabled:opacity-50"
            title="Approve"
          >
            {isApproving ? <Loader2 size={14} className="animate-spin" /> : 'Approve'}
          </button>
          <button
            onClick={onReject}
            disabled={isRejecting}
            className="px-2.5 py-1.5 rounded-md bg-red-500/10 hover:bg-red-500/20 text-red-400 text-xs font-medium transition disabled:opacity-50"
            title="Reject"
          >
            {isRejecting ? <Loader2 size={14} className="animate-spin" /> : 'Reject'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ---- Event Row ---- */

function EventRow({ event }: { event: SystemEvent }) {
  const Icon = domainIcons[event.event_domain] || Activity;
  const sColor = severityColors[event.event_severity] || severityColors.info;
  return (
    <div className="flex items-start gap-3 py-2.5 px-3 hover:bg-gray-800/30 rounded-lg transition">
      <div className={`mt-0.5 ${sColor}`}>
        <Icon size={14} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm text-gray-300 leading-snug">{event.summary}</p>
        <div className="flex items-center gap-2 mt-1 flex-wrap">
          <span className="text-[10px] font-medium uppercase tracking-wider px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">
            {event.event_domain}
          </span>
          {event.new_state && (
            <span className="text-[10px] text-gray-500">
              {event.previous_state && `${event.previous_state} \u2192 `}{event.new_state}
            </span>
          )}
        </div>
      </div>
      <span className="text-[11px] text-gray-600 shrink-0">{timeAgo(event.created_at)}</span>
    </div>
  );
}

/* ---- GM Directive Banner ---- */

function DirectiveBanner({ directive }: { directive: GMDirective }) {
  const text = directive.directive || directive.summary;
  if (!text) return null;
  return (
    <div className="bg-gradient-to-r from-cyan-500/10 via-blue-500/10 to-purple-500/10 border border-cyan-500/20 rounded-xl px-5 py-3 flex items-center gap-3">
      <MessageSquare size={18} className="text-cyan-400 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-medium text-cyan-400 uppercase tracking-wider mb-0.5">Latest GM Directive</p>
        <p className="text-sm text-gray-300 line-clamp-2">{text}</p>
      </div>
      <Link
        href="/dashboard/gm"
        className="shrink-0 px-3 py-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 text-xs font-medium transition flex items-center gap-1.5"
      >
        Talk to GM
        <ChevronRight size={12} />
      </Link>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main Page                                                           */
/* ------------------------------------------------------------------ */

export default function DashboardOverviewPage() {
  const queryClient = useQueryClient();
  const [revTimeRange, setRevTimeRange] = useState('30d');
  const [revGroupBy, setRevGroupBy] = useState('all');
  const [checklistDismissed, setChecklistDismissed] = useState(false);

  // --- GM startup prompt (first-boot detection) ---
  type StartupData = {
    phase: string;
    machine_state: Record<string, unknown>;
    checklist: ChecklistState;
    checklist_progress: { completed: number; total: number };
    gm_opening: string;
  };
  const { data: startupData, isLoading: startupLoading } = useQuery({
    queryKey: ['gm-startup-prompt'],
    queryFn: () => gmApi.getStartupPrompt().then((r) => r.data as StartupData),
  });

  // --- Core data: control layer dashboard (primary data source) ---
  const {
    data: ctrl,
    isLoading: ctrlLoading,
    isError: ctrlError,
    error: ctrlErr,
  } = useQuery({
    queryKey: ['control-layer-dashboard'],
    queryFn: () => controlLayerApi.dashboard().then((r) => r.data as ControlDashboard),
    refetchInterval: 30_000,
  });

  // --- Portfolio overview (optional, enriches metrics) ---
  const { data: portfolio } = useQuery({
    queryKey: ['portfolio-overview'],
    queryFn: () =>
      apiFetch<PortfolioOverview>('/api/v1/portfolio/overview').catch(() => null),
    refetchInterval: 30_000,
  });

  // --- Brands list ---
  const { data: brands, isLoading: brandsLoading } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  // --- System events (separate feed with auto-refresh) ---
  const { data: eventsFeed } = useQuery({
    queryKey: ['system-events-feed'],
    queryFn: () =>
      apiFetch<SystemEvent[]>('/api/v1/system-events?limit=50').catch(() => null),
    refetchInterval: 15_000,
  });

  // --- Operator actions (separate feed) ---
  const { data: actionsFeed } = useQuery({
    queryKey: ['operator-actions-feed'],
    queryFn: () =>
      apiFetch<OperatorAction[]>('/api/v1/operator-actions?status=pending&limit=30').catch(() => null),
    refetchInterval: 15_000,
  });

  // --- GM directive ---
  const { data: gmDirective } = useQuery({
    queryKey: ['gm-directive'],
    queryFn: () =>
      apiFetch<GMDirective>('/api/v1/gm/directive').catch(() => null),
    refetchInterval: 60_000,
  });

  // --- API health ---
  const { data: apiHealth } = useQuery({
    queryKey: ['health'],
    queryFn: () => healthApi.readyz().then((r) => r.data),
    refetchInterval: 30_000,
  });

  // --- Mutations ---
  const approveMut = useMutation({
    mutationFn: (actionId: string) => controlLayerApi.completeAction(actionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['control-layer-dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['operator-actions-feed'] });
    },
  });

  const rejectMut = useMutation({
    mutationFn: (actionId: string) => controlLayerApi.dismissAction(actionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['control-layer-dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['operator-actions-feed'] });
    },
  });

  const [pipelineBrandId, setPipelineBrandId] = useState<string | null>(null);
  const pipelineRunMut = useMutation({
    mutationFn: (brandId: string) => pipelineApi.runPipeline(brandId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['control-layer-dashboard'] });
    },
  });

  // --- Derived data ---
  const health = ctrl?.health;
  const actions = actionsFeed || ctrl?.pending_actions || [];
  const events = eventsFeed || ctrl?.recent_events || [];
  const brandPerfs: BrandPerf[] = portfolio?.brands || [];
  const revSeries: RevenuePoint[] = portfolio?.revenue_series || [];

  // Compute top-level metrics preferring portfolio data, falling back to control layer
  const totalRevenue = portfolio?.total_revenue ?? health?.total_revenue_30d ?? 0;
  const totalFollowers = portfolio?.total_followers ?? 0;
  const contentPublished = portfolio?.content_published ?? health?.content_published ?? 0;
  const activeAccounts = portfolio?.active_accounts ?? health?.total_accounts ?? 0;
  const pendingActions = portfolio?.pending_actions ?? health?.actions_pending ?? 0;

  // --- Loading state ---
  if (ctrlLoading && brandsLoading && startupLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="animate-spin text-gray-600" size={32} />
          <p className="text-sm text-gray-600">Loading command center...</p>
        </div>
      </div>
    );
  }

  // --- Error state ---
  if (ctrlError && !health) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Portfolio Command Center</h1>
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl py-8 text-center text-red-300">
          Failed to load dashboard: {errMessage(ctrlErr)}
        </div>
      </div>
    );
  }

  // --- First-boot: Welcome overlay (zero brands AND zero accounts) ---
  if (startupData?.phase === 'empty') {
    return (
      <div className="flex items-center justify-center min-h-[70vh]">
        <div className="max-w-[560px] w-full text-center space-y-8">
          <div>
            <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-cyan-500/20 via-blue-500/20 to-purple-500/20 border border-cyan-500/20 mb-6">
              <Zap size={36} className="text-cyan-400" />
            </div>
            <h1 className="text-3xl font-bold text-white tracking-tight">
              Welcome to The Machine
            </h1>
            <p className="text-gray-400 mt-3 text-base leading-relaxed max-w-md mx-auto">
              Your AI-powered revenue system is ready for configuration.
              Talk to the GM to define your niche, audience, and strategy.
              Everything gets built from that conversation.
            </p>
          </div>

          <Link
            href="/dashboard/gm"
            className="inline-flex items-center gap-3 px-8 py-4 rounded-xl bg-gradient-to-r from-cyan-500/20 to-blue-500/20 hover:from-cyan-500/30 hover:to-blue-500/30 border border-cyan-500/30 text-cyan-300 font-semibold text-lg transition-all duration-200 hover:scale-[1.02]"
          >
            <MessageSquare size={22} />
            Talk to GM
            <ChevronRight size={18} />
          </Link>

          <p className="text-xs text-gray-600">
            The GM will ask about your niche, audience, and goals, then build the full
            launch blueprint for your approval.
          </p>
        </div>
      </div>
    );
  }

  // --- Empty state fallback: no brands but startup data not loaded yet ---
  if (!brands?.length && !brandsLoading && !startupData) {
    return (
      <div className="space-y-6 max-w-[800px] mx-auto">
        <h1 className="text-2xl font-bold text-white">Portfolio Command Center</h1>
        {gmDirective && <DirectiveBanner directive={gmDirective} />}
        <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl text-center py-16 px-6">
          <Package className="mx-auto text-gray-700 mb-4" size={56} />
          <p className="text-gray-400 text-lg font-medium">No brands yet</p>
          <p className="text-gray-600 text-sm mt-2 max-w-md mx-auto">
            Talk to the GM to define your first brand and get the operating system running.
          </p>
          <Link
            href="/dashboard/gm"
            className="inline-flex items-center gap-2 mt-6 px-5 py-2.5 rounded-xl bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 font-medium text-sm transition"
          >
            <MessageSquare size={16} />
            Talk to GM to get started
            <ChevronRight size={14} />
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5 max-w-[1600px]">
      {/* ---- GM Directive Banner ---- */}
      {gmDirective && <DirectiveBanner directive={gmDirective} />}

      {/* ---- Setup Checklist Banner (partially configured) ---- */}
      {startupData?.phase === 'partial' && !checklistDismissed && (
        <SetupChecklist
          checklist={startupData.checklist}
          progress={startupData.checklist_progress}
          onDismiss={() => setChecklistDismissed(true)}
        />
      )}

      {/* ---- Header ---- */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Portfolio Command Center</h1>
          <p className="text-sm text-gray-500 mt-0.5">Real-time overview across all brands and operations</p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard/gm"
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 text-sm font-medium transition"
          >
            <MessageSquare size={14} />
            Talk to GM
          </Link>
          <div className="flex items-center gap-1.5">
            {apiHealth?.status === 'ready' ? (
              <span className="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 rounded-full px-2.5 py-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Online
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-xs text-yellow-400 bg-yellow-500/10 border border-yellow-500/30 rounded-full px-2.5 py-1">
                <Loader2 size={10} className="animate-spin" />
                Connecting
              </span>
            )}
          </div>
        </div>
      </div>

      {/* ---- Critical Alert Banner ---- */}
      {(ctrl?.critical_count ?? 0) > 0 && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-5 py-3 flex items-center gap-3">
          <AlertOctagon size={20} className="text-red-400 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-red-300">
              {ctrl!.critical_count} critical action{ctrl!.critical_count > 1 ? 's' : ''} require immediate attention
            </p>
            {(ctrl?.failed_jobs_24h ?? 0) > 0 && (
              <p className="text-xs text-red-400/70 mt-0.5">
                {ctrl!.failed_jobs_24h} failed jobs in last 24h
              </p>
            )}
          </div>
        </div>
      )}

      {/* ---- Top Metrics Bar ---- */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <MetricCard
          label="Total Revenue"
          value={fmtMoney(totalRevenue)}
          icon={DollarSign}
          color="#22c55e"
        />
        <MetricCard
          label="Total Followers"
          value={fmtCompact(totalFollowers)}
          icon={Users}
          color="#3b82f6"
          sublabel={totalFollowers === 0 ? 'No follower data yet' : undefined}
        />
        <MetricCard
          label="Content Published"
          value={fmtNum(contentPublished)}
          icon={Layers}
          color="#8b5cf6"
        />
        <MetricCard
          label="Active Accounts"
          value={fmtNum(activeAccounts)}
          icon={Activity}
          color="#14b8a6"
        />
        <MetricCard
          label="Pending Actions"
          value={pendingActions}
          icon={Clock}
          color={pendingActions > 0 ? '#f59e0b' : '#22c55e'}
          sublabel={
            (health?.actions_critical ?? 0) > 0
              ? `${health!.actions_critical} critical`
              : undefined
          }
        />
      </div>

      {/* ---- Channel Pills + Run Pipeline ---- */}
      <div className="flex items-center justify-between gap-4">
        <ChannelPills />
        <button
          className="btn-primary flex items-center gap-2 shrink-0"
          disabled={pipelineRunMut.isPending || !brands?.length}
          onClick={() => {
            const bid = brands?.[0]?.id;
            if (bid) pipelineRunMut.mutate(bid);
          }}
        >
          {pipelineRunMut.isPending ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <Zap size={16} />
          )}
          Run Pipeline
        </button>
      </div>

      {/* ---- Revenue Chart ---- */}
      <RevenueChart
        data={revSeries}
        timeRange={revTimeRange}
        onTimeRangeChange={setRevTimeRange}
        groupBy={revGroupBy}
        onGroupByChange={setRevGroupBy}
      />

      {/* ---- Brand Performance Cards ---- */}
      {brandPerfs.length > 0 ? (
        <div>
          <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
            <BarChart3 size={16} className="text-blue-400" />
            Brand Performance
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {brandPerfs.map((b) => (
              <BrandCard key={b.id} brand={b} />
            ))}
          </div>
        </div>
      ) : brands && brands.length > 0 ? (
        <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
            <BarChart3 size={16} className="text-blue-400" />
            Brand Performance
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {brands.map((b) => (
              <BrandCard
                key={b.id}
                brand={{
                  id: b.id,
                  name: b.name,
                  revenue: 0,
                  content_count: 0,
                  account_count: 0,
                  trajectory: 'flat',
                }}
              />
            ))}
          </div>
        </div>
      ) : null}

      {/* ---- Two Column: Operator Actions + Activity Feed ---- */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        {/* Operator Action Queue */}
        <div className="lg:col-span-2 bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Shield size={16} className="text-amber-400" />
              Operator Action Queue
            </h3>
            {actions.length > 0 && (
              <span className="text-xs text-gray-500">{actions.length} pending</span>
            )}
          </div>
          {actions.length === 0 ? (
            <div className="text-center py-10">
              <CheckCircle2 className="mx-auto text-emerald-500/50 mb-2" size={36} />
              <p className="text-sm text-gray-500">All clear — no operator actions needed</p>
              <p className="text-xs text-gray-600 mt-1">Actions requiring your attention will appear here</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
              {actions.map((a) => (
                <ActionCard
                  key={a.id}
                  action={a}
                  onApprove={() => approveMut.mutate(a.id)}
                  onReject={() => rejectMut.mutate(a.id)}
                  isApproving={approveMut.isPending && approveMut.variables === a.id}
                  isRejecting={rejectMut.isPending && rejectMut.variables === a.id}
                />
              ))}
            </div>
          )}
        </div>

        {/* Activity Feed */}
        <div className="lg:col-span-3 bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Activity size={16} className="text-cyan-400" />
              Activity Feed
            </h3>
            {events.length > 0 && (
              <span className="text-xs text-gray-500">{events.length} events</span>
            )}
          </div>
          {events.length === 0 ? (
            <div className="text-center py-10">
              <Activity className="mx-auto text-gray-700 mb-2" size={36} />
              <p className="text-sm text-gray-500">No system events yet</p>
              <p className="text-xs text-gray-600 mt-1">
                Events will appear as workers execute and content flows through the pipeline
              </p>
            </div>
          ) : (
            <div className="space-y-0.5 max-h-[500px] overflow-y-auto pr-1">
              {events.map((e) => (
                <EventRow key={e.id} event={e} />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ---- System Terminal ---- */}
      <SystemTerminal />

      {/* ---- System Status Footer ---- */}
      {health && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white mb-3">Infrastructure</h3>
            <div className="space-y-2.5">
              <StatusRow label="API Server" ok={true} />
              <StatusRow label="Database" ok={apiHealth?.checks?.database ?? false} />
              <StatusRow
                label="Workers"
                ok={true}
                sublabel={
                  health.jobs_running > 0 ? `${health.jobs_running} active` : 'Standby'
                }
              />
            </div>
          </div>
          <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white mb-3">Entities</h3>
            <div className="space-y-2.5">
              <StatusRow label="Brands" ok={true} sublabel={`${health.total_brands}`} />
              <StatusRow label="Accounts" ok={health.total_accounts > 0} sublabel={`${health.total_accounts}`} />
              <StatusRow label="Content" ok={health.total_content_items > 0} sublabel={`${health.total_content_items} total`} />
            </div>
          </div>
          <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white mb-3">Operations (24h)</h3>
            <div className="space-y-2.5">
              <StatusRow label="Jobs Completed" ok={true} sublabel={fmtNum(health.jobs_completed_24h)} />
              <StatusRow
                label="Jobs Failed"
                ok={health.jobs_failed_24h === 0}
                sublabel={String(health.jobs_failed_24h)}
                warn={health.jobs_failed_24h > 0}
              />
              <StatusRow label="Provider Cost" ok={true} sublabel={fmtMoney(health.total_cost_30d)} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ---- Status Row ---- */

function StatusRow({
  label,
  ok,
  sublabel,
  warn,
}: {
  label: string;
  ok: boolean;
  sublabel?: string;
  warn?: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-gray-400">{label}</span>
      <div className="flex items-center gap-2">
        {sublabel && <span className="text-xs text-gray-500">{sublabel}</span>}
        <span
          className={`w-2 h-2 rounded-full ${
            warn ? 'bg-yellow-400' : ok ? 'bg-emerald-400' : 'bg-red-400'
          }`}
        />
      </div>
    </div>
  );
}
