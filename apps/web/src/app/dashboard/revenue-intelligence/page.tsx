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
  ChevronDown,
  ChevronUp,
  X,
  RefreshCw,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Clock,
  BarChart3,
  Activity,
  Star,
  Filter,
} from "lucide-react";

/* ──────────────────────────────────── Types ──────────────────────────────────── */

interface ForecastPoint {
  date: string;
  actual: number | null;
  predicted: number;
  upper: number;
  lower: number;
}

interface ForecastData {
  points: ForecastPoint[];
  trend: "accelerating" | "steady" | "decelerating";
  growth_rate: number;
  predicted_30d_revenue: number;
}

interface ContentLTV {
  content_id: string;
  title: string;
  age_days: number;
  revenue_30d: number;
  revenue_90d: number;
  revenue_365d: number;
  evergreen_score: number;
  viral_coefficient: number;
}

interface AnomalyAlert {
  id: string;
  type: "spike" | "drop";
  severity: "critical" | "warning" | "info";
  metric: string;
  expected: number;
  actual: number;
  deviation_pct: number;
  explanation: string;
  recommended_action: string;
  detected_at: string;
}

interface CeilingBottleneck {
  category: string;
  description: string;
  impact_amount: number;
  priority: number;
}

interface CeilingOpportunity {
  name: string;
  expected_lift: number;
  effort: "low" | "medium" | "high";
  timeline_days: number;
}

interface RevenueCeilingData {
  current_monthly: number;
  theoretical_ceiling: number;
  efficiency_pct: number;
  bottlenecks: CeilingBottleneck[];
  opportunities: CeilingOpportunity[];
}

interface OfferRanking {
  offer_id: string;
  offer_name: string;
  overall_score: number;
  revenue_score: number;
  conversion_score: number;
  engagement_score: number;
  platform: string;
  content_type: string;
  monthly_revenue: number;
}

/* ──────────────────────────────────── Null-safe formatters ──────────────────────────────────── */

function fmtNum(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "0";
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: digits });
}

function fmtCurrency(v: number | null | undefined): string {
  return `$${fmtNum(v)}`;
}

function safeNum(v: number | null | undefined, fallback = 0): number {
  if (v === null || v === undefined || Number.isNaN(v)) return fallback;
  return v;
}

/* ──────────────────────────────────── SVG Chart Helpers ──────────────────────────────────── */

function MiniSparkline({ data, color, height = 40, width = 120 }: { data: number[]; color: string; height?: number; width?: number }) {
  if (data.length < 2) return null;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return `${x},${y}`;
  });
  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" points={points.join(" ")} />
    </svg>
  );
}

function ForecastChart({ points }: { points: ForecastPoint[] }) {
  const W = 800;
  const H = 300;
  const PAD = { top: 20, right: 20, bottom: 40, left: 60 };
  const cw = W - PAD.left - PAD.right;
  const ch = H - PAD.top - PAD.bottom;

  const allValues = points.flatMap((p) => [p.actual, p.predicted, p.upper, p.lower].filter((v): v is number => v !== null));
  const maxVal = Math.max(...allValues, 1);
  const minVal = Math.min(...allValues, 0);
  const range = maxVal - minVal || 1;

  const x = (i: number) => PAD.left + (i / Math.max(points.length - 1, 1)) * cw;
  const y = (v: number) => PAD.top + ch - ((v - minVal) / range) * ch;

  const bandPath = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(p.upper)}`)
    .join(" ")
    + " " + [...points].reverse().map((p, i) => `L${x(points.length - 1 - i)},${y(p.lower)}`).join(" ")
    + " Z";

  const actualPts = points.filter((p) => p.actual !== null);
  const actualLine = actualPts.map((p, i) => {
    const idx = points.indexOf(p);
    return `${i === 0 ? "M" : "L"}${x(idx)},${y(p.actual!)}`;
  }).join(" ");

  const predictedLine = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(p.predicted)}`).join(" ");

  const dividerIdx = points.findIndex((p) => p.actual === null);

  const gridLines = 5;
  const gridStep = range / gridLines;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="bandGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgb(34,211,238)" stopOpacity="0.15" />
          <stop offset="100%" stopColor="rgb(34,211,238)" stopOpacity="0.02" />
        </linearGradient>
        <linearGradient id="actualGrad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="rgb(34,211,238)" />
          <stop offset="100%" stopColor="rgb(99,102,241)" />
        </linearGradient>
      </defs>

      {Array.from({ length: gridLines + 1 }, (_, i) => {
        const val = minVal + i * gridStep;
        const yPos = y(val);
        return (
          <g key={i}>
            <line x1={PAD.left} y1={yPos} x2={W - PAD.right} y2={yPos} stroke="rgb(55,65,81)" strokeWidth="0.5" strokeDasharray="4,4" />
            <text x={PAD.left - 8} y={yPos + 4} textAnchor="end" fill="rgb(107,114,128)" fontSize="10" fontFamily="monospace">
              ${(val / 1000).toFixed(1)}k
            </text>
          </g>
        );
      })}

      {dividerIdx > 0 && (
        <line x1={x(dividerIdx)} y1={PAD.top} x2={x(dividerIdx)} y2={H - PAD.bottom} stroke="rgb(107,114,128)" strokeWidth="1" strokeDasharray="6,4" />
      )}
      {dividerIdx > 0 && (
        <text x={x(dividerIdx) + 6} y={PAD.top + 12} fill="rgb(156,163,175)" fontSize="9" fontFamily="monospace">FORECAST →</text>
      )}

      <path d={bandPath} fill="url(#bandGrad)" />

      <path d={predictedLine} fill="none" stroke="rgb(99,102,241)" strokeWidth="2" strokeDasharray="6,4" strokeLinecap="round" />

      {actualLine && <path d={actualLine} fill="none" stroke="url(#actualGrad)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />}

      {actualPts.map((p) => {
        const idx = points.indexOf(p);
        return <circle key={idx} cx={x(idx)} cy={y(p.actual!)} r="3" fill="rgb(34,211,238)" stroke="rgb(17,24,39)" strokeWidth="1.5" />;
      })}

      {points.filter((_, i) => i % Math.ceil(points.length / 8) === 0 || i === points.length - 1).map((p, _, arr) => {
        const idx = points.indexOf(p);
        return (
          <text key={idx} x={x(idx)} y={H - PAD.bottom + 20} textAnchor="middle" fill="rgb(107,114,128)" fontSize="9" fontFamily="monospace">
            {new Date(p.date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
          </text>
        );
      })}
    </svg>
  );
}

function ScheduleHeatmap({ data }: { data: number[][] }) {
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const hours = Array.from({ length: 24 }, (_, i) => i);
  const maxVal = Math.max(...data.flat(), 1);

  const intensity = (v: number) => {
    const ratio = v / maxVal;
    if (ratio > 0.8) return "bg-cyan-400";
    if (ratio > 0.6) return "bg-cyan-500/80";
    if (ratio > 0.4) return "bg-cyan-600/60";
    if (ratio > 0.2) return "bg-cyan-700/40";
    if (ratio > 0) return "bg-cyan-900/30";
    return "bg-gray-800/40";
  };

  return (
    <div className="overflow-x-auto">
      <div className="inline-grid gap-[2px]" style={{ gridTemplateColumns: `auto repeat(24, minmax(20px, 1fr))` }}>
        <div />
        {hours.map((h) => (
          <div key={h} className="text-[8px] text-gray-500 font-mono text-center">
            {h.toString().padStart(2, "0")}
          </div>
        ))}
        {days.map((day, di) => (
          <>
            <div key={`label-${day}`} className="text-[10px] text-gray-400 font-mono pr-2 flex items-center">{day}</div>
            {hours.map((h) => (
              <div key={`${day}-${h}`} className={`w-5 h-5 rounded-sm ${intensity(data[di]?.[h] ?? 0)} transition-colors hover:ring-1 hover:ring-cyan-300/50`} title={`${day} ${h}:00 — Score: ${(data[di]?.[h] ?? 0).toFixed(1)}`} />
            ))}
          </>
        ))}
      </div>
    </div>
  );
}

/* ──────────────────────────────────── Skeleton Loaders ──────────────────────────────────── */

function MetricCardSkeleton() {
  return (
    <div className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-5 animate-pulse">
      <div className="h-3 w-24 bg-gray-700 rounded mb-3" />
      <div className="h-8 w-32 bg-gray-700 rounded mb-2" />
      <div className="h-3 w-20 bg-gray-800 rounded" />
    </div>
  );
}

function ChartSkeleton() {
  return (
    <div className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-6 animate-pulse">
      <div className="h-4 w-40 bg-gray-700 rounded mb-4" />
      <div className="h-[200px] bg-gray-800/40 rounded-lg" />
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-6 animate-pulse">
      <div className="h-4 w-48 bg-gray-700 rounded mb-4" />
      {Array.from({ length: 5 }, (_, i) => (
        <div key={i} className="flex gap-4 mb-3">
          <div className="h-3 flex-1 bg-gray-800 rounded" />
          <div className="h-3 w-16 bg-gray-800 rounded" />
          <div className="h-3 w-16 bg-gray-800 rounded" />
          <div className="h-3 w-16 bg-gray-800 rounded" />
        </div>
      ))}
    </div>
  );
}

/* ──────────────────────────────────── Error State ──────────────────────────────────── */

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

/* ──────────────────────────────────── Section Components ──────────────────────────────────── */

function MetricCard({ label, value, subtitle, icon: Icon, trend, trendValue, accentColor }: {
  label: string;
  value: string;
  subtitle?: string;
  icon: typeof DollarSign;
  trend?: "up" | "down" | "flat";
  trendValue?: string;
  accentColor: string;
}) {
  const borderMap: Record<string, string> = {
    cyan: "border-cyan-500/30 hover:border-cyan-400/50",
    green: "border-green-500/30 hover:border-green-400/50",
    purple: "border-purple-500/30 hover:border-purple-400/50",
    amber: "border-amber-500/30 hover:border-amber-400/50",
  };
  const glowMap: Record<string, string> = {
    cyan: "shadow-[0_0_20px_rgba(34,211,238,0.08)]",
    green: "shadow-[0_0_20px_rgba(34,197,94,0.08)]",
    purple: "shadow-[0_0_20px_rgba(168,85,247,0.08)]",
    amber: "shadow-[0_0_20px_rgba(245,158,11,0.08)]",
  };
  const iconBgMap: Record<string, string> = {
    cyan: "bg-cyan-500/10 text-cyan-400",
    green: "bg-green-500/10 text-green-400",
    purple: "bg-purple-500/10 text-purple-400",
    amber: "bg-amber-500/10 text-amber-400",
  };
  const valueColorMap: Record<string, string> = {
    cyan: "text-cyan-300",
    green: "text-green-300",
    purple: "text-purple-300",
    amber: "text-amber-300",
  };

  return (
    <div className={`bg-gray-900/70 border rounded-xl p-5 backdrop-blur-sm transition-all duration-300 ${borderMap[accentColor]} ${glowMap[accentColor]}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] text-gray-500 font-mono uppercase tracking-wider">{label}</span>
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${iconBgMap[accentColor]}`}>
          <Icon className="w-4 h-4" />
        </div>
      </div>
      <p className={`text-2xl font-black tracking-tight ${valueColorMap[accentColor]}`}>{value}</p>
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

function ContentLTVTable({ items }: { items: ContentLTV[] }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [sortKey] = useState<"revenue_90d">("revenue_90d");

  const sorted = useMemo(() => [...items].sort((a, b) => b[sortKey] - a[sortKey]), [items, sortKey]);

  const evergreenColor = (score: number) => {
    if (score >= 80) return "text-green-400 bg-green-500/10";
    if (score >= 50) return "text-amber-400 bg-amber-500/10";
    return "text-red-400 bg-red-500/10";
  };

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-800/50">
            <th className="text-left text-[10px] text-gray-500 font-mono uppercase tracking-wider py-3 px-3" />
            <th className="text-left text-[10px] text-gray-500 font-mono uppercase tracking-wider py-3 px-3">Title</th>
            <th className="text-right text-[10px] text-gray-500 font-mono uppercase tracking-wider py-3 px-3">Age</th>
            <th className="text-right text-[10px] text-gray-500 font-mono uppercase tracking-wider py-3 px-3">30d Rev</th>
            <th className="text-right text-[10px] text-gray-500 font-mono uppercase tracking-wider py-3 px-3">90d Rev</th>
            <th className="text-right text-[10px] text-gray-500 font-mono uppercase tracking-wider py-3 px-3">365d Rev</th>
            <th className="text-center text-[10px] text-gray-500 font-mono uppercase tracking-wider py-3 px-3">Evergreen</th>
            <th className="text-right text-[10px] text-gray-500 font-mono uppercase tracking-wider py-3 px-3">Viral K</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((item) => (
            <>
              <tr key={item.content_id} className="border-b border-gray-800/30 hover:bg-gray-800/20 transition-colors cursor-pointer" onClick={() => toggle(item.content_id)}>
                <td className="py-3 px-3">
                  {expanded.has(item.content_id) ? <ChevronUp className="w-3.5 h-3.5 text-gray-500" /> : <ChevronDown className="w-3.5 h-3.5 text-gray-500" />}
                </td>
                <td className="py-3 px-3 text-white font-medium max-w-[240px] truncate">{item.title}</td>
                <td className="py-3 px-3 text-right text-gray-400 font-mono text-xs">{safeNum(item.age_days)}d</td>
                <td className="py-3 px-3 text-right text-gray-300 font-mono">{fmtCurrency(item.revenue_30d)}</td>
                <td className="py-3 px-3 text-right text-cyan-300 font-mono font-bold">{fmtCurrency(item.revenue_90d)}</td>
                <td className="py-3 px-3 text-right text-gray-300 font-mono">{fmtCurrency(item.revenue_365d)}</td>
                <td className="py-3 px-3 text-center">
                  <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-mono font-bold ${evergreenColor(item.evergreen_score)}`}>
                    {item.evergreen_score}
                  </span>
                </td>
                <td className="py-3 px-3 text-right text-gray-300 font-mono">{item.viral_coefficient.toFixed(2)}</td>
              </tr>
              {expanded.has(item.content_id) && (
                <tr key={`${item.content_id}-detail`} className="bg-gray-800/10">
                  <td colSpan={8} className="px-6 py-4">
                    <div className="grid grid-cols-3 gap-4 text-xs">
                      <div>
                        <span className="text-gray-500 font-mono">REVENUE TRAJECTORY</span>
                        <div className="flex items-end gap-1 mt-2 h-8">
                          {[item.revenue_30d, item.revenue_90d, item.revenue_365d].map((v, i) => (
                            <div key={i} className="bg-cyan-500/30 rounded-sm flex-1" style={{ height: `${(v / Math.max(item.revenue_365d, 1)) * 100}%`, minHeight: 4 }} />
                          ))}
                        </div>
                      </div>
                      <div>
                        <span className="text-gray-500 font-mono">EVERGREEN SCORE</span>
                        <div className="mt-2">
                          <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                            <div className={`h-full rounded-full ${item.evergreen_score >= 80 ? "bg-green-400" : item.evergreen_score >= 50 ? "bg-amber-400" : "bg-red-400"}`} style={{ width: `${item.evergreen_score}%` }} />
                          </div>
                        </div>
                      </div>
                      <div>
                        <span className="text-gray-500 font-mono">VIRAL COEFFICIENT</span>
                        <p className={`text-lg font-black mt-1 ${item.viral_coefficient > 1 ? "text-green-400" : "text-gray-400"}`}>
                          {item.viral_coefficient.toFixed(3)} {item.viral_coefficient > 1 && "🔥"}
                        </p>
                      </div>
                    </div>
                  </td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>
      {sorted.length === 0 && <p className="text-gray-600 text-xs text-center py-8">No content LTV data available</p>}
    </div>
  );
}

function RevenueCeilingPanel({ data }: { data: RevenueCeilingData | null | undefined }) {
  if (!data) {
    return (
      <div className="text-center py-8 text-gray-500 text-sm">
        No revenue ceiling data yet for this brand. Run recompute or wait for the scheduler.
      </div>
    );
  }

  const pct = safeNum(data.efficiency_pct);
  const currentMonthly = safeNum(data.current_monthly);
  const theoreticalCeiling = safeNum(data.theoretical_ceiling);
  const gap = theoreticalCeiling - currentMonthly;
  const bottlenecks = Array.isArray(data.bottlenecks) ? data.bottlenecks : [];
  const opportunities = Array.isArray(data.opportunities) ? data.opportunities : [];

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-gray-400">
            {fmtCurrency(currentMonthly)} <span className="text-gray-600">of</span> {fmtCurrency(theoreticalCeiling)}
          </span>
          <span className={`text-sm font-bold font-mono ${pct >= 70 ? "text-green-400" : pct >= 40 ? "text-amber-400" : "text-red-400"}`}>{pct.toFixed(1)}%</span>
        </div>
        <div className="h-4 bg-gray-800 rounded-full overflow-hidden relative">
          <div
            className={`h-full rounded-full transition-all duration-1000 ${pct >= 70 ? "bg-gradient-to-r from-green-500 to-green-400" : pct >= 40 ? "bg-gradient-to-r from-amber-500 to-amber-400" : "bg-gradient-to-r from-red-500 to-red-400"}`}
            style={{ width: `${Math.min(pct, 100)}%` }}
          />
          <div className="absolute inset-0 bg-[repeating-linear-gradient(90deg,transparent,transparent_8px,rgba(0,0,0,0.1)_8px,rgba(0,0,0,0.1)_16px)]" />
        </div>
        <p className="text-xs text-gray-500 mt-1 font-mono">Revenue gap: {fmtCurrency(gap)}/mo unrealized</p>
      </div>

      {bottlenecks.length > 0 && (
        <div>
          <h4 className="text-[10px] text-gray-500 font-mono uppercase tracking-wider mb-3">Bottlenecks by Impact</h4>
          <div className="space-y-2">
            {bottlenecks.slice().sort((a, b) => safeNum(b.impact_amount) - safeNum(a.impact_amount)).map((b, i) => (
              <div key={i} className="flex items-center gap-3 bg-gray-800/30 rounded-lg px-4 py-3">
                <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center text-red-400 font-mono text-xs font-bold">
                  #{b.priority ?? i + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white font-medium">{b.category ?? "—"}</p>
                  <p className="text-xs text-gray-500 truncate">{b.description ?? ""}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm text-red-400 font-mono font-bold">-{fmtCurrency(b.impact_amount)}</p>
                  <p className="text-[10px] text-gray-500">per month</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {opportunities.length > 0 && (
        <div>
          <h4 className="text-[10px] text-gray-500 font-mono uppercase tracking-wider mb-3">Top Opportunities</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {opportunities.map((opp, i) => (
              <div key={i} className="bg-green-950/10 border border-green-900/20 rounded-lg px-4 py-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-white font-medium">{opp.name ?? "—"}</p>
                  <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${opp.effort === "low" ? "bg-green-500/10 text-green-400" : opp.effort === "medium" ? "bg-amber-500/10 text-amber-400" : "bg-red-500/10 text-red-400"}`}>
                    {(opp.effort ?? "unknown").toUpperCase()}
                  </span>
                </div>
                <div className="flex items-center gap-3 mt-1.5">
                  <span className="text-green-400 font-mono font-bold text-sm">+{fmtCurrency(opp.expected_lift)}/mo</span>
                  <span className="text-[10px] text-gray-500 font-mono">{safeNum(opp.timeline_days)}d timeline</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function AnomalyAlerts({ alerts, onDismiss }: { alerts: AnomalyAlert[]; onDismiss: (id: string) => void }) {
  const severityStyle = (s: string) => {
    if (s === "critical") return "border-red-500/40 bg-red-950/20";
    if (s === "warning") return "border-amber-500/30 bg-amber-950/15";
    return "border-blue-500/20 bg-blue-950/10";
  };

  const typeIcon = (type: string) => type === "spike"
    ? <TrendingUp className="w-4 h-4 text-green-400" />
    : <TrendingDown className="w-4 h-4 text-red-400" />;

  return (
    <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1 scrollbar-thin">
      {alerts.map((a) => (
        <div key={a.id} className={`border rounded-lg px-4 py-3 ${severityStyle(a.severity)} transition-all`}>
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2">
              {typeIcon(a.type)}
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-white font-medium">{a.metric}</span>
                  <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded-full ${a.severity === "critical" ? "bg-red-500/20 text-red-400" : a.severity === "warning" ? "bg-amber-500/20 text-amber-400" : "bg-blue-500/20 text-blue-400"}`}>
                    {a.severity.toUpperCase()}
                  </span>
                </div>
                <p className="text-xs text-gray-400 mt-0.5">{a.explanation}</p>
              </div>
            </div>
            <button aria-label="Dismiss alert" onClick={() => onDismiss(a.id)} className="text-gray-600 hover:text-gray-400 transition-colors flex-shrink-0">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="flex items-center gap-4 mt-2 text-[10px] font-mono">
            <span className="text-gray-500">Expected: {fmtCurrency(a.expected)}</span>
            <span className={a.type === "spike" ? "text-green-400" : "text-red-400"}>Actual: {fmtCurrency(a.actual)}</span>
            <span className="text-gray-500">{safeNum(a.deviation_pct) > 0 ? "+" : ""}{safeNum(a.deviation_pct).toFixed(1)}%</span>
          </div>
          <div className="mt-2 bg-gray-800/40 rounded px-3 py-2">
            <p className="text-[10px] text-cyan-400 font-mono">RECOMMENDED: {a.recommended_action}</p>
          </div>
        </div>
      ))}
      {alerts.length === 0 && (
        <div className="text-center py-8">
          <Activity className="w-6 h-6 text-gray-700 mx-auto mb-2" />
          <p className="text-gray-600 text-xs">No anomalies detected</p>
        </div>
      )}
    </div>
  );
}

function OfferRankingsTable({ offers }: { offers: OfferRanking[] }) {
  const [platformFilter, setPlatformFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");

  const platforms = useMemo(() => ["all", ...new Set(offers.map((o) => o.platform))], [offers]);
  const types = useMemo(() => ["all", ...new Set(offers.map((o) => o.content_type))], [offers]);

  const filtered = useMemo(() => {
    let result = offers;
    if (platformFilter !== "all") result = result.filter((o) => o.platform === platformFilter);
    if (typeFilter !== "all") result = result.filter((o) => o.content_type === typeFilter);
    return result.sort((a, b) => b.overall_score - a.overall_score);
  }, [offers, platformFilter, typeFilter]);

  const scoreBar = (score: number, color: string) => (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-[10px] font-mono text-gray-400 w-6 text-right">{score}</span>
    </div>
  );

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <Filter className="w-3.5 h-3.5 text-gray-500" />
        <select aria-label="Filter by platform" value={platformFilter} onChange={(e) => setPlatformFilter(e.target.value)} className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-xs text-white">
          {platforms.map((p) => <option key={p} value={p}>{p === "all" ? "All Platforms" : p}</option>)}
        </select>
        <select aria-label="Filter by content type" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-xs text-white">
          {types.map((t) => <option key={t} value={t}>{t === "all" ? "All Types" : t}</option>)}
        </select>
      </div>

      <div className="space-y-2">
        {filtered.map((offer, idx) => (
          <div key={offer.offer_id} className="bg-gray-800/30 border border-gray-800/50 rounded-lg px-4 py-3 hover:bg-gray-800/50 transition-colors">
            <div className="flex items-center gap-4">
              <div className="w-8 h-8 rounded-lg bg-gray-700/50 flex items-center justify-center">
                <span className="text-xs font-bold font-mono text-cyan-400">#{idx + 1}</span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-white font-medium truncate">{offer.offer_name}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-[10px] font-mono text-gray-500 bg-gray-800 px-1.5 py-0.5 rounded">{offer.platform}</span>
                  <span className="text-[10px] font-mono text-gray-500 bg-gray-800 px-1.5 py-0.5 rounded">{offer.content_type}</span>
                </div>
              </div>
              <div className="text-right">
                <p className="text-lg font-black text-cyan-300 font-mono">{safeNum(offer.overall_score)}</p>
                <p className="text-[10px] text-gray-500">{fmtCurrency(offer.monthly_revenue)}/mo</p>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4 mt-3">
              <div>
                <span className="text-[9px] text-gray-500 font-mono">REVENUE</span>
                {scoreBar(offer.revenue_score, "bg-cyan-400")}
              </div>
              <div>
                <span className="text-[9px] text-gray-500 font-mono">CONVERSION</span>
                {scoreBar(offer.conversion_score, "bg-green-400")}
              </div>
              <div>
                <span className="text-[9px] text-gray-500 font-mono">ENGAGEMENT</span>
                {scoreBar(offer.engagement_score, "bg-purple-400")}
              </div>
            </div>
          </div>
        ))}
        {filtered.length === 0 && <p className="text-gray-600 text-xs text-center py-6">No offers match the selected filters</p>}
      </div>
    </div>
  );
}

/* ──────────────────────────────────── Main Page ──────────────────────────────────── */

export default function RevenueIntelligencePage() {
  const brandId = useBrandId();

  const [forecast, setForecast] = useState<ForecastData | null>(null);
  const [anomalies, setAnomalies] = useState<AnomalyAlert[]>([]);
  const [contentLtv, setContentLtv] = useState<ContentLTV[]>([]);
  const [ceiling, setCeiling] = useState<RevenueCeilingData | null>(null);
  const [offerRankings, setOfferRankings] = useState<OfferRanking[]>([]);

  const [loadingForecast, setLoadingForecast] = useState(true);
  const [loadingAnomalies, setLoadingAnomalies] = useState(true);
  const [loadingLtv, setLoadingLtv] = useState(true);
  const [loadingCeiling, setLoadingCeiling] = useState(true);
  const [loadingOffers, setLoadingOffers] = useState(true);

  const [errorForecast, setErrorForecast] = useState("");
  const [errorAnomalies, setErrorAnomalies] = useState("");
  const [errorLtv, setErrorLtv] = useState("");
  const [errorCeiling, setErrorCeiling] = useState("");
  const [errorOffers, setErrorOffers] = useState("");

  const [dismissedAlerts, setDismissedAlerts] = useState<Set<string>>(new Set());

  const [heatmapData, setHeatmapData] = useState<number[][]>(() =>
    Array.from({ length: 7 }, () => Array.from({ length: 24 }, () => 0))
  );

  useEffect(() => {
    if (!brandId) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await apiFetch<{ heatmap: number[][] }>(`/api/v1/brands/${brandId}/intelligence/posting-schedule`);
        if (!cancelled && data?.heatmap?.length === 7) {
          setHeatmapData(data.heatmap);
        }
      } catch {
        // API not available yet — leave zeros (shows empty heatmap)
      }
    })();
    return () => { cancelled = true; };
  }, [brandId]);

  const fetchForecast = useCallback(async () => {
    if (!brandId) return;
    setLoadingForecast(true);
    setErrorForecast("");
    try {
      const data = await apiFetch<ForecastData & { status?: string }>(`/api/v1/brands/${brandId}/intelligence/forecast`);
      if (data?.status === "insufficient_data" || !data?.points) {
        setForecast(null);
        setErrorForecast("Not enough data yet — need at least 14 days of activity to generate forecasts.");
      } else {
        setForecast(data);
      }
    } catch (e: any) {
      setErrorForecast(e.message || "Failed to load forecast");
    } finally {
      setLoadingForecast(false);
    }
  }, [brandId]);

  const fetchAnomalies = useCallback(async () => {
    if (!brandId) return;
    setLoadingAnomalies(true);
    setErrorAnomalies("");
    try {
      const data = await apiFetch<AnomalyAlert[]>(`/api/v1/brands/${brandId}/intelligence/anomalies`);
      setAnomalies(data);
    } catch (e: any) {
      setErrorAnomalies(e.message || "Failed to load anomalies");
    } finally {
      setLoadingAnomalies(false);
    }
  }, [brandId]);

  const fetchLtv = useCallback(async () => {
    if (!brandId) return;
    setLoadingLtv(true);
    setErrorLtv("");
    try {
      const data = await apiFetch<ContentLTV[]>(`/api/v1/brands/${brandId}/intelligence/content-ltv`);
      setContentLtv(data);
    } catch (e: any) {
      setErrorLtv(e.message || "Failed to load content LTV");
    } finally {
      setLoadingLtv(false);
    }
  }, [brandId]);

  const fetchCeiling = useCallback(async () => {
    if (!brandId) return;
    setLoadingCeiling(true);
    setErrorCeiling("");
    try {
      const data = await apiFetch<RevenueCeilingData & { status?: string }>(`/api/v1/brands/${brandId}/intelligence/revenue-ceiling`);
      if (data?.status === "insufficient_data" || data?.current_monthly === undefined) {
        setCeiling(null);
        setErrorCeiling("Not enough revenue data yet to calculate ceiling analysis.");
      } else {
        setCeiling(data);
      }
    } catch (e: any) {
      setErrorCeiling(e.message || "Failed to load revenue ceiling");
    } finally {
      setLoadingCeiling(false);
    }
  }, [brandId]);

  const fetchOffers = useCallback(async () => {
    if (!brandId) return;
    setLoadingOffers(true);
    setErrorOffers("");
    try {
      const data = await apiFetch<OfferRanking[]>(`/api/v1/brands/${brandId}/intelligence/offer-rankings`);
      setOfferRankings(data);
    } catch (e: any) {
      setErrorOffers(e.message || "Failed to load offer rankings");
    } finally {
      setLoadingOffers(false);
    }
  }, [brandId]);

  useEffect(() => {
    if (!brandId) return;
    fetchForecast();
    fetchAnomalies();
    fetchLtv();
    fetchCeiling();
    fetchOffers();
  }, [brandId, fetchForecast, fetchAnomalies, fetchLtv, fetchCeiling, fetchOffers]);

  const visibleAnomalies = anomalies.filter((a) => !dismissedAlerts.has(a.id));

  const trendLabel = forecast?.trend === "accelerating" ? "Accelerating" : forecast?.trend === "decelerating" ? "Decelerating" : "Steady";
  const trendDir = forecast?.trend === "accelerating" ? "up" : forecast?.trend === "decelerating" ? "down" : "flat";

  if (!brandId) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center space-y-4">
          <DollarSign className="w-12 h-12 text-gray-700 mx-auto" />
          <h2 className="text-xl font-bold text-white">No Brand Selected</h2>
          <p className="text-gray-500 text-sm max-w-md">Create a brand in Accounts first, then return here to view your revenue intelligence.</p>
          <a href="/dashboard/accounts" className="inline-flex items-center gap-2 px-5 py-2.5 bg-cyan-600 text-white rounded-lg text-sm font-medium hover:bg-cyan-500 transition-colors">
            Manage Accounts
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white space-y-8 -m-8 p-6">
      {/* ─── HEADER ─── */}
      <div className="flex items-center justify-between border-b border-cyan-900/30 pb-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight bg-gradient-to-r from-cyan-400 via-blue-500 to-purple-500 bg-clip-text text-transparent">
            REVENUE INTELLIGENCE
          </h1>
          <p className="text-gray-500 text-xs mt-1 font-mono">AUTONOMOUS REVENUE OS • PREDICTIVE ANALYTICS • REAL-TIME</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => { fetchForecast(); fetchAnomalies(); fetchLtv(); fetchCeiling(); fetchOffers(); }}
            className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-xs text-gray-300 hover:text-white hover:border-gray-600 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)] animate-pulse" />
            <span className="text-cyan-400 text-xs font-mono">LIVE</span>
          </div>
        </div>
      </div>

      {/* ─── KEY METRICS ─── */}
      <section>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {loadingForecast || loadingCeiling ? (
            <>
              <MetricCardSkeleton />
              <MetricCardSkeleton />
              <MetricCardSkeleton />
              <MetricCardSkeleton />
            </>
          ) : (
            <>
              <MetricCard
                label="Monthly Revenue"
                value={`$${(ceiling?.current_monthly ?? 0).toLocaleString()}`}
                icon={DollarSign}
                trend={trendDir}
                trendValue={`${(forecast?.growth_rate ?? 0).toFixed(1)}%`}
                subtitle="vs last period"
                accentColor="cyan"
              />
              <MetricCard
                label="Revenue Velocity"
                value={`${Math.round((forecast?.growth_rate ?? 0) * 10)}`}
                icon={Gauge}
                trend={(forecast?.growth_rate ?? 0) > 5 ? "up" : (forecast?.growth_rate ?? 0) < 0 ? "down" : "flat"}
                trendValue={trendLabel}
                subtitle="0-100 score"
                accentColor="purple"
              />
              <MetricCard
                label="Revenue Efficiency"
                value={`${(ceiling?.efficiency_pct ?? 0).toFixed(1)}%`}
                icon={Target}
                trend={(ceiling?.efficiency_pct ?? 0) >= 70 ? "up" : "down"}
                trendValue={`$${((ceiling?.theoretical_ceiling ?? 0) - (ceiling?.current_monthly ?? 0)).toLocaleString()} gap`}
                subtitle="of ceiling achieved"
                accentColor="green"
              />
              <MetricCard
                label="Predicted 30d Revenue"
                value={`$${(forecast?.predicted_30d_revenue ?? 0).toLocaleString()}`}
                icon={Zap}
                trend={trendDir}
                trendValue={`${(forecast?.growth_rate ?? 0).toFixed(1)}% growth`}
                subtitle="ML forecast"
                accentColor="amber"
              />
            </>
          )}
        </div>
      </section>

      {/* ─── FORECAST CHART ─── */}
      <section className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-6 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-bold text-cyan-400/80 uppercase tracking-widest">Revenue Forecast</h2>
            <p className="text-xs text-gray-500 mt-0.5 font-mono">Historical + ML predicted revenue with confidence bands</p>
          </div>
          {forecast && (
            <div className="flex items-center gap-4 text-xs">
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-0.5 bg-cyan-400 rounded-full" />
                <span className="text-gray-400">Actual</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-0.5 bg-indigo-400 rounded-full" style={{ borderBottom: "1px dashed" }} />
                <span className="text-gray-400">Predicted</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-2 bg-cyan-500/20 rounded-sm" />
                <span className="text-gray-400">Confidence</span>
              </div>
              <span className={`px-2 py-0.5 rounded-full font-mono ${trendDir === "up" ? "bg-green-500/10 text-green-400" : trendDir === "down" ? "bg-red-500/10 text-red-400" : "bg-gray-700 text-gray-400"}`}>
                {trendLabel} • {(forecast?.growth_rate ?? 0).toFixed(1)}% growth
              </span>
            </div>
          )}
        </div>
        {loadingForecast ? (
          <div className="h-[300px] bg-gray-800/30 rounded-lg animate-pulse" />
        ) : errorForecast ? (
          <ErrorPanel message={errorForecast} onRetry={fetchForecast} />
        ) : forecast ? (
          <ForecastChart points={forecast.points} />
        ) : null}
      </section>

      {/* ─── CONTENT LTV + ANOMALIES (2-col) ─── */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 bg-gray-900/60 border border-gray-800/50 rounded-xl p-6 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-bold text-cyan-400/80 uppercase tracking-widest">Content Lifetime Value</h2>
              <p className="text-xs text-gray-500 mt-0.5 font-mono">Projected revenue by content piece</p>
            </div>
            <Star className="w-4 h-4 text-gray-700" />
          </div>
          {loadingLtv ? <TableSkeleton /> : errorLtv ? <ErrorPanel message={errorLtv} onRetry={fetchLtv} /> : <ContentLTVTable items={contentLtv} />}
        </div>

        <div className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-6 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-bold text-cyan-400/80 uppercase tracking-widest">Anomaly Detection</h2>
              <p className="text-xs text-gray-500 mt-0.5 font-mono">{visibleAnomalies.length} active alert{visibleAnomalies.length !== 1 && "s"}</p>
            </div>
            <AlertTriangle className={`w-4 h-4 ${visibleAnomalies.some((a) => a.severity === "critical") ? "text-red-400 animate-pulse" : "text-gray-700"}`} />
          </div>
          {loadingAnomalies ? <ChartSkeleton /> : errorAnomalies ? <ErrorPanel message={errorAnomalies} onRetry={fetchAnomalies} /> : (
            <AnomalyAlerts alerts={visibleAnomalies} onDismiss={(id) => setDismissedAlerts((prev) => new Set(prev).add(id))} />
          )}
        </div>
      </div>

      {/* ─── REVENUE CEILING ─── */}
      <section className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-6 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-sm font-bold text-cyan-400/80 uppercase tracking-widest">Revenue Ceiling Analysis</h2>
            <p className="text-xs text-gray-500 mt-0.5 font-mono">Gap between current and theoretical maximum revenue</p>
          </div>
          <BarChart3 className="w-4 h-4 text-gray-700" />
        </div>
        {loadingCeiling ? <ChartSkeleton /> : errorCeiling ? <ErrorPanel message={errorCeiling} onRetry={fetchCeiling} /> : ceiling ? <RevenueCeilingPanel data={ceiling} /> : null}
      </section>

      {/* ─── POSTING SCHEDULE HEATMAP ─── */}
      <section className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-6 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-bold text-cyan-400/80 uppercase tracking-widest">Optimal Posting Schedule</h2>
            <p className="text-xs text-gray-500 mt-0.5 font-mono">Revenue-weighted engagement heatmap by day &amp; hour</p>
          </div>
          <Clock className="w-4 h-4 text-gray-700" />
        </div>
        <ScheduleHeatmap data={heatmapData} />
        <div className="flex items-center gap-2 mt-3">
          <span className="text-[10px] text-gray-600 font-mono">LOW</span>
          <div className="flex gap-[2px]">
            {["bg-gray-800/40", "bg-cyan-900/30", "bg-cyan-700/40", "bg-cyan-600/60", "bg-cyan-500/80", "bg-cyan-400"].map((c, i) => (
              <div key={i} className={`w-4 h-3 rounded-sm ${c}`} />
            ))}
          </div>
          <span className="text-[10px] text-gray-600 font-mono">HIGH</span>
        </div>
      </section>

      {/* ─── OFFER RANKINGS ─── */}
      <section className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-6 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-bold text-cyan-400/80 uppercase tracking-widest">Offer Rankings</h2>
            <p className="text-xs text-gray-500 mt-0.5 font-mono">Composite scoring across revenue, conversion &amp; engagement</p>
          </div>
          <TrendingUp className="w-4 h-4 text-gray-700" />
        </div>
        {loadingOffers ? <TableSkeleton /> : errorOffers ? <ErrorPanel message={errorOffers} onRetry={fetchOffers} /> : <OfferRankingsTable offers={offerRankings} />}
      </section>
    </div>
  );
}
