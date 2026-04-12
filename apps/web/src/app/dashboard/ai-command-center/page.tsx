"use client";

import { useEffect, useState, useCallback } from "react";
import { useBrandId } from "@/hooks/useBrandId";
import { apiFetch } from "@/lib/api";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Brain,
  CheckCircle2,
  ChevronRight,
  Clock,
  Cpu,
  DollarSign,
  FlaskConical,
  Gauge,
  Layers,
  Minus,
  PieChart,
  RefreshCw,
  Server,
  Shield,
  TrendingUp,
  X,
  XCircle,
  Zap,
  ArrowUpRight,
  ArrowDownRight,
  Play,
  Pause,
  RotateCcw,
  Eye,
  Award,
  Target,
} from "lucide-react";

/* ──────────────────────────────────── Types ──────────────────────────────────── */

interface AIProviderStatus {
  provider: string;
  display_name: string;
  status: "healthy" | "degraded" | "down";
  circuit_breaker: "closed" | "half_open" | "open";
  current_load_pct: number;
  error_rate_pct: number;
  cost_per_unit: number;
  avg_latency_ms: number;
  requests_24h: number;
}

interface QualityScore {
  content_id: string;
  title: string;
  overall_score: number;
  passed: boolean;
  dimensions: { name: string; score: number; weight: number }[];
  evaluated_at: string;
}

interface QualityGateStats {
  total_evaluated: number;
  pass_rate_pct: number;
  avg_score: number;
  recent_scores: QualityScore[];
  dimension_averages: { name: string; avg_score: number }[];
}

interface Experiment {
  id: string;
  name: string;
  status: "running" | "paused" | "concluded";
  variant_a: string;
  variant_b: string;
  metric: string;
  sample_size_a: number;
  sample_size_b: number;
  lift_pct: number;
  confidence_pct: number;
  winner: "a" | "b" | null;
  started_at: string;
  days_running: number;
}

interface BudgetChannel {
  channel: string;
  allocated: number;
  spent: number;
  revenue: number;
  roi: number;
}

interface BudgetData {
  total_budget: number;
  total_spent: number;
  total_revenue: number;
  overall_roi: number;
  channels: BudgetChannel[];
  rebalance_recommendations: { action: string; from_channel: string; to_channel: string; amount: number; expected_roi_lift: number }[];
}

interface WorkerStatus {
  name: string;
  status: "active" | "idle" | "error" | "offline";
  active_tasks: number;
  completed_24h: number;
  failed_24h: number;
  avg_execution_ms: number;
}

interface SystemHealthData {
  workers: WorkerStatus[];
  queue_depths: { queue: string; depth: number; oldest_age_s: number }[];
  error_rate_1h: number;
  error_rate_24h: number;
  auto_recovery_actions: { action: string; target: string; result: string; timestamp: string }[];
}

interface ActivityEvent {
  id: string;
  type: "ai_call" | "quality_gate" | "experiment" | "budget" | "recovery" | "alert";
  message: string;
  timestamp: string;
  severity: "info" | "warning" | "error";
}

/* ──────────────────────────────────── Helpers ──────────────────────────────────── */

function StatusDot({ status }: { status: string }) {
  const colorMap: Record<string, string> = {
    healthy: "bg-green-400 shadow-[0_0_8px_rgba(74,222,128,0.6)]",
    active: "bg-green-400 shadow-[0_0_8px_rgba(74,222,128,0.6)]",
    closed: "bg-green-400 shadow-[0_0_8px_rgba(74,222,128,0.6)]",
    idle: "bg-gray-400",
    degraded: "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.6)] animate-pulse",
    half_open: "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.6)] animate-pulse",
    down: "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)] animate-pulse",
    open: "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)] animate-pulse",
    error: "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)] animate-pulse",
    offline: "bg-gray-600",
  };
  return <span className={`w-2 h-2 rounded-full inline-block flex-shrink-0 ${colorMap[status] ?? "bg-gray-600"}`} />;
}

function CircuitBreakerBadge({ state }: { state: string }) {
  const styles: Record<string, string> = {
    closed: "bg-green-500/10 text-green-400 border-green-500/20",
    half_open: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    open: "bg-red-500/10 text-red-400 border-red-500/20",
  };
  return (
    <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${styles[state] ?? "bg-gray-800 text-gray-500 border-gray-700"}`}>
      {state.replace("_", " ").toUpperCase()}
    </span>
  );
}

function MiniBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = Math.min((value / Math.max(max, 1)) * 100, 100);
  return (
    <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden flex-1">
      <div className={`h-full rounded-full ${color} transition-all duration-500`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function SectionHeader({ title, subtitle, icon: Icon }: { title: string; subtitle: string; icon: typeof Activity }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div>
        <h2 className="text-sm font-bold text-cyan-400/80 uppercase tracking-widest">{title}</h2>
        <p className="text-xs text-gray-500 mt-0.5 font-mono">{subtitle}</p>
      </div>
      <Icon className="w-4 h-4 text-gray-700" />
    </div>
  );
}

/* ──────────────────────────────────── Skeletons ──────────────────────────────────── */

function CardSkeleton({ h = "h-32" }: { h?: string }) {
  return <div className={`bg-gray-900/60 border border-gray-800/50 rounded-xl p-5 animate-pulse ${h}`} />;
}

function ErrorPanel({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="bg-red-950/20 border border-red-900/30 rounded-xl p-5 text-center">
      <AlertTriangle className="w-6 h-6 text-red-400 mx-auto mb-2" />
      <p className="text-sm text-red-300 mb-3">{message}</p>
      <button onClick={onRetry} className="inline-flex items-center gap-2 px-4 py-1.5 bg-red-900/40 border border-red-800/50 text-red-300 rounded-lg text-xs hover:bg-red-900/60 transition-colors">
        <RefreshCw className="w-3 h-3" /> Retry
      </button>
    </div>
  );
}

/* ──────────────────────────────────── Section Components ──────────────────────────────────── */

function AIProviderGrid({ providers }: { providers: AIProviderStatus[] }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
      {providers.map((p) => {
        const borderColor = p.status === "healthy"
          ? "border-green-500/20 hover:border-green-400/40"
          : p.status === "degraded"
            ? "border-amber-500/30 hover:border-amber-400/50"
            : "border-red-500/40 hover:border-red-400/60";

        return (
          <div key={p.provider} className={`bg-gray-900/70 border rounded-xl p-4 backdrop-blur-sm transition-all ${borderColor}`}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <StatusDot status={p.status} />
                <span className="text-sm font-bold text-white">{p.display_name}</span>
              </div>
              <CircuitBreakerBadge state={p.circuit_breaker} />
            </div>

            <div className="space-y-2.5">
              <div>
                <div className="flex items-center justify-between text-[10px] mb-1">
                  <span className="text-gray-500 font-mono">LOAD</span>
                  <span className={`font-mono ${p.current_load_pct > 80 ? "text-red-400" : p.current_load_pct > 60 ? "text-amber-400" : "text-green-400"}`}>
                    {p.current_load_pct}%
                  </span>
                </div>
                <MiniBar value={p.current_load_pct} max={100} color={p.current_load_pct > 80 ? "bg-red-400" : p.current_load_pct > 60 ? "bg-amber-400" : "bg-green-400"} />
              </div>

              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[10px]">
                <div className="flex justify-between">
                  <span className="text-gray-500">ERR RATE</span>
                  <span className={`font-mono ${p.error_rate_pct > 5 ? "text-red-400" : "text-gray-300"}`}>{p.error_rate_pct.toFixed(1)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">COST/UNIT</span>
                  <span className="text-gray-300 font-mono">${p.cost_per_unit.toFixed(4)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">LATENCY</span>
                  <span className="text-gray-300 font-mono">{p.avg_latency_ms}ms</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">24H REQS</span>
                  <span className="text-gray-300 font-mono">{p.requests_24h.toLocaleString()}</span>
                </div>
              </div>
            </div>
          </div>
        );
      })}
      {providers.length === 0 && <p className="text-gray-600 text-xs col-span-3">No AI providers configured</p>}
    </div>
  );
}

function QualityGatePanel({ stats }: { stats: QualityGateStats }) {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-gray-800/40 rounded-lg p-3 text-center">
          <p className="text-[10px] text-gray-500 font-mono">EVALUATED</p>
          <p className="text-xl font-black text-white mt-1">{stats.total_evaluated}</p>
        </div>
        <div className="bg-gray-800/40 rounded-lg p-3 text-center">
          <p className="text-[10px] text-gray-500 font-mono">PASS RATE</p>
          <p className={`text-xl font-black mt-1 ${stats.pass_rate_pct >= 80 ? "text-green-400" : stats.pass_rate_pct >= 60 ? "text-amber-400" : "text-red-400"}`}>
            {stats.pass_rate_pct.toFixed(1)}%
          </p>
        </div>
        <div className="bg-gray-800/40 rounded-lg p-3 text-center">
          <p className="text-[10px] text-gray-500 font-mono">AVG SCORE</p>
          <p className="text-xl font-black text-cyan-300 mt-1">{stats.avg_score.toFixed(1)}</p>
        </div>
      </div>

      {stats.dimension_averages.length > 0 && (
        <div>
          <p className="text-[10px] text-gray-500 font-mono uppercase mb-2">Dimension Breakdown</p>
          <div className="space-y-2">
            {stats.dimension_averages.map((d) => (
              <div key={d.name} className="flex items-center gap-3">
                <span className="text-xs text-gray-400 w-28 truncate">{d.name}</span>
                <MiniBar value={d.avg_score} max={100} color={d.avg_score >= 80 ? "bg-green-400" : d.avg_score >= 60 ? "bg-amber-400" : "bg-red-400"} />
                <span className="text-xs font-mono text-gray-300 w-8 text-right">{d.avg_score.toFixed(0)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {stats.recent_scores.length > 0 && (
        <div>
          <p className="text-[10px] text-gray-500 font-mono uppercase mb-2">Recent Evaluations</p>
          <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
            {stats.recent_scores.slice(0, 8).map((s) => (
              <div key={s.content_id} className="flex items-center gap-3 bg-gray-800/20 rounded-lg px-3 py-2">
                {s.passed ? <CheckCircle2 className="w-3.5 h-3.5 text-green-400 flex-shrink-0" /> : <XCircle className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />}
                <span className="text-xs text-white truncate flex-1">{s.title}</span>
                <span className={`text-xs font-mono font-bold ${s.passed ? "text-green-400" : "text-red-400"}`}>{s.overall_score.toFixed(0)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ExperimentPanel({ experiments }: { experiments: Experiment[] }) {
  const statusColors: Record<string, string> = {
    running: "bg-green-500/10 text-green-400 border-green-500/20",
    paused: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    concluded: "bg-gray-700/30 text-gray-400 border-gray-600/30",
  };

  return (
    <div className="space-y-3">
      {experiments.map((exp) => {
        const sigPct = Math.min(exp.confidence_pct, 100);
        const significant = exp.confidence_pct >= 95;

        return (
          <div key={exp.id} className="bg-gray-800/30 border border-gray-800/50 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <FlaskConical className="w-3.5 h-3.5 text-purple-400" />
                <span className="text-sm text-white font-medium">{exp.name}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${statusColors[exp.status]}`}>
                  {exp.status.toUpperCase()}
                </span>
                {exp.status === "running" && (
                  <span className="text-[10px] text-gray-500 font-mono">{exp.days_running}d</span>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 mb-3">
              <div className="bg-gray-900/50 rounded px-3 py-2">
                <p className="text-[9px] text-gray-500 font-mono">VARIANT A</p>
                <p className="text-xs text-white mt-0.5">{exp.variant_a}</p>
                <p className="text-[10px] text-gray-500 font-mono mt-1">n={exp.sample_size_a.toLocaleString()}</p>
              </div>
              <div className="bg-gray-900/50 rounded px-3 py-2">
                <p className="text-[9px] text-gray-500 font-mono">VARIANT B</p>
                <p className="text-xs text-white mt-0.5">{exp.variant_b}</p>
                <p className="text-[10px] text-gray-500 font-mono mt-1">n={exp.sample_size_b.toLocaleString()}</p>
              </div>
            </div>

            <div className="mb-3">
              <div className="flex items-center justify-between text-[10px] mb-1">
                <span className="text-gray-500 font-mono">STATISTICAL SIGNIFICANCE</span>
                <span className={`font-mono font-bold ${significant ? "text-green-400" : "text-amber-400"}`}>{sigPct.toFixed(1)}%</span>
              </div>
              <div className="h-2 bg-gray-800 rounded-full overflow-hidden relative">
                <div className={`h-full rounded-full transition-all duration-700 ${significant ? "bg-green-400" : "bg-amber-400"}`} style={{ width: `${sigPct}%` }} />
                <div className="absolute top-0 bottom-0 left-[95%] w-px bg-white/20" />
              </div>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">Lift:</span>
                <span className={`text-sm font-bold font-mono ${exp.lift_pct > 0 ? "text-green-400" : exp.lift_pct < 0 ? "text-red-400" : "text-gray-400"}`}>
                  {exp.lift_pct > 0 ? "+" : ""}{exp.lift_pct.toFixed(2)}%
                </span>
                <span className="text-xs text-gray-500">on {exp.metric}</span>
              </div>
              {exp.winner && (
                <div className="flex items-center gap-1.5">
                  <Award className="w-3.5 h-3.5 text-amber-400" />
                  <span className="text-xs font-bold text-amber-400">Winner: {exp.winner.toUpperCase()}</span>
                </div>
              )}
            </div>
          </div>
        );
      })}
      {experiments.length === 0 && (
        <div className="text-center py-6">
          <FlaskConical className="w-6 h-6 text-gray-700 mx-auto mb-2" />
          <p className="text-xs text-gray-600">No active experiments</p>
        </div>
      )}
    </div>
  );
}

function BudgetPanel({ data }: { data: BudgetData }) {
  const maxRev = Math.max(...data.channels.map((c) => c.revenue), 1);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: "TOTAL BUDGET", value: `$${data.total_budget.toLocaleString()}`, color: "text-white" },
          { label: "TOTAL SPENT", value: `$${data.total_spent.toLocaleString()}`, color: "text-gray-300" },
          { label: "TOTAL REVENUE", value: `$${data.total_revenue.toLocaleString()}`, color: "text-cyan-300" },
          { label: "OVERALL ROI", value: `${data.overall_roi.toFixed(1)}x`, color: data.overall_roi >= 2 ? "text-green-400" : data.overall_roi >= 1 ? "text-amber-400" : "text-red-400" },
        ].map((m) => (
          <div key={m.label} className="bg-gray-800/40 rounded-lg p-3 text-center">
            <p className="text-[10px] text-gray-500 font-mono">{m.label}</p>
            <p className={`text-lg font-black mt-1 ${m.color}`}>{m.value}</p>
          </div>
        ))}
      </div>

      <div>
        <p className="text-[10px] text-gray-500 font-mono uppercase mb-2">ROI by Channel</p>
        <div className="space-y-2">
          {data.channels.sort((a, b) => b.roi - a.roi).map((ch) => (
            <div key={ch.channel} className="flex items-center gap-3">
              <span className="text-xs text-gray-400 w-24 truncate">{ch.channel}</span>
              <div className="flex-1 h-5 bg-gray-800 rounded-full overflow-hidden relative">
                <div className="h-full bg-gradient-to-r from-cyan-600 to-cyan-400 rounded-full transition-all" style={{ width: `${(ch.revenue / maxRev) * 100}%` }} />
              </div>
              <span className={`text-xs font-mono font-bold w-12 text-right ${ch.roi >= 2 ? "text-green-400" : ch.roi >= 1 ? "text-amber-400" : "text-red-400"}`}>
                {ch.roi.toFixed(1)}x
              </span>
              <span className="text-[10px] text-gray-500 font-mono w-20 text-right">${ch.revenue.toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>

      {data.rebalance_recommendations.length > 0 && (
        <div>
          <p className="text-[10px] text-gray-500 font-mono uppercase mb-2">Rebalance Recommendations</p>
          <div className="space-y-2">
            {data.rebalance_recommendations.map((rec, i) => (
              <div key={i} className="bg-cyan-950/15 border border-cyan-900/20 rounded-lg px-4 py-3 flex items-center gap-3">
                <Zap className="w-4 h-4 text-cyan-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-white">{rec.action}</p>
                  <p className="text-[10px] text-gray-500 font-mono mt-0.5">
                    {rec.from_channel} → {rec.to_channel} • ${rec.amount.toLocaleString()}
                  </p>
                </div>
                <span className="text-xs font-mono text-green-400 flex-shrink-0">+{rec.expected_roi_lift.toFixed(1)}% ROI</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function SystemHealthPanel({ data }: { data: SystemHealthData }) {
  const workerStatusColor = (s: string) => {
    if (s === "active") return "border-green-500/20";
    if (s === "idle") return "border-gray-700/50";
    if (s === "error") return "border-red-500/30";
    return "border-gray-800/50";
  };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-gray-800/40 rounded-lg p-3 text-center">
          <p className="text-[10px] text-gray-500 font-mono">ERROR RATE (1H)</p>
          <p className={`text-xl font-black mt-1 ${data.error_rate_1h > 5 ? "text-red-400" : data.error_rate_1h > 2 ? "text-amber-400" : "text-green-400"}`}>
            {data.error_rate_1h.toFixed(2)}%
          </p>
        </div>
        <div className="bg-gray-800/40 rounded-lg p-3 text-center">
          <p className="text-[10px] text-gray-500 font-mono">ERROR RATE (24H)</p>
          <p className={`text-xl font-black mt-1 ${data.error_rate_24h > 5 ? "text-red-400" : data.error_rate_24h > 2 ? "text-amber-400" : "text-green-400"}`}>
            {data.error_rate_24h.toFixed(2)}%
          </p>
        </div>
      </div>

      <div>
        <p className="text-[10px] text-gray-500 font-mono uppercase mb-2">Celery Workers</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {data.workers.map((w) => (
            <div key={w.name} className={`border rounded-lg px-3 py-2.5 bg-gray-900/50 ${workerStatusColor(w.status)}`}>
              <div className="flex items-center gap-2 mb-1.5">
                <StatusDot status={w.status} />
                <span className="text-xs text-white font-medium truncate">{w.name}</span>
              </div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px]">
                <div className="flex justify-between"><span className="text-gray-500">ACTIVE</span><span className="text-gray-300 font-mono">{w.active_tasks}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">24H OK</span><span className="text-green-400 font-mono">{w.completed_24h}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">24H FAIL</span><span className={`font-mono ${w.failed_24h > 0 ? "text-red-400" : "text-gray-400"}`}>{w.failed_24h}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">AVG MS</span><span className="text-gray-300 font-mono">{w.avg_execution_ms}</span></div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {data.queue_depths.length > 0 && (
        <div>
          <p className="text-[10px] text-gray-500 font-mono uppercase mb-2">Queue Depths</p>
          <div className="space-y-1.5">
            {data.queue_depths.map((q) => (
              <div key={q.queue} className="flex items-center gap-3">
                <span className="text-xs text-gray-400 w-32 truncate font-mono">{q.queue}</span>
                <MiniBar value={q.depth} max={Math.max(...data.queue_depths.map((x) => x.depth), 100)} color={q.depth > 50 ? "bg-amber-400" : "bg-cyan-400"} />
                <span className="text-xs font-mono text-gray-300 w-8 text-right">{q.depth}</span>
                {q.oldest_age_s > 300 && <span className="text-[9px] text-amber-400 font-mono">{Math.round(q.oldest_age_s / 60)}m old</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {data.auto_recovery_actions.length > 0 && (
        <div>
          <p className="text-[10px] text-gray-500 font-mono uppercase mb-2">Auto-Recovery Actions</p>
          <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
            {data.auto_recovery_actions.map((a, i) => (
              <div key={i} className="flex items-start gap-2 bg-gray-800/20 rounded px-3 py-2">
                <RotateCcw className="w-3 h-3 text-cyan-400 mt-0.5 flex-shrink-0" />
                <div className="min-w-0">
                  <p className="text-xs text-white">{a.action}: {a.target}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className={`text-[9px] font-mono ${a.result === "success" ? "text-green-400" : "text-red-400"}`}>{a.result}</span>
                    <span className="text-[9px] text-gray-500 font-mono">{new Date(a.timestamp).toLocaleTimeString()}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ActivityFeed({ events }: { events: ActivityEvent[] }) {
  const iconMap: Record<string, typeof Activity> = {
    ai_call: Brain,
    quality_gate: Shield,
    experiment: FlaskConical,
    budget: DollarSign,
    recovery: RotateCcw,
    alert: AlertTriangle,
  };
  const sevColor: Record<string, string> = {
    info: "text-gray-400",
    warning: "text-amber-400",
    error: "text-red-400",
  };

  return (
    <div className="space-y-1 max-h-[600px] overflow-y-auto pr-1">
      {events.map((ev) => {
        const Icon = iconMap[ev.type] ?? Activity;
        return (
          <div key={ev.id} className="flex items-start gap-2.5 px-3 py-2 hover:bg-gray-800/20 rounded transition-colors">
            <Icon className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${sevColor[ev.severity]}`} />
            <div className="min-w-0 flex-1">
              <p className="text-xs text-gray-300 leading-relaxed">{ev.message}</p>
              <span className="text-[9px] text-gray-600 font-mono">{new Date(ev.timestamp).toLocaleTimeString()}</span>
            </div>
          </div>
        );
      })}
      {events.length === 0 && (
        <div className="text-center py-8">
          <Activity className="w-5 h-5 text-gray-700 mx-auto mb-2" />
          <p className="text-xs text-gray-600">No recent activity</p>
        </div>
      )}
    </div>
  );
}

/* ──────────────────────────────────── Main Page ──────────────────────────────────── */

export default function AICommandCenterPage() {
  const brandId = useBrandId();

  const [providers, setProviders] = useState<AIProviderStatus[]>([]);
  const [qualityGate, setQualityGate] = useState<QualityGateStats | null>(null);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [budget, setBudget] = useState<BudgetData | null>(null);
  const [systemHealth, setSystemHealth] = useState<SystemHealthData | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);

  const [loading, setLoading] = useState({
    providers: true,
    quality: true,
    experiments: true,
    budget: true,
    health: true,
    activity: true,
  });
  const [errors, setErrors] = useState({
    providers: "",
    quality: "",
    experiments: "",
    budget: "",
    health: "",
    activity: "",
  });

  const setLoadingKey = (key: keyof typeof loading, val: boolean) => setLoading((p) => ({ ...p, [key]: val }));
  const setErrorKey = (key: keyof typeof errors, val: string) => setErrors((p) => ({ ...p, [key]: val }));

  const fetchProviders = useCallback(async () => {
    if (!brandId) return;
    setLoadingKey("providers", true);
    setErrorKey("providers", "");
    try {
      const raw = await apiFetch<any>(`/api/v1/brands/${brandId}/ai-command/providers`);
      setProviders(Array.isArray(raw) ? raw : []);
    } catch (e: any) { setErrorKey("providers", e.message || "Failed"); }
    finally { setLoadingKey("providers", false); }
  }, [brandId]);

  const fetchQuality = useCallback(async () => {
    if (!brandId) return;
    setLoadingKey("quality", true);
    setErrorKey("quality", "");
    try {
      setQualityGate(await apiFetch<QualityGateStats>(`/api/v1/brands/${brandId}/ai-command/quality-gate`));
    } catch (e: any) { setErrorKey("quality", e.message || "Failed"); }
    finally { setLoadingKey("quality", false); }
  }, [brandId]);

  const fetchExperiments = useCallback(async () => {
    if (!brandId) return;
    setLoadingKey("experiments", true);
    setErrorKey("experiments", "");
    try {
      const raw = await apiFetch<any>(`/api/v1/brands/${brandId}/ai-command/experiments`);
      setExperiments(Array.isArray(raw) ? raw : []);
    } catch (e: any) { setErrorKey("experiments", e.message || "Failed"); }
    finally { setLoadingKey("experiments", false); }
  }, [brandId]);

  const fetchBudget = useCallback(async () => {
    if (!brandId) return;
    setLoadingKey("budget", true);
    setErrorKey("budget", "");
    try {
      setBudget(await apiFetch<BudgetData>(`/api/v1/brands/${brandId}/ai-command/budget`));
    } catch (e: any) { setErrorKey("budget", e.message || "Failed"); }
    finally { setLoadingKey("budget", false); }
  }, [brandId]);

  const fetchHealth = useCallback(async () => {
    if (!brandId) return;
    setLoadingKey("health", true);
    setErrorKey("health", "");
    try {
      setSystemHealth(await apiFetch<SystemHealthData>(`/api/v1/brands/${brandId}/ai-command/system-health`));
    } catch (e: any) { setErrorKey("health", e.message || "Failed"); }
    finally { setLoadingKey("health", false); }
  }, [brandId]);

  const fetchActivity = useCallback(async () => {
    if (!brandId) return;
    setLoadingKey("activity", true);
    setErrorKey("activity", "");
    try {
      const raw = await apiFetch<any>(`/api/v1/brands/${brandId}/ai-command/activity`);
      setActivity(Array.isArray(raw) ? raw : []);
    } catch (e: any) { setErrorKey("activity", e.message || "Failed"); }
    finally { setLoadingKey("activity", false); }
  }, [brandId]);

  const fetchAll = useCallback(() => {
    fetchProviders();
    fetchQuality();
    fetchExperiments();
    fetchBudget();
    fetchHealth();
    fetchActivity();
  }, [fetchProviders, fetchQuality, fetchExperiments, fetchBudget, fetchHealth, fetchActivity]);

  useEffect(() => {
    if (!brandId) return;
    fetchAll();
  }, [brandId, fetchAll]);

  const healthySystems = providers.filter((p) => p.status === "healthy").length;
  const totalSystems = providers.length;
  const overallHealth = totalSystems > 0 ? Math.round((healthySystems / totalSystems) * 100) : 0;

  if (!brandId) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center space-y-4">
          <Brain className="w-12 h-12 text-gray-700 mx-auto" />
          <h2 className="text-xl font-bold text-white">No Brand Selected</h2>
          <p className="text-gray-500 text-sm max-w-md">Create a brand first, then return here to access the AI Command Center.</p>
          <a href="/dashboard/accounts" className="inline-flex items-center gap-2 px-5 py-2.5 bg-cyan-600 text-white rounded-lg text-sm font-medium hover:bg-cyan-500 transition-colors">
            Manage Accounts
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white -m-8 p-6">
      {/* ─── HEADER + SYSTEM HEALTH BAR ─── */}
      <div className="border-b border-purple-900/30 pb-4 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-black tracking-tight bg-gradient-to-r from-purple-400 via-pink-500 to-cyan-400 bg-clip-text text-transparent">
              AI COMMAND CENTER
            </h1>
            <p className="text-gray-500 text-xs mt-1 font-mono">GOD-MODE CONTROL • AI ORCHESTRATION • LIVE TELEMETRY</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={fetchAll}
              className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-xs text-gray-300 hover:text-white hover:border-gray-600 transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Refresh
            </button>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-purple-400 shadow-[0_0_8px_rgba(192,132,252,0.8)] animate-pulse" />
              <span className="text-purple-400 text-xs font-mono">ACTIVE</span>
            </div>
          </div>
        </div>

        {/* System health indicators */}
        <div className="flex items-center gap-6 mt-4">
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-gray-500 font-mono">SYSTEM HEALTH</span>
            <div className="w-24 h-2 bg-gray-800 rounded-full overflow-hidden">
              <div className={`h-full rounded-full transition-all ${overallHealth >= 80 ? "bg-green-400" : overallHealth >= 50 ? "bg-amber-400" : "bg-red-400"}`} style={{ width: `${overallHealth}%` }} />
            </div>
            <span className={`text-xs font-mono font-bold ${overallHealth >= 80 ? "text-green-400" : overallHealth >= 50 ? "text-amber-400" : "text-red-400"}`}>{overallHealth}%</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-gray-500 font-mono">PROVIDERS</span>
            <span className="text-xs font-mono text-white">{healthySystems}/{totalSystems} <span className="text-green-400">OK</span></span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-gray-500 font-mono">ERR RATE</span>
            <span className={`text-xs font-mono font-bold ${(systemHealth?.error_rate_1h ?? 0) > 5 ? "text-red-400" : "text-green-400"}`}>
              {(systemHealth?.error_rate_1h ?? 0).toFixed(2)}%
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-gray-500 font-mono">EXPERIMENTS</span>
            <span className="text-xs font-mono text-white">{experiments.filter((e) => e.status === "running").length} running</span>
          </div>
        </div>
      </div>

      {/* ─── MAIN SPLIT LAYOUT ─── */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
        {/* LEFT PANEL: Command sections (3 cols) */}
        <div className="xl:col-span-3 space-y-6">
          {/* AI Provider Health */}
          <section className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-6 backdrop-blur-sm">
            <SectionHeader title="AI Model Status" subtitle="Real-time provider health and circuit breaker states" icon={Cpu} />
            {loading.providers ? (
              <div className="grid grid-cols-3 gap-3">
                <CardSkeleton h="h-36" />
                <CardSkeleton h="h-36" />
                <CardSkeleton h="h-36" />
              </div>
            ) : errors.providers ? (
              <ErrorPanel message={errors.providers} onRetry={fetchProviders} />
            ) : (
              <AIProviderGrid providers={providers} />
            )}
          </section>

          {/* Quality Gate + Experiments (2-col) */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <section className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-6 backdrop-blur-sm">
              <SectionHeader title="Quality Gate Dashboard" subtitle="Content quality scoring and pass rates" icon={Shield} />
              {loading.quality ? <CardSkeleton h="h-64" /> : errors.quality ? <ErrorPanel message={errors.quality} onRetry={fetchQuality} /> : qualityGate ? <QualityGatePanel stats={qualityGate} /> : null}
            </section>

            <section className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-6 backdrop-blur-sm">
              <SectionHeader title="Experiment Control" subtitle="A/B tests with statistical significance tracking" icon={FlaskConical} />
              {loading.experiments ? <CardSkeleton h="h-64" /> : errors.experiments ? <ErrorPanel message={errors.experiments} onRetry={fetchExperiments} /> : <ExperimentPanel experiments={experiments} />}
            </section>
          </div>

          {/* Budget Optimization */}
          <section className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-6 backdrop-blur-sm">
            <SectionHeader title="Budget Optimization" subtitle="Channel allocation, ROI tracking, and rebalance recommendations" icon={PieChart} />
            {loading.budget ? <CardSkeleton h="h-48" /> : errors.budget ? <ErrorPanel message={errors.budget} onRetry={fetchBudget} /> : budget ? <BudgetPanel data={budget} /> : null}
          </section>

          {/* System Health */}
          <section className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-6 backdrop-blur-sm">
            <SectionHeader title="System Health" subtitle="Worker status, queue depths, error rates, auto-recovery" icon={Server} />
            {loading.health ? <CardSkeleton h="h-64" /> : errors.health ? <ErrorPanel message={errors.health} onRetry={fetchHealth} /> : systemHealth ? <SystemHealthPanel data={systemHealth} /> : null}
          </section>
        </div>

        {/* RIGHT PANEL: Activity Feed (1 col) */}
        <div className="xl:col-span-1">
          <div className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-4 backdrop-blur-sm sticky top-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-sm font-bold text-purple-400/80 uppercase tracking-widest">Live Activity</h2>
                <p className="text-[10px] text-gray-500 font-mono mt-0.5">{activity.length} events</p>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse" />
                <span className="text-[9px] text-purple-400 font-mono">STREAMING</span>
              </div>
            </div>
            {loading.activity ? (
              <div className="space-y-2">
                {Array.from({ length: 8 }, (_, i) => (
                  <div key={i} className="flex gap-2 animate-pulse">
                    <div className="w-3.5 h-3.5 bg-gray-800 rounded" />
                    <div className="flex-1 space-y-1">
                      <div className="h-3 bg-gray-800 rounded w-full" />
                      <div className="h-2 bg-gray-800/60 rounded w-16" />
                    </div>
                  </div>
                ))}
              </div>
            ) : errors.activity ? (
              <ErrorPanel message={errors.activity} onRetry={fetchActivity} />
            ) : (
              <ActivityFeed events={activity} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
