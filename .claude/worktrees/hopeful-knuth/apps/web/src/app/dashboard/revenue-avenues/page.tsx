"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useBrandId } from "@/hooks/useBrandId";
import { apiFetch } from "@/lib/api";
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  Gauge,
  Target,
  Zap,
  AlertTriangle,
  RefreshCw,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  BarChart3,
  Activity,
  Shield,
  ChevronRight,
  Layers,
  Crown,
  Users,
  Package,
  Briefcase,
  PieChart,
  Rocket,
} from "lucide-react";

/* ──────────────────────────────────── Types ──────────────────────────────────── */

interface SaaSMetrics {
  mrr: number;
  arr: number;
  net_new_mrr: number;
  new_mrr: number;
  churned_mrr: number;
  expansion_mrr: number;
  contraction_mrr: number;
  active_subscriptions: number;
  new_subscriptions_30d: number;
  churned_subscriptions_30d: number;
  gross_churn_rate: number;
  net_revenue_retention: number;
  ltv: number;
  quick_ratio: number;
  avg_mrr_per_customer: number;
  plan_breakdown: Record<string, { count: number; mrr: number }>;
  status: string;
}

interface AvenueRanking {
  avenue_key: string;
  label: string;
  type: string;
  current_monthly_revenue: number;
  potential_monthly_revenue: number;
  margin: number;
  setup_effort: string;
  time_to_revenue_days: number;
  roi_score: number;
  active_opportunities: number;
  tier: "gold" | "silver" | "standard";
}

interface PipelineDeal {
  id: string;
  customer_name: string;
  deal_value: number;
  stage: string;
  product_type: string;
  probability: number;
  weighted_value: number;
  score: number;
  days_stale: number;
  interactions: number;
  expected_close: string | null;
  needs_attention: boolean;
}

interface PipelineData {
  status: string;
  summary: {
    total_open_deals: number;
    total_pipeline_value: number;
    weighted_pipeline_value: number;
    velocity_30d: number;
    avg_deal_size: number;
    win_rate_30d: number;
  };
  bottleneck: { stage: string; avg_days: number; deals_stuck: number } | null;
  stages: Record<string, { count: number; total_value: number; weighted_value: number; avg_days_in_stage: number }>;
  deals: PipelineDeal[];
}

interface RevenueStack {
  status: string;
  total_monthly_revenue: number;
  recurring_monthly: number;
  one_time_monthly: number;
  recurring_pct: number;
  active_streams: number;
  diversification_score: number;
  vulnerability: string;
  stack: Record<string, { monthly: number; type: string }>;
}

interface ExpansionOpp {
  subscription_id: string;
  customer_id: string;
  customer_name: string;
  current_plan: string;
  current_mrr: number;
  opportunity_type: string;
  expected_mrr_delta: number;
  probability: number;
  expected_value: number;
  tenure_days: number;
}

interface ExpansionData {
  status: string;
  total_opportunities: number;
  total_expected_expansion: number;
  opportunities: ExpansionOpp[];
}

interface RankingsData {
  status: string;
  total_avenues: number;
  rankings: AvenueRanking[];
}

/* ──────────────────────────────────── Skeletons ──────────────────────────────────── */

function CardSkeleton() {
  return (
    <div className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-5 animate-pulse">
      <div className="h-3 w-24 bg-gray-700 rounded mb-3" />
      <div className="h-8 w-32 bg-gray-700 rounded mb-2" />
      <div className="h-3 w-20 bg-gray-800 rounded" />
    </div>
  );
}

function SectionSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-6 animate-pulse">
      <div className="h-4 w-48 bg-gray-700 rounded mb-6" />
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex gap-4 mb-4">
          <div className="h-10 w-10 bg-gray-800 rounded-lg" />
          <div className="flex-1 space-y-2">
            <div className="h-3 w-full bg-gray-800 rounded" />
            <div className="h-3 w-2/3 bg-gray-800/60 rounded" />
          </div>
          <div className="h-6 w-16 bg-gray-800 rounded" />
        </div>
      ))}
    </div>
  );
}

/* ──────────────────────────────────── Helpers ──────────────────────────────────── */

function ErrorPanel({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="bg-red-950/20 border border-red-900/30 rounded-xl p-6 text-center">
      <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-3" />
      <p className="text-sm text-red-300 mb-3">{message}</p>
      <button onClick={onRetry} className="inline-flex items-center gap-2 px-4 py-2 bg-red-900/40 border border-red-800/50 text-red-300 rounded-lg text-sm hover:bg-red-900/60 transition-colors">
        <RefreshCw className="w-3.5 h-3.5" /> Retry
      </button>
    </div>
  );
}

function MetricCard({ label, value, subtitle, icon: Icon, trend, trendValue, accentColor }: {
  label: string;
  value: string;
  subtitle?: string;
  icon: typeof DollarSign;
  trend?: "up" | "down" | "flat";
  trendValue?: string;
  accentColor: string;
}) {
  const styles: Record<string, { border: string; glow: string; iconBg: string; value: string }> = {
    cyan: { border: "border-cyan-500/30 hover:border-cyan-400/50", glow: "shadow-[0_0_20px_rgba(34,211,238,0.08)]", iconBg: "bg-cyan-500/10 text-cyan-400", value: "text-cyan-300" },
    green: { border: "border-green-500/30 hover:border-green-400/50", glow: "shadow-[0_0_20px_rgba(34,197,94,0.08)]", iconBg: "bg-green-500/10 text-green-400", value: "text-green-300" },
    purple: { border: "border-purple-500/30 hover:border-purple-400/50", glow: "shadow-[0_0_20px_rgba(168,85,247,0.08)]", iconBg: "bg-purple-500/10 text-purple-400", value: "text-purple-300" },
    amber: { border: "border-amber-500/30 hover:border-amber-400/50", glow: "shadow-[0_0_20px_rgba(245,158,11,0.08)]", iconBg: "bg-amber-500/10 text-amber-400", value: "text-amber-300" },
    rose: { border: "border-rose-500/30 hover:border-rose-400/50", glow: "shadow-[0_0_20px_rgba(244,63,94,0.08)]", iconBg: "bg-rose-500/10 text-rose-400", value: "text-rose-300" },
  };
  const s = styles[accentColor] || styles.cyan;

  return (
    <div className={`bg-gray-900/70 border rounded-xl p-5 backdrop-blur-sm transition-all duration-300 ${s.border} ${s.glow}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] text-gray-500 font-mono uppercase tracking-wider">{label}</span>
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${s.iconBg}`}>
          <Icon className="w-4 h-4" />
        </div>
      </div>
      <p className={`text-2xl font-black tracking-tight ${s.value}`}>{value}</p>
      <div className="flex items-center gap-2 mt-2">
        {trend && (
          <span className={`inline-flex items-center gap-0.5 text-xs font-semibold ${trend === "up" ? "text-green-400" : trend === "down" ? "text-red-400" : "text-gray-400"}`}>
            {trend === "up" ? <ArrowUpRight className="w-3.5 h-3.5" /> : trend === "down" ? <ArrowDownRight className="w-3.5 h-3.5" /> : <Minus className="w-3.5 h-3.5" />}
            {trendValue}
          </span>
        )}
        {subtitle && <span className="text-[10px] text-gray-500">{subtitle}</span>}
      </div>
    </div>
  );
}

const STAGE_ORDER = ["awareness", "interest", "consideration", "proposal", "negotiation"];
const STAGE_COLORS: Record<string, string> = {
  awareness: "bg-blue-500/20 border-blue-500/30 text-blue-300",
  interest: "bg-cyan-500/20 border-cyan-500/30 text-cyan-300",
  consideration: "bg-purple-500/20 border-purple-500/30 text-purple-300",
  proposal: "bg-amber-500/20 border-amber-500/30 text-amber-300",
  negotiation: "bg-green-500/20 border-green-500/30 text-green-300",
};

/* ──────────────────────────────────── Avenue Rankings ──────────────────────────────────── */

function AvenueRankingsSection({ rankings }: { rankings: AvenueRanking[] }) {
  const tierBorder: Record<string, string> = {
    gold: "border-amber-400/40 bg-amber-950/10",
    silver: "border-gray-400/30 bg-gray-800/20",
    standard: "border-gray-700/30 bg-gray-900/30",
  };
  const tierBadge: Record<string, string> = {
    gold: "bg-amber-500/20 text-amber-300",
    silver: "bg-gray-500/20 text-gray-300",
    standard: "bg-gray-700/30 text-gray-500",
  };
  const effortColor: Record<string, string> = {
    low: "bg-green-500/10 text-green-400",
    medium: "bg-amber-500/10 text-amber-400",
    high: "bg-red-500/10 text-red-400",
  };
  const typeIcon: Record<string, typeof DollarSign> = {
    recurring: Activity,
    one_time: Zap,
    mixed: Layers,
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {rankings.map((r, idx) => {
        const Icon = typeIcon[r.type] || Layers;
        return (
          <div key={r.avenue_key} className={`border rounded-xl p-5 transition-all duration-300 hover:scale-[1.01] ${tierBorder[r.tier]}`}>
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-gray-800/50 flex items-center justify-center">
                  <span className="text-sm font-black font-mono text-white">#{idx + 1}</span>
                </div>
                <div>
                  <p className="text-sm font-bold text-white">{r.label}</p>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <Icon className="w-3 h-3 text-gray-500" />
                    <span className="text-[10px] text-gray-500 font-mono">{r.type.toUpperCase()}</span>
                  </div>
                </div>
              </div>
              <span className={`text-[9px] font-mono px-2 py-0.5 rounded-full ${tierBadge[r.tier]}`}>
                {r.tier === "gold" ? "TOP" : r.tier === "silver" ? "MID" : "STD"}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 mb-4">
              <div>
                <span className="text-[9px] text-gray-500 font-mono">CURRENT</span>
                <p className="text-sm font-bold text-white font-mono">${r.current_monthly_revenue.toLocaleString()}/mo</p>
              </div>
              <div>
                <span className="text-[9px] text-gray-500 font-mono">POTENTIAL</span>
                <p className="text-sm font-bold text-green-400 font-mono">${r.potential_monthly_revenue.toLocaleString()}/mo</p>
              </div>
            </div>

            <div className="flex items-center gap-2 mb-3">
              <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${r.tier === "gold" ? "bg-amber-400" : r.tier === "silver" ? "bg-gray-400" : "bg-gray-600"}`} style={{ width: `${Math.min(r.roi_score, 100)}%` }} />
              </div>
              <span className="text-xs font-mono font-bold text-white">{r.roi_score}</span>
            </div>

            <div className="flex items-center gap-2 text-[10px]">
              <span className={`px-1.5 py-0.5 rounded font-mono ${effortColor[r.setup_effort]}`}>{r.setup_effort.toUpperCase()}</span>
              <span className="text-gray-500 font-mono">{r.time_to_revenue_days}d to rev</span>
              <span className="text-gray-500 font-mono">{(r.margin * 100).toFixed(0)}% margin</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ──────────────────────────────────── SaaS Metrics Panel ──────────────────────────────────── */

function SaaSMetricsPanel({ data }: { data: SaaSMetrics }) {
  if (data.status === "no_subscriptions") {
    return (
      <div className="text-center py-8">
        <Package className="w-8 h-8 text-gray-700 mx-auto mb-2" />
        <p className="text-gray-500 text-sm">No active subscriptions</p>
      </div>
    );
  }

  const qrColor = data.quick_ratio >= 4 ? "text-green-400" : data.quick_ratio >= 2 ? "text-amber-400" : "text-red-400";
  const nrrColor = data.net_revenue_retention >= 1.1 ? "text-green-400" : data.net_revenue_retention >= 1 ? "text-amber-400" : "text-red-400";
  const churnDir = data.gross_churn_rate > 0.05 ? "down" : data.gross_churn_rate > 0.03 ? "flat" : "up";

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-gray-800/30 rounded-lg p-4">
          <span className="text-[9px] text-gray-500 font-mono">MRR</span>
          <p className="text-xl font-black text-cyan-300 font-mono">${data.mrr.toLocaleString()}</p>
        </div>
        <div className="bg-gray-800/30 rounded-lg p-4">
          <span className="text-[9px] text-gray-500 font-mono">ARR</span>
          <p className="text-xl font-black text-purple-300 font-mono">${data.arr.toLocaleString()}</p>
        </div>
        <div className="bg-gray-800/30 rounded-lg p-4">
          <span className="text-[9px] text-gray-500 font-mono">NRR %</span>
          <p className={`text-xl font-black font-mono ${nrrColor}`}>{(data.net_revenue_retention * 100).toFixed(1)}%</p>
        </div>
        <div className="bg-gray-800/30 rounded-lg p-4">
          <span className="text-[9px] text-gray-500 font-mono">QUICK RATIO</span>
          <p className={`text-xl font-black font-mono ${qrColor}`}>{data.quick_ratio.toFixed(1)}x</p>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="flex items-center gap-3 bg-green-950/10 border border-green-900/20 rounded-lg px-3 py-2">
          <ArrowUpRight className="w-4 h-4 text-green-400" />
          <div>
            <span className="text-[9px] text-gray-500 font-mono">NEW MRR</span>
            <p className="text-sm font-bold text-green-400 font-mono">+${data.new_mrr.toLocaleString()}</p>
          </div>
        </div>
        <div className="flex items-center gap-3 bg-cyan-950/10 border border-cyan-900/20 rounded-lg px-3 py-2">
          <TrendingUp className="w-4 h-4 text-cyan-400" />
          <div>
            <span className="text-[9px] text-gray-500 font-mono">EXPANSION</span>
            <p className="text-sm font-bold text-cyan-400 font-mono">+${data.expansion_mrr.toLocaleString()}</p>
          </div>
        </div>
        <div className="flex items-center gap-3 bg-red-950/10 border border-red-900/20 rounded-lg px-3 py-2">
          <ArrowDownRight className="w-4 h-4 text-red-400" />
          <div>
            <span className="text-[9px] text-gray-500 font-mono">CHURNED</span>
            <p className="text-sm font-bold text-red-400 font-mono">-${data.churned_mrr.toLocaleString()}</p>
          </div>
        </div>
        <div className="flex items-center gap-3 bg-amber-950/10 border border-amber-900/20 rounded-lg px-3 py-2">
          <TrendingDown className="w-4 h-4 text-amber-400" />
          <div>
            <span className="text-[9px] text-gray-500 font-mono">CONTRACTION</span>
            <p className="text-sm font-bold text-amber-400 font-mono">-${data.contraction_mrr.toLocaleString()}</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="bg-gray-800/20 rounded-lg p-3">
          <span className="text-[9px] text-gray-500 font-mono">LTV</span>
          <p className="text-lg font-bold text-white font-mono">${data.ltv.toLocaleString()}</p>
        </div>
        <div className="bg-gray-800/20 rounded-lg p-3">
          <span className="text-[9px] text-gray-500 font-mono">CHURN RATE</span>
          <p className={`text-lg font-bold font-mono ${churnDir === "up" ? "text-green-400" : churnDir === "down" ? "text-red-400" : "text-amber-400"}`}>
            {(data.gross_churn_rate * 100).toFixed(2)}%
          </p>
        </div>
        <div className="bg-gray-800/20 rounded-lg p-3">
          <span className="text-[9px] text-gray-500 font-mono">ACTIVE SUBS</span>
          <p className="text-lg font-bold text-white font-mono">{data.active_subscriptions}</p>
        </div>
      </div>
    </div>
  );
}

/* ──────────────────────────────────── Pipeline Kanban ──────────────────────────────────── */

function PipelineKanban({ data }: { data: PipelineData }) {
  if (data.status === "empty_pipeline") {
    return (
      <div className="text-center py-8">
        <Briefcase className="w-8 h-8 text-gray-700 mx-auto mb-2" />
        <p className="text-gray-500 text-sm">No deals in pipeline</p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-gray-800/30 rounded-lg p-3">
          <span className="text-[9px] text-gray-500 font-mono">PIPELINE VALUE</span>
          <p className="text-lg font-bold text-white font-mono">${data.summary.total_pipeline_value.toLocaleString()}</p>
        </div>
        <div className="bg-gray-800/30 rounded-lg p-3">
          <span className="text-[9px] text-gray-500 font-mono">WEIGHTED VALUE</span>
          <p className="text-lg font-bold text-cyan-300 font-mono">${data.summary.weighted_pipeline_value.toLocaleString()}</p>
        </div>
        <div className="bg-gray-800/30 rounded-lg p-3">
          <span className="text-[9px] text-gray-500 font-mono">30D VELOCITY</span>
          <p className="text-lg font-bold text-green-300 font-mono">${data.summary.velocity_30d.toLocaleString()}</p>
        </div>
        <div className="bg-gray-800/30 rounded-lg p-3">
          <span className="text-[9px] text-gray-500 font-mono">WIN RATE</span>
          <p className="text-lg font-bold text-amber-300 font-mono">{(data.summary.win_rate_30d * 100).toFixed(1)}%</p>
        </div>
      </div>

      {data.bottleneck && data.bottleneck.stage && (
        <div className="bg-red-950/10 border border-red-900/20 rounded-lg px-4 py-3 flex items-center gap-3">
          <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
          <p className="text-xs text-red-300">
            <span className="font-bold">Bottleneck:</span> {data.bottleneck.deals_stuck} deals stuck in <span className="font-mono uppercase">{data.bottleneck.stage}</span> for avg {data.bottleneck.avg_days.toFixed(0)} days
          </p>
        </div>
      )}

      <div className="flex gap-3 overflow-x-auto pb-2">
        {STAGE_ORDER.map((stage) => {
          const stageInfo = data.stages[stage];
          const stageDeals = data.deals.filter((d) => d.stage === stage);
          const colorClass = STAGE_COLORS[stage] || "bg-gray-800/20 border-gray-700/30 text-gray-300";
          return (
            <div key={stage} className="min-w-[220px] flex-shrink-0">
              <div className={`border rounded-lg px-3 py-2 mb-2 ${colorClass}`}>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold font-mono uppercase">{stage}</span>
                  <span className="text-[10px] font-mono">{stageInfo?.count ?? 0}</span>
                </div>
                {stageInfo && stageInfo.total_value > 0 && (
                  <p className="text-[10px] font-mono mt-0.5">${stageInfo.total_value.toLocaleString()}</p>
                )}
              </div>
              <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
                {stageDeals.map((deal) => (
                  <div key={deal.id} className={`bg-gray-800/30 border rounded-lg px-3 py-2 ${deal.needs_attention ? "border-amber-500/30" : "border-gray-700/30"}`}>
                    <p className="text-xs font-medium text-white truncate">{deal.customer_name}</p>
                    <p className="text-sm font-bold text-white font-mono">${deal.deal_value.toLocaleString()}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[9px] text-gray-500 font-mono">{deal.product_type}</span>
                      {deal.needs_attention && <span className="text-[9px] text-amber-400 font-mono">{deal.days_stale}d stale</span>}
                    </div>
                  </div>
                ))}
                {stageDeals.length === 0 && (
                  <p className="text-[10px] text-gray-600 text-center py-4">No deals</p>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="bg-gray-800/20 rounded-lg p-3">
        <span className="text-[9px] text-gray-500 font-mono">30-DAY FORECAST</span>
        <div className="h-6 bg-gray-800 rounded-full overflow-hidden mt-2 relative">
          {(() => {
            const total = data.summary.total_pipeline_value || 1;
            let offset = 0;
            return STAGE_ORDER.map((stage) => {
              const sv = data.stages[stage]?.weighted_value || 0;
              const pct = (sv / total) * 100;
              const left = offset;
              offset += pct;
              const bgColors: Record<string, string> = {
                awareness: "bg-blue-500/50",
                interest: "bg-cyan-500/50",
                consideration: "bg-purple-500/50",
                proposal: "bg-amber-500/50",
                negotiation: "bg-green-500/50",
              };
              return pct > 0 ? (
                <div key={stage} className={`absolute top-0 h-full ${bgColors[stage] || "bg-gray-600"}`} style={{ left: `${left}%`, width: `${pct}%` }} title={`${stage}: $${sv.toLocaleString()}`} />
              ) : null;
            });
          })()}
        </div>
        <div className="flex items-center gap-3 mt-2 flex-wrap">
          {STAGE_ORDER.map((stage) => (
            <div key={stage} className="flex items-center gap-1">
              <div className={`w-2 h-2 rounded-full ${STAGE_COLORS[stage]?.split(" ")[0] || "bg-gray-600"}`} />
              <span className="text-[9px] text-gray-500 font-mono capitalize">{stage}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ──────────────────────────────────── Revenue Stack ──────────────────────────────────── */

function RevenueStackPanel({ data }: { data: RevenueStack }) {
  const maxMonthly = Math.max(...Object.values(data.stack).map((s) => s.monthly), 1);
  const vulnColor: Record<string, string> = {
    healthy: "text-green-400 bg-green-500/10",
    moderate: "text-amber-400 bg-amber-500/10",
    high: "text-red-400 bg-red-500/10",
    critical: "text-red-500 bg-red-500/20",
  };

  const typeColors: Record<string, string> = {
    recurring: "bg-cyan-500",
    one_time: "bg-amber-500",
    mixed: "bg-purple-500",
  };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-gray-800/30 rounded-lg p-3">
          <span className="text-[9px] text-gray-500 font-mono">TOTAL MONTHLY</span>
          <p className="text-lg font-black text-white font-mono">${data.total_monthly_revenue.toLocaleString()}</p>
        </div>
        <div className="bg-gray-800/30 rounded-lg p-3">
          <span className="text-[9px] text-gray-500 font-mono">RECURRING</span>
          <p className="text-lg font-black text-cyan-300 font-mono">{data.recurring_pct.toFixed(0)}%</p>
        </div>
        <div className="bg-gray-800/30 rounded-lg p-3">
          <span className="text-[9px] text-gray-500 font-mono">DIVERSIFICATION</span>
          <p className="text-lg font-black text-purple-300 font-mono">{(data.diversification_score * 100).toFixed(0)}/100</p>
        </div>
        <div className="bg-gray-800/30 rounded-lg p-3">
          <span className="text-[9px] text-gray-500 font-mono">VULNERABILITY</span>
          <p className={`text-sm font-bold font-mono px-2 py-0.5 rounded inline-block ${vulnColor[data.vulnerability] || vulnColor.moderate}`}>
            {data.vulnerability.toUpperCase()}
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {Object.entries(data.stack)
          .filter(([, v]) => v.monthly > 0)
          .sort(([, a], [, b]) => b.monthly - a.monthly)
          .map(([key, val]) => (
            <div key={key} className="flex items-center gap-4">
              <div className="w-36 text-right">
                <span className="text-xs text-gray-400 font-mono capitalize">{key.replace(/_/g, " ")}</span>
              </div>
              <div className="flex-1 h-6 bg-gray-800/40 rounded-full overflow-hidden relative">
                <div
                  className={`h-full rounded-full ${typeColors[val.type] || "bg-gray-500"} transition-all duration-700`}
                  style={{ width: `${(val.monthly / maxMonthly) * 100}%`, minWidth: "4px" }}
                />
              </div>
              <div className="w-28 text-right">
                <span className="text-sm font-bold text-white font-mono">${val.monthly.toLocaleString()}</span>
                <span className="text-[9px] text-gray-500 font-mono ml-1">{val.type}</span>
              </div>
            </div>
          ))}
      </div>

      <div className="bg-gray-800/20 rounded-lg p-3">
        <span className="text-[9px] text-gray-500 font-mono">RECURRING vs ONE-TIME</span>
        <div className="h-4 bg-gray-800 rounded-full overflow-hidden mt-2 flex">
          <div className="h-full bg-cyan-500 transition-all" style={{ width: `${data.recurring_pct}%` }} />
          <div className="h-full bg-amber-500 transition-all" style={{ width: `${100 - data.recurring_pct}%` }} />
        </div>
        <div className="flex items-center justify-between mt-1">
          <span className="text-[10px] text-cyan-400 font-mono">Recurring: ${data.recurring_monthly.toLocaleString()}</span>
          <span className="text-[10px] text-amber-400 font-mono">One-time: ${data.one_time_monthly.toLocaleString()}</span>
        </div>
      </div>
    </div>
  );
}

/* ──────────────────────────────────── Expansion Opportunities ──────────────────────────────────── */

function ExpansionPanel({ data }: { data: ExpansionData }) {
  if (data.status === "no_subscriptions" || data.opportunities.length === 0) {
    return (
      <div className="text-center py-8">
        <Users className="w-8 h-8 text-gray-700 mx-auto mb-2" />
        <p className="text-gray-500 text-sm">No expansion opportunities found</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-400">{data.total_opportunities} opportunities</span>
        <span className="text-xs text-green-400 font-mono font-bold">+${data.total_expected_expansion.toLocaleString()} expected</span>
      </div>
      {data.opportunities.slice(0, 10).map((opp) => (
        <div key={opp.subscription_id} className="bg-gray-800/30 border border-gray-700/30 rounded-lg px-4 py-3 hover:bg-gray-800/50 transition-colors">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-white font-medium">{opp.customer_name || opp.customer_id}</p>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-[10px] text-gray-500 font-mono">{opp.current_plan}</span>
                <ChevronRight className="w-3 h-3 text-gray-600" />
                <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${opp.opportunity_type === "tier_upgrade" ? "bg-purple-500/10 text-purple-400" : "bg-cyan-500/10 text-cyan-400"}`}>
                  {opp.opportunity_type === "tier_upgrade" ? "UPGRADE" : "ANNUAL"}
                </span>
              </div>
            </div>
            <div className="text-right">
              <p className="text-sm font-bold text-green-400 font-mono">+${opp.expected_mrr_delta.toLocaleString()}/mo</p>
              <p className="text-[10px] text-gray-500 font-mono">{(opp.probability * 100).toFixed(0)}% probability</p>
            </div>
          </div>
          <div className="flex items-center gap-1 mt-2">
            <div className="flex-1 h-1 bg-gray-800 rounded-full overflow-hidden">
              <div className="h-full bg-green-500 rounded-full" style={{ width: `${opp.probability * 100}%` }} />
            </div>
            <span className="text-[9px] text-gray-500 font-mono">{opp.tenure_days}d tenure</span>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ──────────────────────────────────── Main Page ──────────────────────────────────── */

export default function RevenueAvenuesPage() {
  const brandId = useBrandId();

  const [saasMetrics, setSaasMetrics] = useState<SaaSMetrics | null>(null);
  const [rankings, setRankings] = useState<RankingsData | null>(null);
  const [pipeline, setPipeline] = useState<PipelineData | null>(null);
  const [revenueStack, setRevenueStack] = useState<RevenueStack | null>(null);
  const [expansion, setExpansion] = useState<ExpansionData | null>(null);

  const [loadingSaas, setLoadingSaas] = useState(true);
  const [loadingRankings, setLoadingRankings] = useState(true);
  const [loadingPipeline, setLoadingPipeline] = useState(true);
  const [loadingStack, setLoadingStack] = useState(true);
  const [loadingExpansion, setLoadingExpansion] = useState(true);

  const [errorSaas, setErrorSaas] = useState("");
  const [errorRankings, setErrorRankings] = useState("");
  const [errorPipeline, setErrorPipeline] = useState("");
  const [errorStack, setErrorStack] = useState("");
  const [errorExpansion, setErrorExpansion] = useState("");

  const fetchSaas = useCallback(async () => {
    if (!brandId) return;
    setLoadingSaas(true); setErrorSaas("");
    try { setSaasMetrics(await apiFetch<SaaSMetrics>(`/api/v1/brands/${brandId}/avenues/saas-metrics`)); }
    catch (e: any) { setErrorSaas(e.message || "Failed to load SaaS metrics"); }
    finally { setLoadingSaas(false); }
  }, [brandId]);

  const fetchRankings = useCallback(async () => {
    if (!brandId) return;
    setLoadingRankings(true); setErrorRankings("");
    try { setRankings(await apiFetch<RankingsData>(`/api/v1/brands/${brandId}/avenues/rankings`)); }
    catch (e: any) { setErrorRankings(e.message || "Failed to load rankings"); }
    finally { setLoadingRankings(false); }
  }, [brandId]);

  const fetchPipeline = useCallback(async () => {
    if (!brandId) return;
    setLoadingPipeline(true); setErrorPipeline("");
    try { setPipeline(await apiFetch<PipelineData>(`/api/v1/brands/${brandId}/avenues/pipeline`)); }
    catch (e: any) { setErrorPipeline(e.message || "Failed to load pipeline"); }
    finally { setLoadingPipeline(false); }
  }, [brandId]);

  const fetchStack = useCallback(async () => {
    if (!brandId) return;
    setLoadingStack(true); setErrorStack("");
    try { setRevenueStack(await apiFetch<RevenueStack>(`/api/v1/brands/${brandId}/avenues/revenue-stack`)); }
    catch (e: any) { setErrorStack(e.message || "Failed to load revenue stack"); }
    finally { setLoadingStack(false); }
  }, [brandId]);

  const fetchExpansion = useCallback(async () => {
    if (!brandId) return;
    setLoadingExpansion(true); setErrorExpansion("");
    try { setExpansion(await apiFetch<ExpansionData>(`/api/v1/brands/${brandId}/avenues/expansion-opportunities`)); }
    catch (e: any) { setErrorExpansion(e.message || "Failed to load expansion opportunities"); }
    finally { setLoadingExpansion(false); }
  }, [brandId]);

  const refreshAll = useCallback(() => {
    fetchSaas(); fetchRankings(); fetchPipeline(); fetchStack(); fetchExpansion();
  }, [fetchSaas, fetchRankings, fetchPipeline, fetchStack, fetchExpansion]);

  useEffect(() => {
    if (!brandId) return;
    refreshAll();
  }, [brandId, refreshAll]);

  if (!brandId) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center space-y-4">
          <Crown className="w-12 h-12 text-gray-700 mx-auto" />
          <h2 className="text-xl font-bold text-white">No Brand Selected</h2>
          <p className="text-gray-500 text-sm max-w-md">Create a brand in Accounts first, then return here to optimize your revenue avenues.</p>
          <a href="/dashboard/accounts" className="inline-flex items-center gap-2 px-5 py-2.5 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-500 transition-colors">
            Manage Accounts
          </a>
        </div>
      </div>
    );
  }

  const totalMonthly = revenueStack?.total_monthly_revenue ?? 0;
  const nrr = saasMetrics?.net_revenue_retention ?? 0;
  const pipelineVal = pipeline?.summary?.weighted_pipeline_value ?? 0;
  const diversification = revenueStack?.diversification_score ?? 0;

  return (
    <div className="min-h-screen bg-gray-950 text-white space-y-8 -m-8 p-6">
      {/* ─── HEADER ─── */}
      <div className="flex items-center justify-between border-b border-amber-900/30 pb-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight bg-gradient-to-r from-amber-400 via-orange-500 to-rose-500 bg-clip-text text-transparent">
            REVENUE AVENUES
          </h1>
          <p className="text-gray-500 text-xs mt-1 font-mono">STRATEGIC COMMAND CENTER • AVENUE OPTIMIZATION • PIPELINE INTELLIGENCE</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={refreshAll}
            className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-xs text-gray-300 hover:text-white hover:border-gray-600 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-400 shadow-[0_0_8px_rgba(245,158,11,0.8)] animate-pulse" />
            <span className="text-amber-400 text-xs font-mono">LIVE</span>
          </div>
        </div>
      </div>

      {/* ─── KEY METRICS ─── */}
      <section>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {loadingStack || loadingSaas ? (
            <>{[...Array(4)].map((_, i) => <CardSkeleton key={i} />)}</>
          ) : (
            <>
              <MetricCard label="Total Monthly Revenue" value={`$${totalMonthly.toLocaleString()}`} icon={DollarSign} accentColor="amber" subtitle="all avenues" trend={totalMonthly > 0 ? "up" : "flat"} trendValue={`${revenueStack?.active_streams ?? 0} streams`} />
              <MetricCard label="Net Revenue Retention" value={`${(nrr * 100).toFixed(1)}%`} icon={Gauge} accentColor={nrr >= 1 ? "green" : "rose"} trend={nrr >= 1.1 ? "up" : nrr >= 1 ? "flat" : "down"} trendValue={nrr >= 1 ? "Healthy" : "Below par"} />
              <MetricCard label="Weighted Pipeline" value={`$${pipelineVal.toLocaleString()}`} icon={Target} accentColor="purple" subtitle="expected close value" trend={pipelineVal > 0 ? "up" : "flat"} trendValue={`${pipeline?.summary?.total_open_deals ?? 0} deals`} />
              <MetricCard label="Diversification" value={`${(diversification * 100).toFixed(0)}/100`} icon={Shield} accentColor="cyan" subtitle={revenueStack?.vulnerability ?? "unknown"} trend={diversification > 0.5 ? "up" : diversification > 0.3 ? "flat" : "down"} trendValue={diversification > 0.5 ? "Diversified" : "Concentrated"} />
            </>
          )}
        </div>
      </section>

      {/* ─── AVENUE RANKINGS ─── */}
      <section className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-6 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-sm font-bold text-amber-400/80 uppercase tracking-widest">Revenue Avenue Rankings</h2>
            <p className="text-xs text-gray-500 mt-0.5 font-mono">Ranked by ROI score • Gold = Top 3 • Silver = 4-6</p>
          </div>
          <Rocket className="w-4 h-4 text-gray-700" />
        </div>
        {loadingRankings ? <SectionSkeleton rows={3} /> : errorRankings ? <ErrorPanel message={errorRankings} onRetry={fetchRankings} /> : rankings ? <AvenueRankingsSection rankings={rankings.rankings} /> : null}
      </section>

      {/* ─── SAAS METRICS + REVENUE STACK (2-col) ─── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <section className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-6 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-bold text-amber-400/80 uppercase tracking-widest">SaaS Metrics</h2>
              <p className="text-xs text-gray-500 mt-0.5 font-mono">Subscription health and MRR movement</p>
            </div>
            <BarChart3 className="w-4 h-4 text-gray-700" />
          </div>
          {loadingSaas ? <SectionSkeleton /> : errorSaas ? <ErrorPanel message={errorSaas} onRetry={fetchSaas} /> : saasMetrics ? <SaaSMetricsPanel data={saasMetrics} /> : null}
        </section>

        <section className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-6 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-bold text-amber-400/80 uppercase tracking-widest">Revenue Stack</h2>
              <p className="text-xs text-gray-500 mt-0.5 font-mono">Revenue by avenue with diversification scoring</p>
            </div>
            <PieChart className="w-4 h-4 text-gray-700" />
          </div>
          {loadingStack ? <SectionSkeleton /> : errorStack ? <ErrorPanel message={errorStack} onRetry={fetchStack} /> : revenueStack ? <RevenueStackPanel data={revenueStack} /> : null}
        </section>
      </div>

      {/* ─── PIPELINE KANBAN ─── */}
      <section className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-6 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-bold text-amber-400/80 uppercase tracking-widest">High-Ticket Pipeline</h2>
            <p className="text-xs text-gray-500 mt-0.5 font-mono">Deal stages, velocity, and bottleneck detection</p>
          </div>
          <Briefcase className="w-4 h-4 text-gray-700" />
        </div>
        {loadingPipeline ? <SectionSkeleton rows={5} /> : errorPipeline ? <ErrorPanel message={errorPipeline} onRetry={fetchPipeline} /> : pipeline ? <PipelineKanban data={pipeline} /> : null}
      </section>

      {/* ─── EXPANSION OPPORTUNITIES ─── */}
      <section className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-6 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-bold text-amber-400/80 uppercase tracking-widest">Expansion Opportunities</h2>
            <p className="text-xs text-gray-500 mt-0.5 font-mono">Scored upsell and cross-sell opportunities</p>
          </div>
          <TrendingUp className="w-4 h-4 text-gray-700" />
        </div>
        {loadingExpansion ? <SectionSkeleton /> : errorExpansion ? <ErrorPanel message={errorExpansion} onRetry={fetchExpansion} /> : expansion ? <ExpansionPanel data={expansion} /> : null}
      </section>
    </div>
  );
}
