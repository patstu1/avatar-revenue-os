'use client';

import { useEffect, useMemo, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { dashboardApi, brandsApi, healthApi } from '@/lib/api';
import { analyticsApi } from '@/lib/analytics-api';
import { controlLayerApi } from '@/lib/control-layer-api';
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  ChevronRight,
  Clock,
  DollarSign,
  Eye,
  Flame,
  Layers,
  Loader2,
  MousePointerClick,
  Package,
  RefreshCw,
  Shield,
  TrendingUp,
  Users,
  XCircle,
  Zap,
} from 'lucide-react';

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

type Brand = { id: string; name: string };

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

type IntelligenceCounts = {
  winning_patterns: number;
  active_decisions: number;
  active_experiments: number;
  active_suppressions: number;
};

type GovernanceCounts = {
  pending_approvals: number;
  open_alerts: number;
  memory_entries: number;
  creative_atoms: number;
};

type ControlDashboard = {
  health: SystemHealth;
  pending_actions: OperatorAction[];
  recent_events: SystemEvent[];
  critical_count: number;
  pending_action_count: number;
  failed_jobs_24h: number;
  intelligence?: IntelligenceCounts;
  governance?: GovernanceCounts;
};

type RevenueDash = {
  gross_revenue: number;
  net_profit: number;
  total_impressions: number;
  avg_ctr: number;
  rpm: number;
  epc: number;
  total_conversions: number;
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
    <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl px-5 py-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">{label}</p>
          <p className="text-2xl font-bold mt-1" style={{ color }}>
            {value}
          </p>
          {sublabel && <p className="text-xs text-gray-600 mt-1">{sublabel}</p>}
        </div>
        <div className="p-2 rounded-lg" style={{ backgroundColor: `${color}12` }}>
          <Icon size={18} style={{ color }} />
        </div>
      </div>
    </div>
  );
}

function PipelineBar({ health }: { health: SystemHealth }) {
  const stages = [
    { label: 'Draft', count: health.content_draft, color: '#6b7280' },
    { label: 'Generating', count: health.content_generating, color: '#8b5cf6' },
    { label: 'Review', count: health.content_review, color: '#f59e0b' },
    { label: 'Approved', count: health.content_approved, color: '#22c55e' },
    { label: 'Publishing', count: health.content_publishing, color: '#3b82f6' },
    { label: 'Published', count: health.content_published, color: '#14b8a6' },
    { label: 'Failed', count: health.content_failed, color: '#ef4444' },
  ];
  const total = stages.reduce((s, st) => s + st.count, 0);

  return (
    <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
      <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
        <Layers size={16} className="text-cyan-400" />
        Content Pipeline
      </h3>
      {total === 0 ? (
        <p className="text-sm text-gray-600 text-center py-4">No content items yet</p>
      ) : (
        <>
          <div className="flex h-3 rounded-full overflow-hidden bg-gray-800 mb-3">
            {stages
              .filter((s) => s.count > 0)
              .map((s) => (
                <div
                  key={s.label}
                  className="h-full transition-all"
                  style={{
                    width: `${(s.count / total) * 100}%`,
                    backgroundColor: s.color,
                  }}
                  title={`${s.label}: ${s.count}`}
                />
              ))}
          </div>
          <div className="grid grid-cols-4 lg:grid-cols-7 gap-2">
            {stages.map((s) => (
              <div key={s.label} className="text-center">
                <p className="text-lg font-bold" style={{ color: s.color }}>
                  {s.count}
                </p>
                <p className="text-[10px] text-gray-500 uppercase tracking-wider">{s.label}</p>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function ActionCard({
  action,
  onComplete,
  onDismiss,
}: {
  action: OperatorAction;
  onComplete: () => void;
  onDismiss: () => void;
}) {
  const colorClass = priorityColors[action.priority] || priorityColors.medium;
  return (
    <div className={`border rounded-lg px-4 py-3 ${colorClass}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-bold uppercase tracking-wider opacity-80">
              {action.priority}
            </span>
            <span className="text-[10px] text-gray-500">{action.category}</span>
          </div>
          <p className="text-sm font-medium text-white truncate">{action.title}</p>
          {action.source_module && (
            <p className="text-[11px] text-gray-500 mt-0.5">from {action.source_module}</p>
          )}
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={onComplete}
            className="p-1.5 rounded-md hover:bg-green-500/20 text-green-400 transition"
            title="Complete"
          >
            <CheckCircle2 size={16} />
          </button>
          <button
            onClick={onDismiss}
            className="p-1.5 rounded-md hover:bg-gray-500/20 text-gray-500 transition"
            title="Dismiss"
          >
            <XCircle size={16} />
          </button>
        </div>
      </div>
      <p className="text-[11px] text-gray-600 mt-1">{timeAgo(action.created_at)}</p>
    </div>
  );
}

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
        <div className="flex items-center gap-2 mt-1">
          <span className="text-[10px] text-gray-600 uppercase">{event.event_domain}</span>
          {event.new_state && (
            <span className="text-[10px] text-gray-500">
              {event.previous_state && `${event.previous_state} → `}{event.new_state}
            </span>
          )}
        </div>
      </div>
      <span className="text-[11px] text-gray-600 shrink-0">{timeAgo(event.created_at)}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main Page                                                           */
/* ------------------------------------------------------------------ */

export default function DashboardOverviewPage() {
  const queryClient = useQueryClient();
  const [selectedBrandId, setSelectedBrandId] = useState('');

  // --- Data queries ---
  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) setSelectedBrandId(String(brands[0].id));
  }, [brands, selectedBrandId]);

  const { data: ctrl, isLoading: ctrlLoading } = useQuery({
    queryKey: ['control-layer-dashboard'],
    queryFn: () => controlLayerApi.dashboard().then((r) => r.data as ControlDashboard),
    refetchInterval: 15_000,
  });

  const { data: revenue } = useQuery({
    queryKey: ['analytics-revenue-dashboard', selectedBrandId],
    queryFn: () => analyticsApi.revenueDashboard(selectedBrandId).then((r) => r.data as RevenueDash),
    enabled: Boolean(selectedBrandId),
    refetchInterval: 30_000,
  });

  const { data: apiHealth } = useQuery({
    queryKey: ['health'],
    queryFn: () => healthApi.readyz().then((r) => r.data),
    refetchInterval: 30_000,
  });

  // --- Mutations ---
  const completeMut = useMutation({
    mutationFn: (actionId: string) => controlLayerApi.completeAction(actionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['control-layer-dashboard'] }),
  });

  const dismissMut = useMutation({
    mutationFn: (actionId: string) => controlLayerApi.dismissAction(actionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['control-layer-dashboard'] }),
  });

  const health = ctrl?.health;
  const actions = ctrl?.pending_actions || [];
  const events = ctrl?.recent_events || [];

  // --- Loading / Error ---
  if (brandsLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="animate-spin text-gray-600" size={32} />
      </div>
    );
  }

  if (brandsError) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Control Center</h1>
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl py-8 text-center text-red-300">
          Failed to load: {errMessage(brandsErr)}
        </div>
      </div>
    );
  }

  if (!brands?.length) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Control Center</h1>
        <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl text-center py-16">
          <Package className="mx-auto text-gray-700 mb-4" size={48} />
          <p className="text-gray-500 text-lg">No brands configured</p>
          <p className="text-gray-600 text-sm mt-2">Create a brand to activate the operating system</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-[1600px]">
      {/* ---- Header ---- */}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Control Center</h1>
          <p className="text-sm text-gray-500 mt-0.5">Real-time system state and operator actions</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            className="bg-gray-800 border border-gray-700 text-gray-300 rounded-lg px-3 py-1.5 text-sm"
            value={selectedBrandId}
            onChange={(e) => setSelectedBrandId(e.target.value)}
          >
            {brands.map((b) => (
              <option key={b.id} value={String(b.id)}>{b.name}</option>
            ))}
          </select>
          <div className="flex items-center gap-1.5">
            {apiHealth?.status === 'ready' ? (
              <span className="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 rounded-full px-2.5 py-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                System Online
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
            <p className="text-xs text-red-400/70 mt-0.5">
              {ctrl!.failed_jobs_24h > 0 && `${ctrl!.failed_jobs_24h} failed jobs in last 24h`}
            </p>
          </div>
        </div>
      )}

      {/* ---- Key Metrics Row ---- */}
      {health && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <MetricCard
            label="Revenue (30d)"
            value={fmtMoney(revenue?.gross_revenue || health.total_revenue_30d)}
            icon={DollarSign}
            color="#22c55e"
          />
          <MetricCard
            label="Content Items"
            value={fmtNum(health.total_content_items)}
            icon={Layers}
            color="#8b5cf6"
            sublabel={`${health.content_published} published`}
          />
          <MetricCard
            label="Accounts"
            value={fmtNum(health.total_accounts)}
            icon={Users}
            color="#3b82f6"
          />
          <MetricCard
            label="Pending Actions"
            value={health.actions_pending}
            icon={Clock}
            color={health.actions_critical > 0 ? '#ef4444' : '#f59e0b'}
            sublabel={health.actions_critical > 0 ? `${health.actions_critical} critical` : undefined}
          />
          <MetricCard
            label="Jobs Running"
            value={health.jobs_running}
            icon={Activity}
            color="#14b8a6"
            sublabel={`${health.jobs_pending} queued`}
          />
          <MetricCard
            label="Failed (24h)"
            value={health.jobs_failed_24h}
            icon={health.jobs_failed_24h > 0 ? Flame : CheckCircle2}
            color={health.jobs_failed_24h > 0 ? '#ef4444' : '#22c55e'}
            sublabel={`${health.jobs_completed_24h} completed`}
          />
        </div>
      )}

      {/* ---- Content Pipeline ---- */}
      {health && <PipelineBar health={health} />}

      {/* ---- Revenue + Intelligence Row ---- */}
      {health && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Revenue State */}
          <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <DollarSign size={16} className="text-emerald-400" />
              Revenue (30d)
            </h3>
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center">
                <p className="text-2xl font-bold text-emerald-400">{fmtMoney(health.total_revenue_30d)}</p>
                <p className="text-[10px] text-gray-500 uppercase tracking-wider">Total Revenue</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-red-400">{fmtMoney(health.total_cost_30d)}</p>
                <p className="text-[10px] text-gray-500 uppercase tracking-wider">Provider Cost</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold" style={{ color: (health.total_revenue_30d - health.total_cost_30d) >= 0 ? '#22c55e' : '#ef4444' }}>
                  {fmtMoney(health.total_revenue_30d - health.total_cost_30d)}
                </p>
                <p className="text-[10px] text-gray-500 uppercase tracking-wider">Net</p>
              </div>
            </div>
          </div>

          {/* Intelligence State */}
          {ctrl?.intelligence && (
            <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <Zap size={16} className="text-purple-400" />
                Intelligence
              </h3>
              <div className="grid grid-cols-4 gap-4">
                <div className="text-center">
                  <p className="text-2xl font-bold text-purple-400">{ctrl.intelligence.winning_patterns}</p>
                  <p className="text-[10px] text-gray-500 uppercase tracking-wider">Patterns</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-cyan-400">{ctrl.intelligence.active_decisions}</p>
                  <p className="text-[10px] text-gray-500 uppercase tracking-wider">Decisions</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-amber-400">{ctrl.intelligence.active_experiments}</p>
                  <p className="text-[10px] text-gray-500 uppercase tracking-wider">Experiments</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-red-400">{ctrl.intelligence.active_suppressions}</p>
                  <p className="text-[10px] text-gray-500 uppercase tracking-wider">Suppressions</p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ---- Governance & Memory Bar ---- */}
      {ctrl?.governance && (
        <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
            <Shield size={16} className="text-emerald-400" />
            Governance & Memory
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <p className="text-2xl font-bold" style={{ color: ctrl.governance.pending_approvals > 0 ? '#f59e0b' : '#22c55e' }}>
                {ctrl.governance.pending_approvals}
              </p>
              <p className="text-[10px] text-gray-500 uppercase tracking-wider">Pending Approvals</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold" style={{ color: ctrl.governance.open_alerts > 0 ? '#ef4444' : '#22c55e' }}>
                {ctrl.governance.open_alerts}
              </p>
              <p className="text-[10px] text-gray-500 uppercase tracking-wider">Gate Alerts</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-blue-400">{ctrl.governance.memory_entries}</p>
              <p className="text-[10px] text-gray-500 uppercase tracking-wider">Memory Entries</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-violet-400">{ctrl.governance.creative_atoms}</p>
              <p className="text-[10px] text-gray-500 uppercase tracking-wider">Creative Atoms</p>
            </div>
          </div>
        </div>
      )}

      {/* ---- (cleaned up legacy section) ---- */}
      {false && ctrl?.intelligence && (
        <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
            <Zap size={16} className="text-purple-400" />
            Intelligence Layer
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-purple-400">{ctrl.intelligence.winning_patterns}</p>
              <p className="text-[10px] text-gray-500 uppercase tracking-wider">Winning Patterns</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-cyan-400">{ctrl.intelligence.active_decisions}</p>
              <p className="text-[10px] text-gray-500 uppercase tracking-wider">Active Decisions</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-amber-400">{ctrl.intelligence.active_experiments}</p>
              <p className="text-[10px] text-gray-500 uppercase tracking-wider">Experiments</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-red-400">{ctrl.intelligence.active_suppressions}</p>
              <p className="text-[10px] text-gray-500 uppercase tracking-wider">Suppressions</p>
            </div>
          </div>
        </div>
      )}

      {/* ---- Two Column: Actions + Events ---- */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        {/* Pending Actions */}
        <div className="lg:col-span-2 bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Shield size={16} className="text-amber-400" />
              Pending Actions
            </h3>
            {actions.length > 0 && (
              <span className="text-xs text-gray-500">{actions.length} pending</span>
            )}
          </div>
          {actions.length === 0 ? (
            <div className="text-center py-8">
              <CheckCircle2 className="mx-auto text-emerald-500/50 mb-2" size={32} />
              <p className="text-sm text-gray-500">All clear — no actions needed</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
              {actions.map((a) => (
                <ActionCard
                  key={a.id}
                  action={a}
                  onComplete={() => completeMut.mutate(a.id)}
                  onDismiss={() => dismissMut.mutate(a.id)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Event Feed */}
        <div className="lg:col-span-3 bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Activity size={16} className="text-cyan-400" />
              System Activity
            </h3>
            {events.length > 0 && (
              <span className="text-xs text-gray-500">{events.length} events</span>
            )}
          </div>
          {events.length === 0 ? (
            <div className="text-center py-8">
              <Activity className="mx-auto text-gray-700 mb-2" size={32} />
              <p className="text-sm text-gray-500">No events yet — the system is starting up</p>
              <p className="text-xs text-gray-600 mt-1">Events will appear as workers execute and content flows through the pipeline</p>
            </div>
          ) : (
            <div className="space-y-0.5 max-h-[400px] overflow-y-auto pr-1">
              {events.map((e) => (
                <EventRow key={e.id} event={e} />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ---- System Status ---- */}
      {health && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white mb-3">Infrastructure</h3>
            <div className="space-y-2.5">
              <StatusRow label="API Server" ok={true} />
              <StatusRow label="Database" ok={apiHealth?.checks?.database ?? false} />
              <StatusRow label="Workers" ok={health.jobs_running >= 0} sublabel={
                health.jobs_running > 0 ? `${health.jobs_running} active` : 'Standby'
              } />
              <StatusRow label="Scheduler" ok={true} sublabel="Beat active" />
            </div>
          </div>
          <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white mb-3">Entities</h3>
            <div className="space-y-2.5">
              <StatusRow label="Brands" ok={true} sublabel={`${health.total_brands} active`} />
              <StatusRow label="Accounts" ok={health.total_accounts > 0} sublabel={`${health.total_accounts} configured`} />
              <StatusRow label="Offers" ok={health.total_offers > 0} sublabel={`${health.total_offers} in catalog`} />
              <StatusRow label="Content" ok={health.total_content_items > 0} sublabel={`${health.total_content_items} total`} />
            </div>
          </div>
          <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white mb-3">Operations (24h)</h3>
            <div className="space-y-2.5">
              <StatusRow label="Jobs Completed" ok={true} sublabel={fmtNum(health.jobs_completed_24h)} />
              <StatusRow label="Jobs Failed" ok={health.jobs_failed_24h === 0} sublabel={String(health.jobs_failed_24h)} warn={health.jobs_failed_24h > 0} />
              <StatusRow label="Actions Resolved" ok={true} sublabel={fmtNum(health.actions_completed_24h)} />
              <StatusRow label="Provider Cost" ok={true} sublabel={fmtMoney(health.total_cost_30d)} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

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
