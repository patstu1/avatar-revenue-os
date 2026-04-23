"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import {
  Zap,
  CheckCircle2,
  XCircle,
  TrendingUp,
  ShieldCheck,
  RefreshCw,
  ArrowRight,
  DollarSign,
  Users,
  Repeat,
  Target,
  CreditCard,
  Crown,
  Package,
  BarChart3,
  Sparkles,
  Bot,
  Lock,
  AlertTriangle,
} from "lucide-react";

/* ═══════════════════════════════ Types ═══════════════════════════════ */

interface MachineReport {
  health_score: number;
  grade: string;
  mrr: number;
  arr: number;
  arpu: number;
  total_customers: number;
  churn_rate: number;
  ltv: number;
  cac: number;
  ltv_cac_ratio: number;
  net_revenue_retention: number;
  expansion_rate: number;
}

interface ReadinessQuestion {
  id: string;
  question: string;
  short_label: string;
  passing: boolean;
  actual_value: number;
  threshold: number;
  unit: string;
  score_contribution: number;
  gap_text: string | null;
}

interface ReadinessData {
  questions: ReadinessQuestion[];
  composite_score: number;
  elite_ready: boolean;
  gap_analysis: string | null;
}

interface EngineSignal {
  label: string;
  value: string;
  status: "good" | "warning" | "critical";
}

interface EngineData {
  engine: string;
  label: string;
  health_score: number;
  grade: string;
  signals: EngineSignal[];
  top_bottleneck: string;
  recommended_action: string;
}

interface SpendTrigger {
  id: string;
  priority: number;
  icon_type: string;
  nudge_message: string;
  cta_label: string;
  cta_action: string;
  cta_url: string | null;
  estimated_revenue_impact: number;
}

interface FeeRow {
  fee_type: string;
  description: string;
  rate_pct: number;
  projected_monthly: number;
}

interface FeeSummary {
  fees: FeeRow[];
  total_projected_monthly: number;
}

interface PremiumOutput {
  id: string;
  name: string;
  category: string;
  price: number;
  credit_cost: number;
  description: string;
}

interface RecommendedAction {
  rank: number;
  title: string;
  expected_impact_pct: number;
  target_section: string;
  target_url: string;
}

/* ═══════════════════════════════ Helpers ═══════════════════════════════ */

function gradeColor(grade: string): string {
  if (grade === "S") return "text-cyan-300";
  if (grade === "A") return "text-emerald-400";
  if (grade === "B") return "text-green-400";
  if (grade === "C") return "text-amber-400";
  if (grade === "D") return "text-orange-400";
  return "text-red-400";
}

function healthBorder(score: number): string {
  if (score > 70) return "border-emerald-500/40";
  if (score > 40) return "border-amber-500/40";
  return "border-red-500/40";
}

function healthGlow(score: number): string {
  if (score > 70) return "shadow-[0_0_20px_rgba(16,185,129,0.12)]";
  if (score > 40) return "shadow-[0_0_20px_rgba(245,158,11,0.12)]";
  return "shadow-[0_0_20px_rgba(239,68,68,0.12)]";
}

function healthBarColor(score: number): string {
  if (score > 70) return "bg-emerald-500";
  if (score > 40) return "bg-amber-500";
  return "bg-red-500";
}

function healthBg(score: number): string {
  if (score > 70) return "bg-emerald-500/10";
  if (score > 40) return "bg-amber-500/10";
  return "bg-red-500/10";
}

function healthText(score: number): string {
  if (score > 70) return "text-emerald-400";
  if (score > 40) return "text-amber-400";
  return "text-red-400";
}

const fmt = (n: number) => n.toLocaleString("en-US", { maximumFractionDigits: 0 });
const fmtUsd = (n: number) => `$${fmt(n)}`;
const fmtPct = (n: number) => `${n.toFixed(1)}%`;

const engineIcons: Record<string, typeof Users> = {
  acquisition: Users,
  conversion: Target,
  expansion: TrendingUp,
  retention: Repeat,
  monetization: DollarSign,
};

const categoryIcons: Record<string, typeof Package> = {
  Content: Sparkles,
  Analytics: BarChart3,
  Automation: Bot,
  Enterprise: Lock,
};

const triggerIcons: Record<string, typeof Zap> = {
  upgrade: Crown,
  credits: CreditCard,
  expansion: TrendingUp,
  retention: Repeat,
  alert: AlertTriangle,
  default: Zap,
};

/* ═══════════════════════════════ Sub-components ═══════════════════════════════ */

function PulsingDot({ className = "" }: { className?: string }) {
  return (
    <span className={`relative flex h-3 w-3 ${className}`}>
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-60" />
      <span className="relative inline-flex rounded-full h-3 w-3 bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.8)]" />
    </span>
  );
}

function ScoreRing({ score, grade, size = 120 }: { score: number; grade: string; size?: number }) {
  const r = (size - 12) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;
  const color = score > 70 ? "#10b981" : score > 40 ? "#f59e0b" : "#ef4444";

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgb(31,41,55)" strokeWidth="8" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          className="transition-all duration-1000"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-black text-white font-mono">{score}</span>
        <span className={`text-lg font-black ${gradeColor(grade)}`}>{grade}</span>
      </div>
    </div>
  );
}

function SkeletonBlock({ className = "" }: { className?: string }) {
  return <div className={`bg-gray-800/60 rounded-lg animate-pulse ${className}`} />;
}

function LoadingSkeleton() {
  return (
    <div className="min-h-screen bg-gray-950 text-white p-6 space-y-8">
      <div className="flex items-center justify-between border-b border-cyan-900/30 pb-4">
        <div>
          <SkeletonBlock className="h-9 w-80 mb-2" />
          <SkeletonBlock className="h-4 w-60" />
        </div>
        <SkeletonBlock className="h-8 w-24" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <SkeletonBlock key={i} className="h-28" />
        ))}
      </div>
      <SkeletonBlock className="h-64" />
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        {[1, 2, 3, 4, 5].map((i) => (
          <SkeletonBlock key={i} className="h-56" />
        ))}
      </div>
      <SkeletonBlock className="h-48" />
      <SkeletonBlock className="h-48" />
    </div>
  );
}

/* ═══════════════════════════════ Main Page ═══════════════════════════════ */

export default function RevenueMachinePage() {
  const [loading, setLoading] = useState(true);
  const [report, setReport] = useState<MachineReport | null>(null);
  const [readiness, setReadiness] = useState<ReadinessData | null>(null);
  const [engines, setEngines] = useState<EngineData[]>([]);
  const [triggers, setTriggers] = useState<SpendTrigger[]>([]);
  const [fees, setFees] = useState<FeeSummary | null>(null);
  const [premiumOutputs, setPremiumOutputs] = useState<PremiumOutput[]>([]);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchAll = () => {
    setLoading(true);
    setError("");
    Promise.all([
      apiFetch<any>("/api/v1/monetization/machine/report").catch(() => null),
      apiFetch<any>("/api/v1/monetization/machine/readiness").catch(() => null),
      apiFetch<any>("/api/v1/monetization/machine/engines").catch(() => null),
      apiFetch<any>("/api/v1/monetization/machine/triggers").catch(() => null),
      apiFetch<any>("/api/v1/monetization/machine/fees").catch(() => null),
      apiFetch<any>("/api/v1/monetization/machine/premium-outputs").catch(() => null),
    ])
      .then(([r, rd, en, tr, fe, po]) => {
        if (r) setReport({ ...r, grade: r.health_grade || r.grade || "F" } as MachineReport);

        if (rd) {
          const qs = (rd.questions ?? []).map((q: any) => ({
            id: q.key ?? q.id ?? "",
            question: q.question ?? "",
            short_label: q.key ?? q.short_label ?? "",
            passing: q.passed ?? q.passing ?? false,
            actual_value: q.weight ?? q.actual_value ?? 0,
            threshold: q.threshold ?? 0,
            unit: q.unit ?? "",
            score_contribution: q.weight ?? q.score_contribution ?? 0,
            gap_text: q.detail ?? q.gap_text ?? null,
          }));
          setReadiness({ questions: qs, composite_score: rd.readiness_score ?? rd.composite_score ?? 0, elite_ready: rd.grade === "Elite Ready", gap_analysis: rd.next_action ?? null });
        }

        const rawEngines = Array.isArray(en) ? en : en?.engines ?? [];
        setEngines(rawEngines.map((e: any) => ({
          engine: e.key ?? e.engine ?? "",
          label: e.engine ?? e.label ?? "",
          health_score: e.score ?? e.health_score ?? 0,
          grade: e.status === "healthy" ? "A" : e.status === "warning" ? "C" : "F",
          signals: Object.entries(e.metrics ?? {}).map(([k, v]) => ({ label: k.replace(/_/g, " "), value: String(v), status: "good" as const })),
          top_bottleneck: e.status === "critical" ? `${e.engine ?? e.label} needs attention` : "",
          recommended_action: e.status === "critical" ? `Improve ${e.engine ?? e.label}` : "Maintain",
        })));

        const triggerList = Array.isArray(tr) ? tr : tr?.triggers ?? [];
        setTriggers(triggerList.map((t: any) => ({
          id: t.trigger_id ?? t.id ?? "",
          priority: t.urgency ?? t.priority ?? 0,
          icon_type: t.type ?? t.icon_type ?? "default",
          nudge_message: t.message ?? t.nudge_message ?? "",
          cta_label: t.recommended_action ?? t.cta_label ?? "",
          cta_action: t.recommended_action === "upgrade_plan" ? "subscribe" : t.cta_action ?? "navigate",
          cta_url: t.cta_url ?? null,
          estimated_revenue_impact: t.estimated_revenue_impact ?? 0,
        })).sort((a: SpendTrigger, b: SpendTrigger) => b.priority - a.priority));

        if (fe) setFees({ fees: (fe.fee_breakdown ?? fe.fees ?? []).map((f: any) => ({ fee_type: f.fee_type ?? f.type ?? "", description: f.description ?? "", rate_pct: f.rate_pct ?? f.rate ?? 0, projected_monthly: f.projected_monthly ?? 0 })), total_projected_monthly: fe.total_fees ?? fe.total_projected_monthly ?? 0 });

        const packs = Array.isArray(po) ? po : [...(po?.premium_packs ?? []), ...(po?.credit_packs ?? [])];
        setPremiumOutputs(packs.map((p: any) => ({ id: p.pack_id ?? p.id ?? "", name: p.name ?? "", category: p.pack_type ?? p.category ?? "pack", price: p.price ?? 0, credit_cost: p.credits ?? p.credit_cost ?? 0, description: p.description ?? `${p.credits ?? 0} credits` })));
      })
      .catch(() => setError("Failed to load Revenue Machine data"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleTriggerCTA = async (trigger: SpendTrigger) => {
    setActionLoading(trigger.id);
    try {
      if (trigger.cta_action === "navigate" && trigger.cta_url) {
        window.location.href = trigger.cta_url;
        return;
      }
      if (trigger.cta_action === "subscribe") {
        const res = await apiFetch<{ checkout_url: string | null }>("/api/v1/monetization/subscribe", {
          method: "POST",
          body: JSON.stringify({ plan_tier: "professional", billing_interval: "monthly" }),
        });
        if (res.checkout_url) window.location.href = res.checkout_url;
      } else if (trigger.cta_action === "buy_credits") {
        window.location.href = "/dashboard/monetization";
      } else if (trigger.cta_url) {
        window.location.href = trigger.cta_url;
      }
    } catch (err) {
      console.error("Trigger CTA failed:", err);
    }
    setActionLoading(null);
  };

  const handlePurchaseOutput = async (output: PremiumOutput) => {
    setActionLoading(output.id);
    try {
      await apiFetch("/api/v1/monetization/credits/purchase", {
        method: "POST",
        body: JSON.stringify({ item_id: output.id, credit_cost: output.credit_cost }),
      });
      fetchAll();
    } catch (err) {
      console.error("Purchase failed:", err);
    }
    setActionLoading(null);
  };

  if (loading) return <LoadingSkeleton />;

  if (error) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-center space-y-4">
          <AlertTriangle className="w-12 h-12 text-red-400 mx-auto" />
          <p className="text-red-300">{error}</p>
          <button onClick={fetchAll} className="inline-flex items-center gap-2 px-4 py-2 bg-red-900/40 border border-red-800/50 text-red-300 rounded-lg text-sm hover:bg-red-900/60 transition-colors">
            <RefreshCw className="w-3.5 h-3.5" /> Retry
          </button>
        </div>
      </div>
    );
  }

  const compositeScore = report?.health_score ?? 0;
  const compositeGrade = report?.grade ?? "F";
  const questions = readiness?.questions ?? [];
  const passCount = questions.filter((q) => q.passing).length;
  const allPassing = passCount === questions.length && questions.length > 0;

  const recommendedActions: RecommendedAction[] = [
    ...(engines
      .filter((e) => e.health_score < 70)
      .sort((a, b) => a.health_score - b.health_score)
      .slice(0, 5)
      .map((e, i) => ({
        rank: i + 1,
        title: e.recommended_action,
        expected_impact_pct: Math.round((70 - e.health_score) * 0.8),
        target_section: e.label,
        target_url: `/dashboard/${e.engine === "monetization" ? "monetization" : e.engine === "acquisition" ? "growth" : e.engine === "retention" ? "recovery" : e.engine === "expansion" ? "offer-lab" : "revenue-intelligence"}`,
      }))),
  ].slice(0, 5);

  const outputCategories = [...new Set(premiumOutputs.map((o) => o.category))];

  return (
    <div className="min-h-screen bg-gray-950 text-white p-6 space-y-8">
      {/* ═══ 1. HEADER ═══ */}
      <div className="flex items-center justify-between border-b border-cyan-900/30 pb-5">
        <div className="flex items-center gap-4">
          <PulsingDot />
          <div>
            <h1 className="text-3xl md:text-4xl font-black tracking-tight bg-gradient-to-r from-cyan-400 via-emerald-400 to-amber-400 bg-clip-text text-transparent">
              REVENUE MACHINE
            </h1>
            <p className="text-gray-500 text-xs mt-1 font-mono tracking-wider">
              UNIFIED REVENUE OS • ENGINES • READINESS • PREMIUM
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={fetchAll}
            className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-xs text-gray-300 hover:text-white hover:border-gray-600 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
          <div className="flex items-center gap-2">
            <span className="text-cyan-400 text-xs font-mono">LIVE</span>
          </div>
        </div>
      </div>

      {/* Composite Score + Key Metrics */}
      <section className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <div className="lg:col-span-1 bg-gray-900/70 border border-cyan-900/30 rounded-xl p-6 flex flex-col items-center justify-center shadow-[0_0_30px_rgba(34,211,238,0.08)]">
          <ScoreRing score={compositeScore} grade={compositeGrade} />
          <p className="text-[10px] text-gray-500 font-mono uppercase mt-3 tracking-widest">COMPOSITE HEALTH</p>
        </div>

        <div className="lg:col-span-4 grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: "MRR", value: fmtUsd(report?.mrr ?? 0), color: "text-cyan-300", border: "border-cyan-500/30" },
            { label: "ARR", value: fmtUsd(report?.arr ?? 0), color: "text-emerald-300", border: "border-emerald-500/30" },
            { label: "ARPU", value: fmtUsd(report?.arpu ?? 0), color: "text-amber-300", border: "border-amber-500/30" },
            { label: "CUSTOMERS", value: fmt(report?.total_customers ?? 0), color: "text-purple-300", border: "border-purple-500/30" },
            { label: "CHURN RATE", value: fmtPct(report?.churn_rate ?? 0), color: (report?.churn_rate ?? 0) < 5 ? "text-emerald-400" : "text-red-400", border: "border-gray-700/50" },
            { label: "LTV", value: fmtUsd(report?.ltv ?? 0), color: "text-cyan-300", border: "border-gray-700/50" },
            { label: "CAC", value: fmtUsd(report?.cac ?? 0), color: "text-amber-300", border: "border-gray-700/50" },
            { label: "LTV:CAC", value: `${(report?.ltv_cac_ratio ?? 0).toFixed(1)}x`, color: (report?.ltv_cac_ratio ?? 0) >= 3 ? "text-emerald-400" : "text-red-400", border: "border-gray-700/50" },
          ].map((m) => (
            <div key={m.label} className={`bg-gray-900/60 border ${m.border} rounded-xl p-4`}>
              <p className="text-[10px] text-gray-500 font-mono uppercase tracking-wider">{m.label}</p>
              <p className={`text-2xl font-black font-mono mt-1 ${m.color}`}>{m.value}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ═══ 2. ELITE READINESS SCORECARD ═══ */}
      <section>
        <h2 className="text-sm font-bold text-cyan-400/80 uppercase tracking-widest mb-4">
          Elite Readiness Scorecard
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-7 gap-3">
          {questions.map((q) => (
            <div
              key={q.id}
              className={`bg-gray-900/70 border rounded-xl p-4 transition-all ${
                q.passing
                  ? "border-emerald-500/30 shadow-[0_0_12px_rgba(16,185,129,0.08)]"
                  : "border-red-500/30 shadow-[0_0_12px_rgba(239,68,68,0.08)]"
              }`}
            >
              <div className="flex items-center gap-2 mb-2">
                {q.passing ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                ) : (
                  <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                )}
                <span className={`text-[10px] font-mono font-bold ${q.passing ? "text-emerald-400" : "text-red-400"}`}>
                  {q.passing ? "PASS" : "FAIL"}
                </span>
              </div>
              <p className="text-xs text-gray-300 font-medium leading-tight mb-3 min-h-[32px]">
                {q.short_label}
              </p>
              <div className="space-y-1">
                <div className="flex justify-between text-[10px]">
                  <span className="text-gray-500">Actual</span>
                  <span className="text-white font-mono font-bold">
                    {q.actual_value}{q.unit}
                  </span>
                </div>
                <div className="flex justify-between text-[10px]">
                  <span className="text-gray-500">Threshold</span>
                  <span className="text-gray-400 font-mono">
                    {q.threshold}{q.unit}
                  </span>
                </div>
                <div className="flex justify-between text-[10px]">
                  <span className="text-gray-500">Score</span>
                  <span className="text-cyan-400 font-mono font-bold">+{q.score_contribution}</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Composite elite score bar */}
        {readiness && (
          <div className="mt-4 bg-gray-900/60 border border-gray-800/50 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                <ShieldCheck className={`w-5 h-5 ${allPassing ? "text-emerald-400" : "text-amber-400"}`} />
                <span className="text-sm font-bold text-white">
                  Elite Score: <span className="font-mono text-cyan-300">{readiness.composite_score}</span>/100
                </span>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${
                  allPassing ? "bg-emerald-500/20 text-emerald-400" : "bg-amber-500/20 text-amber-400"
                }`}>
                  {passCount}/{questions.length} PASSING
                </span>
              </div>
              {allPassing && (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400">
                  ELITE READY
                </span>
              )}
            </div>
            <div className="h-3 bg-gray-800 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-1000 ${
                  allPassing
                    ? "bg-gradient-to-r from-emerald-500 to-cyan-400"
                    : "bg-gradient-to-r from-amber-500 to-amber-400"
                }`}
                style={{ width: `${readiness.composite_score}%` }}
              />
            </div>
            {readiness.gap_analysis && !allPassing && (
              <div className="mt-3 p-3 bg-amber-950/20 border border-amber-900/30 rounded-lg">
                <p className="text-[10px] text-amber-400 font-mono uppercase mb-1">GAP ANALYSIS</p>
                <p className="text-xs text-gray-300">{readiness.gap_analysis}</p>
              </div>
            )}
          </div>
        )}
      </section>

      {/* ═══ 3. OPERATING MODEL HEALTH (5 ENGINES) ═══ */}
      <section>
        <h2 className="text-sm font-bold text-cyan-400/80 uppercase tracking-widest mb-4">
          Operating Model Health — 5 Engines
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {engines.map((eng) => {
            const Icon = engineIcons[eng.engine] ?? Zap;
            const score = eng.health_score;
            return (
              <div
                key={eng.engine}
                className={`bg-gray-900/70 border rounded-xl p-5 transition-all ${healthBorder(score)} ${healthGlow(score)}`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${healthBg(score)}`}>
                    <Icon className={`w-4.5 h-4.5 ${healthText(score)}`} />
                  </div>
                  <div className="text-right">
                    <span className={`text-2xl font-black font-mono ${healthText(score)}`}>{score}</span>
                    <span className={`text-sm font-bold ml-1 ${gradeColor(eng.grade)}`}>{eng.grade}</span>
                  </div>
                </div>

                <p className="text-xs font-bold text-white uppercase tracking-wider mb-3">{eng.label}</p>

                <div className="h-2 bg-gray-800 rounded-full overflow-hidden mb-3">
                  <div className={`h-full rounded-full transition-all duration-700 ${healthBarColor(score)}`} style={{ width: `${score}%` }} />
                </div>

                <div className="space-y-1.5 mb-3">
                  {eng.signals.slice(0, 4).map((s, i) => (
                    <div key={i} className="flex items-center justify-between text-[10px]">
                      <span className="text-gray-500 truncate mr-2">{s.label}</span>
                      <span className={`font-mono font-bold flex-shrink-0 ${
                        s.status === "good" ? "text-emerald-400" : s.status === "warning" ? "text-amber-400" : "text-red-400"
                      }`}>
                        {s.value}
                      </span>
                    </div>
                  ))}
                </div>

                {eng.top_bottleneck && (
                  <div className="p-2 bg-red-950/20 border border-red-900/20 rounded-lg mb-2">
                    <p className="text-[9px] text-red-400 font-mono uppercase">BOTTLENECK</p>
                    <p className="text-[10px] text-gray-400 mt-0.5 leading-tight">{eng.top_bottleneck}</p>
                  </div>
                )}

                {eng.recommended_action && (
                  <div className="p-2 bg-cyan-950/20 border border-cyan-900/20 rounded-lg">
                    <p className="text-[9px] text-cyan-400 font-mono uppercase">ACTION</p>
                    <p className="text-[10px] text-gray-400 mt-0.5 leading-tight">{eng.recommended_action}</p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* ═══ 4. CONTEXTUAL SPEND TRIGGERS ═══ */}
      {triggers.length > 0 && (
        <section>
          <h2 className="text-sm font-bold text-amber-400/80 uppercase tracking-widest mb-4">
            Contextual Spend Triggers
          </h2>
          <div className="space-y-3">
            {triggers.map((t) => {
              const TIcon = triggerIcons[t.icon_type] ?? triggerIcons.default;
              return (
                <div
                  key={t.id}
                  className="bg-gray-900/70 border border-amber-900/30 rounded-xl px-5 py-4 flex items-center gap-4 hover:border-amber-600/50 transition-all group"
                >
                  <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center flex-shrink-0">
                    <TIcon className="w-5 h-5 text-amber-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white font-medium">{t.nudge_message}</p>
                    <p className="text-[10px] text-gray-500 font-mono mt-0.5">
                      Est. revenue impact: <span className="text-emerald-400">+{fmtUsd(t.estimated_revenue_impact)}/mo</span>
                    </p>
                  </div>
                  <button
                    onClick={() => handleTriggerCTA(t)}
                    disabled={actionLoading === t.id}
                    className="flex items-center gap-2 px-4 py-2 bg-amber-600/20 text-amber-300 border border-amber-700/40 rounded-lg text-xs font-bold hover:bg-amber-600/30 hover:border-amber-500/50 transition-all disabled:opacity-50 flex-shrink-0"
                  >
                    {actionLoading === t.id ? (
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <>
                        {t.cta_label}
                        <ArrowRight className="w-3.5 h-3.5" />
                      </>
                    )}
                  </button>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ═══ 5. TRANSACTION FEE SUMMARY ═══ */}
      {fees && (
        <section>
          <h2 className="text-sm font-bold text-cyan-400/80 uppercase tracking-widest mb-1">
            Transaction Fee Summary
          </h2>
          <p className="text-[10px] text-gray-500 font-mono mb-4">
            THIS IS WHAT THE PLATFORM EARNS FROM YOUR SUCCESS
          </p>
          <div className="bg-gray-900/60 border border-gray-800/50 rounded-xl overflow-hidden">
            <div className="grid grid-cols-4 gap-4 px-5 py-3 border-b border-gray-800/50 text-[10px] text-gray-500 font-mono uppercase tracking-wider">
              <span>Fee Type</span>
              <span>Description</span>
              <span className="text-right">Rate</span>
              <span className="text-right">Projected Monthly</span>
            </div>
            {fees.fees.map((f, i) => (
              <div
                key={i}
                className="grid grid-cols-4 gap-4 px-5 py-3 border-b border-gray-800/30 hover:bg-gray-800/20 transition-colors"
              >
                <span className="text-xs text-white font-medium">{f.fee_type}</span>
                <span className="text-xs text-gray-400">{f.description}</span>
                <span className="text-xs text-amber-300 font-mono text-right">{f.rate_pct}%</span>
                <span className="text-xs text-cyan-300 font-mono font-bold text-right">{fmtUsd(f.projected_monthly)}</span>
              </div>
            ))}
            <div className="grid grid-cols-4 gap-4 px-5 py-4 bg-cyan-950/20">
              <span className="text-xs font-bold text-white col-span-3">Total Platform Fee Income</span>
              <span className="text-sm text-cyan-300 font-mono font-black text-right">
                {fmtUsd(fees.total_projected_monthly)}/mo
              </span>
            </div>
          </div>
        </section>
      )}

      {/* ═══ 6. PREMIUM OUTPUT CATALOG ═══ */}
      {premiumOutputs.length > 0 && (
        <section>
          <h2 className="text-sm font-bold text-cyan-400/80 uppercase tracking-widest mb-4">
            Premium Output Catalog
          </h2>
          <div className="space-y-6">
            {outputCategories.map((cat) => {
              const CatIcon = categoryIcons[cat] ?? Package;
              const items = premiumOutputs.filter((o) => o.category === cat);
              return (
                <div key={cat}>
                  <div className="flex items-center gap-2 mb-3">
                    <CatIcon className="w-4 h-4 text-gray-500" />
                    <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">{cat}</h3>
                    <span className="text-[10px] text-gray-600 font-mono">({items.length})</span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                    {items.map((item) => (
                      <div
                        key={item.id}
                        className="bg-gray-900/70 border border-gray-800/50 rounded-xl p-4 hover:border-cyan-700/40 transition-all group"
                      >
                        <p className="text-sm font-bold text-white mb-1">{item.name}</p>
                        <p className="text-[10px] text-gray-500 leading-relaxed mb-3 min-h-[28px]">
                          {item.description}
                        </p>
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <span className="text-lg font-black text-cyan-300 font-mono">{fmtUsd(item.price)}</span>
                            <span className="text-[10px] text-gray-500 ml-2 font-mono">
                              {item.credit_cost} credits
                            </span>
                          </div>
                        </div>
                        <button
                          onClick={() => handlePurchaseOutput(item)}
                          disabled={actionLoading === item.id}
                          className="w-full py-2 text-xs font-bold bg-cyan-600/20 text-cyan-300 rounded-lg border border-cyan-700/30 hover:bg-cyan-600/30 hover:border-cyan-500/50 transition-all disabled:opacity-50"
                        >
                          {actionLoading === item.id ? "Processing..." : "Purchase"}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ═══ 7. RECOMMENDED ACTIONS ═══ */}
      {recommendedActions.length > 0 && (
        <section>
          <h2 className="text-sm font-bold text-emerald-400/80 uppercase tracking-widest mb-4">
            Recommended Actions
          </h2>
          <div className="space-y-2">
            {recommendedActions.map((a) => (
              <a
                key={a.rank}
                href={a.target_url}
                className="flex items-center gap-4 bg-gray-900/70 border border-gray-800/50 rounded-xl px-5 py-4 hover:border-emerald-600/40 hover:shadow-[0_0_15px_rgba(16,185,129,0.08)] transition-all group"
              >
                <div className="w-9 h-9 rounded-lg bg-emerald-500/10 flex items-center justify-center flex-shrink-0">
                  <span className="text-sm font-black text-emerald-400 font-mono">#{a.rank}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white font-medium group-hover:text-emerald-300 transition-colors">
                    {a.title}
                  </p>
                  <p className="text-[10px] text-gray-500 font-mono mt-0.5">{a.target_section}</p>
                </div>
                <div className="text-right flex-shrink-0">
                  <span className="text-lg font-black text-emerald-400 font-mono">+{a.expected_impact_pct}%</span>
                  <p className="text-[10px] text-gray-500">expected impact</p>
                </div>
                <ArrowRight className="w-4 h-4 text-gray-600 group-hover:text-emerald-400 transition-colors flex-shrink-0" />
              </a>
            ))}
          </div>
        </section>
      )}

      {/* ═══ FOOTER ═══ */}
      <section className="border-t border-cyan-900/20 pt-6 flex flex-wrap gap-4">
        <a
          href="/dashboard/monetization"
          className="inline-flex items-center gap-3 bg-gradient-to-r from-cyan-900/40 to-emerald-900/40 border border-cyan-700/30 rounded-xl px-6 py-4 hover:border-cyan-500/50 transition-all group"
        >
          <CreditCard className="w-5 h-5 text-cyan-400" />
          <div>
            <p className="text-cyan-300 font-bold text-sm">Monetization Center</p>
            <p className="text-gray-500 text-[10px]">Credits, plans, billing</p>
          </div>
        </a>
        <a
          href="/dashboard/revenue-intelligence"
          className="inline-flex items-center gap-3 bg-gradient-to-r from-emerald-900/40 to-cyan-900/40 border border-emerald-700/30 rounded-xl px-6 py-4 hover:border-emerald-500/50 transition-all group"
        >
          <TrendingUp className="w-5 h-5 text-emerald-400" />
          <div>
            <p className="text-emerald-300 font-bold text-sm">Revenue Intelligence</p>
            <p className="text-gray-500 text-[10px]">Forecasts, anomalies, LTV</p>
          </div>
        </a>
        <a
          href="/dashboard/copilot"
          className="inline-flex items-center gap-3 bg-gradient-to-r from-amber-900/40 to-cyan-900/40 border border-amber-700/30 rounded-xl px-6 py-4 hover:border-amber-500/50 transition-all group"
        >
          <Sparkles className="w-5 h-5 text-amber-400" />
          <div>
            <p className="text-amber-300 font-bold text-sm">Operator Copilot</p>
            <p className="text-gray-500 text-[10px]">Ask about anything</p>
          </div>
        </a>
      </section>
    </div>
  );
}
