"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface CreditBalance {
  total_credits: number;
  used_credits: number;
  remaining_credits: number;
  bonus_credits: number;
  replenishment_rate: number;
  overage_enabled: boolean;
  overage_rate: number;
  next_replenishment_at: string | null;
}

interface Meter {
  meter_type: string;
  units_used: number;
  units_limit: number;
  utilization_pct: number;
  overage_units: number;
  overage_cost: number;
}

interface UsageSummary {
  period_start: string;
  period_end: string;
  meters: Meter[];
  total_units_used: number;
  total_units_limit: number;
  total_overage_cost: number;
}

interface PlanDetails {
  plan_tier: string;
  plan_name: string;
  monthly_price: number;
  billing_interval: string;
  included_credits: number;
  max_seats: number;
  max_brands: number;
  features: string[];
  meter_limits: Record<string, number>;
  status: string;
  started_at: string | null;
  current_period_end: string | null;
}

interface AscensionTrigger {
  trigger: string;
  label: string;
  urgency: number;
  context: string;
  upgrade_tiers: string[];
}

interface AscensionProfile {
  current_tier: string;
  active_triggers: AscensionTrigger[];
  trigger_count: number;
  recommended_plan: { tier: string; name: string; monthly_price: number; included_credits: number } | null;
  annual_savings: number;
  ascension_score: number;
  credit_balance: CreditBalance;
  usage_summary: UsageSummary;
}

interface MultiplicationOpp {
  type: string;
  message: string;
  recommended_pack?: string;
  recommended_tier?: string;
  urgency: number;
}

interface MultiplicationData {
  opportunities: MultiplicationOpp[];
  total_opportunities: number;
  recent_offers_24h: number;
}

interface HealthReport {
  health_score: number;
  plan_tier: string;
  credit_utilization_pct: number;
  monthly_pack_revenue: number;
  monthly_pack_purchases: number;
  subscription_mrr: number;
  total_mrr: number;
  multiplication: {
    offered_30d: number;
    converted_30d: number;
    conversion_rate_pct: number;
    revenue_30d: number;
  };
  usage_summary: UsageSummary;
  credit_balance: CreditBalance;
}

interface PricingTier {
  tier: string;
  name: string;
  monthly_price: number;
  annual_price: number;
  included_credits: number;
  max_seats: number;
  max_brands: number;
  features: string[];
  meter_limits: Record<string, number>;
}

interface Pack {
  pack_id: string;
  pack_type: string;
  name: string;
  price: number;
  credits: number;
  items: Record<string, unknown>;
}

const tierColor: Record<string, string> = {
  free: "text-gray-400",
  starter: "text-cyan-400",
  professional: "text-blue-400",
  business: "text-purple-400",
  enterprise: "text-amber-400",
};

const tierBorder: Record<string, string> = {
  free: "border-gray-700/50",
  starter: "border-cyan-700/40",
  professional: "border-blue-700/40",
  business: "border-purple-700/40",
  enterprise: "border-amber-700/40",
};

const tierGlow: Record<string, string> = {
  free: "",
  starter: "shadow-[0_0_15px_rgba(34,211,238,0.15)]",
  professional: "shadow-[0_0_15px_rgba(59,130,246,0.15)]",
  business: "shadow-[0_0_15px_rgba(168,85,247,0.15)]",
  enterprise: "shadow-[0_0_20px_rgba(245,158,11,0.2)]",
};

function HealthGauge({ score }: { score: number }) {
  const rotation = (score / 100) * 180 - 90;
  const color = score >= 75 ? "#22d3ee" : score >= 50 ? "#f59e0b" : "#ef4444";
  return (
    <div className="relative w-40 h-20 mx-auto overflow-hidden">
      <div className="absolute inset-0 border-[6px] border-gray-800 rounded-t-full" />
      <div
        className="absolute inset-0 border-[6px] rounded-t-full"
        style={{
          borderColor: color,
          clipPath: `polygon(0 100%, 0 0, ${score}% 0, ${score}% 100%)`,
        }}
      />
      <div
        className="absolute bottom-0 left-1/2 w-1 h-16 origin-bottom transition-transform duration-700"
        style={{ transform: `translateX(-50%) rotate(${rotation}deg)`, background: color }}
      />
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-4 h-4 rounded-full bg-gray-900 border-2" style={{ borderColor: color }} />
    </div>
  );
}

function UsageBar({ used, limit, label }: { used: number; limit: number; label: string }) {
  const pct = limit > 0 ? Math.min((used / limit) * 100, 100) : 0;
  const barColor = pct >= 90 ? "bg-red-500" : pct >= 70 ? "bg-amber-500" : "bg-cyan-500";
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-gray-400">{label}</span>
        <span className="text-gray-300 font-mono">{used.toLocaleString()} / {limit === -1 ? "∞" : limit.toLocaleString()}</span>
      </div>
      <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${barColor}`} style={{ width: `${limit === -1 ? 5 : pct}%` }} />
      </div>
    </div>
  );
}

export default function MonetizationPage() {
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState<HealthReport | null>(null);
  const [ascension, setAscension] = useState<AscensionProfile | null>(null);
  const [multiplication, setMultiplication] = useState<MultiplicationData | null>(null);
  const [pricing, setPricing] = useState<PricingTier[]>([]);
  const [packs, setPacks] = useState<Pack[]>([]);
  const [plan, setPlan] = useState<PlanDetails | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [purchasing, setPurchasing] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      apiFetch<HealthReport>("/api/v1/monetization/health").catch(() => null),
      apiFetch<AscensionProfile>("/api/v1/monetization/ascension").catch(() => null),
      apiFetch<MultiplicationData>("/api/v1/monetization/multiplication-opportunities").catch(() => null),
      apiFetch<PricingTier[]>("/api/v1/monetization/pricing").catch(() => []),
      apiFetch<Pack[]>("/api/v1/monetization/packs").catch(() => []),
      apiFetch<PlanDetails>("/api/v1/monetization/plan").catch(() => null),
      apiFetch<UsageSummary>("/api/v1/monetization/usage").catch(() => null),
    ]).then(([h, a, m, pr, pk, pl, u]) => {
      setHealth(h);
      setAscension(a);
      setMultiplication(m);
      setPricing(pr as PricingTier[]);
      setPacks(pk as Pack[]);
      setPlan(pl);
      setUsage(u);
    }).finally(() => setLoading(false));
  }, []);

  const handlePurchase = async (packId: string) => {
    setPurchasing(packId);
    try {
      await apiFetch("/api/v1/monetization/credits/purchase", {
        method: "POST",
        body: JSON.stringify({ pack_id: packId }),
      });
      const [newHealth, newAscension] = await Promise.all([
        apiFetch<HealthReport>("/api/v1/monetization/health").catch(() => null),
        apiFetch<AscensionProfile>("/api/v1/monetization/ascension").catch(() => null),
      ]);
      if (newHealth) setHealth(newHealth);
      if (newAscension) setAscension(newAscension);
    } catch (err) {
      console.error("Credit purchase failed:", err);
    }
    setPurchasing(null);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh] bg-gray-950">
        <div className="text-cyan-400 text-lg animate-pulse">INITIALIZING MONETIZATION ENGINE...</div>
      </div>
    );
  }

  const bal = health?.credit_balance || ascension?.credit_balance;
  const exhaustionDays = bal && bal.replenishment_rate > 0
    ? Math.ceil(bal.remaining_credits / Math.max(bal.replenishment_rate / 30, 1))
    : null;

  return (
    <div className="min-h-screen bg-gray-950 text-white p-6 space-y-8">
      {/* HEADER */}
      <div className="flex items-center justify-between border-b border-cyan-900/30 pb-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight bg-gradient-to-r from-cyan-400 via-blue-500 to-purple-500 bg-clip-text text-transparent">
            MONETIZATION COMMAND CENTER
          </h1>
          <p className="text-gray-500 text-xs mt-1 font-mono">CREDITS • PLANS • PACKS • ASCENSION • MULTIPLICATION</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)] animate-pulse" />
          <span className="text-cyan-400 text-xs font-mono">LIVE</span>
        </div>
      </div>

      {/* CREDIT BALANCE & USAGE */}
      <section>
        <h2 className="text-sm font-bold text-cyan-400/80 uppercase tracking-widest mb-4">Credit Balance &amp; Usage</h2>
        <div className="grid md:grid-cols-3 gap-4">
          {/* Big balance card */}
          <div className="bg-gray-900/60 border border-cyan-900/40 rounded-xl p-6 shadow-[0_0_20px_rgba(34,211,238,0.1)]">
            <p className="text-[10px] text-gray-500 font-mono uppercase">REMAINING CREDITS</p>
            <p className="text-5xl font-black text-cyan-300 mt-2">{(bal?.remaining_credits ?? 0).toLocaleString()}</p>
            <div className="mt-4 h-3 bg-gray-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full transition-all duration-700"
                style={{ width: `${bal ? Math.min((bal.remaining_credits / Math.max(bal.total_credits, 1)) * 100, 100) : 0}%` }}
              />
            </div>
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>{(bal?.used_credits ?? 0).toLocaleString()} used</span>
              <span>{(bal?.total_credits ?? 0).toLocaleString()} total</span>
            </div>
            {exhaustionDays !== null && (
              <p className="text-xs text-amber-400 mt-3 font-mono">
                ~{exhaustionDays} days until empty at current rate
              </p>
            )}
            {bal?.bonus_credits ? (
              <p className="text-xs text-green-400 mt-1">+{bal.bonus_credits.toLocaleString()} bonus credits</p>
            ) : null}
          </div>

          {/* Meter breakdown */}
          <div className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-6 md:col-span-2">
            <p className="text-[10px] text-gray-500 font-mono uppercase mb-4">PER-METER USAGE</p>
            {usage && usage.meters.length > 0 ? (
              <div className="space-y-3">
                {usage.meters.map((m) => (
                  <UsageBar key={m.meter_type} used={m.units_used} limit={m.units_limit} label={m.meter_type.replace(/_/g, " ").toUpperCase()} />
                ))}
              </div>
            ) : (
              <p className="text-gray-600 text-xs">No meter data for this period yet</p>
            )}
            {usage && usage.total_overage_cost > 0 && (
              <p className="text-xs text-red-400 mt-3 font-mono">Overage cost: ${usage.total_overage_cost.toFixed(2)}</p>
            )}
          </div>
        </div>

        {/* Quick-buy packs */}
        <div className="mt-4">
          <p className="text-[10px] text-gray-500 font-mono uppercase mb-3">QUICK BUY CREDIT PACKS</p>
          <div className="flex gap-3 flex-wrap">
            {packs.filter((p) => p.pack_type === "credit_pack").map((p) => (
              <button
                key={p.pack_id}
                onClick={() => handlePurchase(p.pack_id)}
                disabled={purchasing === p.pack_id}
                className="bg-gray-900/80 border border-cyan-800/30 rounded-lg px-4 py-3 hover:border-cyan-500/50 hover:shadow-[0_0_15px_rgba(34,211,238,0.2)] transition-all group disabled:opacity-50"
              >
                <p className="text-sm font-bold text-cyan-300 group-hover:text-cyan-200">{p.name}</p>
                <p className="text-xs text-gray-500 mt-0.5">{p.credits.toLocaleString()} credits • ${p.price}</p>
                {purchasing === p.pack_id && <p className="text-[10px] text-cyan-400 animate-pulse mt-1">Processing...</p>}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* PLAN & ASCENSION */}
      <section>
        <h2 className="text-sm font-bold text-cyan-400/80 uppercase tracking-widest mb-4">Plan &amp; Ascension</h2>
        <div className="grid md:grid-cols-2 gap-4">
          {/* Current plan */}
          <div className={`bg-gray-900/60 border rounded-xl p-6 ${tierBorder[plan?.plan_tier ?? "free"]} ${tierGlow[plan?.plan_tier ?? "free"]}`}>
            <div className="flex items-center gap-3 mb-4">
              <div className={`w-3 h-3 rounded-full ${plan?.plan_tier === "free" ? "bg-gray-500" : "bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.6)]"}`} />
              <div>
                <p className={`text-lg font-black ${tierColor[plan?.plan_tier ?? "free"]}`}>{plan?.plan_name ?? "Starter (Free)"}</p>
                <p className="text-xs text-gray-500">{plan?.plan_tier?.toUpperCase()} TIER</p>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div><p className="text-[10px] text-gray-500">PRICE</p><p className="text-lg font-bold text-white">${plan?.monthly_price ?? 0}<span className="text-xs text-gray-500">/mo</span></p></div>
              <div><p className="text-[10px] text-gray-500">CREDITS</p><p className="text-lg font-bold text-cyan-300">{(plan?.included_credits ?? 100).toLocaleString()}</p></div>
              <div><p className="text-[10px] text-gray-500">SEATS</p><p className="text-lg font-bold text-white">{plan?.max_seats === -1 ? "∞" : plan?.max_seats ?? 1}</p></div>
            </div>
            {plan?.features && plan.features.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-1.5">
                {plan.features.slice(0, 6).map((f) => (
                  <span key={f} className="text-[10px] bg-gray-800 text-gray-400 px-2 py-0.5 rounded-full">{f.replace(/_/g, " ")}</span>
                ))}
                {plan.features.length > 6 && <span className="text-[10px] text-gray-600">+{plan.features.length - 6} more</span>}
              </div>
            )}
          </div>

          {/* Ascension triggers */}
          <div className="bg-gray-900/60 border border-purple-900/30 rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <p className="text-[10px] text-purple-400 font-mono uppercase">UPGRADE TRIGGERS</p>
              {ascension && (
                <span className={`text-xs font-mono px-2 py-0.5 rounded-full ${
                  ascension.trigger_count > 0 ? "bg-purple-900/40 text-purple-300" : "bg-gray-800 text-gray-500"
                }`}>
                  {ascension.trigger_count} active
                </span>
              )}
            </div>
            {ascension && ascension.active_triggers.length > 0 ? (
              <div className="space-y-2">
                {ascension.active_triggers.map((t, i) => (
                  <div key={i} className="border-l-2 border-purple-500 pl-3 py-1">
                    <p className="text-sm text-white font-medium">{t.label}</p>
                    <p className="text-[10px] text-gray-500">{t.context}</p>
                    <div className="mt-1 h-1 bg-gray-800 rounded-full overflow-hidden w-24">
                      <div className="h-full bg-purple-500 rounded-full" style={{ width: `${t.urgency * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-600 text-xs">No active upgrade triggers</p>
            )}
            {ascension?.recommended_plan && (
              <div className="mt-4 p-3 bg-purple-900/20 border border-purple-800/30 rounded-lg">
                <p className="text-xs text-purple-300 font-bold">Recommended: {ascension.recommended_plan.name}</p>
                <p className="text-[10px] text-gray-400 mt-1">
                  ${ascension.recommended_plan.monthly_price}/mo • {ascension.recommended_plan.included_credits.toLocaleString()} credits
                </p>
                {ascension.annual_savings > 0 && (
                  <p className="text-[10px] text-green-400 mt-0.5">Save ${ascension.annual_savings.toFixed(0)}/year with annual billing</p>
                )}
              </div>
            )}
          </div>
        </div>
      </section>

      {/* MONETIZATION HEALTH */}
      <section>
        <h2 className="text-sm font-bold text-cyan-400/80 uppercase tracking-widest mb-4">Monetization Health</h2>
        <div className="grid md:grid-cols-4 gap-4">
          {/* Health gauge */}
          <div className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-6 flex flex-col items-center justify-center">
            {health ? (
              <>
                <HealthGauge score={health.health_score} />
                <p className="text-3xl font-black text-white mt-2">{health.health_score}</p>
                <p className="text-[10px] text-gray-500 font-mono">HEALTH SCORE</p>
              </>
            ) : (
              <p className="text-gray-600 text-xs">No data</p>
            )}
          </div>

          {/* Key metrics */}
          <div className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-6 md:col-span-2">
            <p className="text-[10px] text-gray-500 font-mono uppercase mb-4">KEY METRICS</p>
            <div className="grid grid-cols-2 gap-4">
              {[
                { label: "SUBSCRIPTION MRR", value: `$${health?.subscription_mrr?.toFixed(0) ?? "0"}`, color: "text-cyan-300" },
                { label: "PACK REVENUE (30D)", value: `$${health?.monthly_pack_revenue?.toFixed(0) ?? "0"}`, color: "text-green-400" },
                { label: "CREDIT UTILIZATION", value: `${health?.credit_utilization_pct?.toFixed(0) ?? "0"}%`, color: "text-blue-400" },
                { label: "TOTAL MRR", value: `$${health?.total_mrr?.toFixed(0) ?? "0"}`, color: "text-purple-400" },
              ].map((m, i) => (
                <div key={i}>
                  <p className="text-[10px] text-gray-500">{m.label}</p>
                  <p className={`text-xl font-black ${m.color}`}>{m.value}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Multiplication stats */}
          <div className="bg-gray-900/60 border border-amber-900/30 rounded-xl p-6">
            <p className="text-[10px] text-amber-400 font-mono uppercase mb-4">MULTIPLICATION</p>
            {health?.multiplication ? (
              <div className="space-y-3">
                <div><p className="text-[10px] text-gray-500">OFFERED (30D)</p><p className="text-lg font-bold text-white">{health.multiplication.offered_30d}</p></div>
                <div><p className="text-[10px] text-gray-500">CONVERTED</p><p className="text-lg font-bold text-green-400">{health.multiplication.converted_30d}</p></div>
                <div><p className="text-[10px] text-gray-500">CONV RATE</p><p className="text-lg font-bold text-amber-400">{health.multiplication.conversion_rate_pct}%</p></div>
                <div><p className="text-[10px] text-gray-500">REVENUE</p><p className="text-lg font-bold text-cyan-300">${health.multiplication.revenue_30d.toFixed(0)}</p></div>
              </div>
            ) : (
              <p className="text-gray-600 text-xs">No multiplication data</p>
            )}
          </div>
        </div>
      </section>

      {/* REVENUE MULTIPLICATION OPPORTUNITIES */}
      {multiplication && multiplication.opportunities.length > 0 && (
        <section>
          <h2 className="text-sm font-bold text-amber-400/80 uppercase tracking-widest mb-4">Active Multiplication Opportunities</h2>
          <div className="grid md:grid-cols-3 gap-3">
            {multiplication.opportunities.map((opp, i) => (
              <div key={i} className="bg-gray-900/60 border border-amber-800/30 rounded-xl p-4 hover:border-amber-600/50 transition-all">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`w-2 h-2 rounded-full ${opp.urgency > 0.7 ? "bg-amber-400 animate-pulse" : "bg-amber-600"}`} />
                  <span className="text-xs font-bold text-amber-300 uppercase">{opp.type.replace(/_/g, " ")}</span>
                </div>
                <p className="text-sm text-white">{opp.message}</p>
                <div className="flex items-center gap-2 mt-2">
                  <div className="h-1 flex-1 bg-gray-800 rounded-full overflow-hidden">
                    <div className="h-full bg-amber-500 rounded-full" style={{ width: `${opp.urgency * 100}%` }} />
                  </div>
                  <span className="text-[10px] text-gray-500">{(opp.urgency * 100).toFixed(0)}%</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* PRICING ARCHITECTURE */}
      <section>
        <h2 className="text-sm font-bold text-cyan-400/80 uppercase tracking-widest mb-4">Pricing Architecture</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {pricing.map((tier) => {
            const isCurrentTier = tier.tier === (plan?.plan_tier ?? "free");
            return (
              <div
                key={tier.tier}
                className={`bg-gray-900/60 border rounded-xl p-5 transition-all ${
                  isCurrentTier
                    ? `${tierBorder[tier.tier]} ${tierGlow[tier.tier]} ring-1 ring-cyan-500/20`
                    : "border-gray-800/50 hover:border-gray-700"
                }`}
              >
                {isCurrentTier && <p className="text-[10px] text-cyan-400 font-mono mb-2">CURRENT PLAN</p>}
                <p className={`text-lg font-black ${tierColor[tier.tier]}`}>{tier.name}</p>
                <p className="text-2xl font-black text-white mt-2">
                  ${tier.monthly_price}<span className="text-xs text-gray-500 font-normal">/mo</span>
                </p>
                {tier.annual_price > 0 && (
                  <p className="text-[10px] text-gray-500">${(tier.annual_price / 12).toFixed(0)}/mo annual</p>
                )}
                <div className="mt-3 space-y-1 text-xs">
                  <div className="flex justify-between"><span className="text-gray-500">Credits</span><span className="text-gray-300">{tier.included_credits.toLocaleString()}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Seats</span><span className="text-gray-300">{tier.max_seats === -1 ? "∞" : tier.max_seats}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Brands</span><span className="text-gray-300">{tier.max_brands === -1 ? "∞" : tier.max_brands}</span></div>
                </div>
                <div className="mt-3 flex flex-wrap gap-1">
                  {tier.features.slice(0, 4).map((f: string) => (
                    <span key={f} className="text-[9px] bg-gray-800 text-gray-500 px-1.5 py-0.5 rounded-full">{f.replace(/_/g, " ")}</span>
                  ))}
                  {tier.features.length > 4 && <span className="text-[9px] text-gray-600">+{tier.features.length - 4}</span>}
                </div>
                {!isCurrentTier && tier.tier !== "free" && tier.tier !== "enterprise" && (
                  <button
                    className="mt-4 w-full py-2 rounded-lg text-xs font-bold bg-cyan-600 hover:bg-cyan-500 text-white transition-colors"
                    onClick={async () => {
                      try {
                        const res = await apiFetch<{ checkout_url: string | null; error?: string }>("/api/v1/monetization/subscribe", {
                          method: "POST",
                          body: JSON.stringify({ plan_tier: tier.tier, billing_interval: "monthly" }),
                        });
                        if (res.checkout_url) window.location.href = res.checkout_url;
                      } catch (err) {
                        console.error("Subscribe failed:", err);
                      }
                    }}
                  >
                    Upgrade to {tier.name}
                  </button>
                )}
                {tier.tier === "enterprise" && !isCurrentTier && (
                  <button className="mt-4 w-full py-2 rounded-lg text-xs font-bold bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors">
                    Contact Sales
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* PACK CATALOG */}
      <section>
        <h2 className="text-sm font-bold text-cyan-400/80 uppercase tracking-widest mb-4">Pack Catalog</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {packs.map((p) => (
            <div key={p.pack_id} className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-5 hover:border-cyan-700/40 transition-all group">
              <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-full ${
                p.pack_type === "credit_pack" ? "bg-cyan-900/30 text-cyan-400" :
                p.pack_type === "outcome_pack" ? "bg-purple-900/30 text-purple-400" :
                "bg-amber-900/30 text-amber-400"
              }`}>
                {p.pack_type.replace(/_/g, " ")}
              </span>
              <p className="text-sm font-bold text-white mt-3">{p.name}</p>
              <p className="text-xl font-black text-cyan-300 mt-1">${p.price}</p>
              <p className="text-xs text-gray-500 mt-1">{p.credits.toLocaleString()} credits included</p>
              {Object.keys(p.items).length > 0 && (
                <div className="mt-2 space-y-0.5">
                  {Object.entries(p.items).slice(0, 3).map(([k, v]) => (
                    <p key={k} className="text-[10px] text-gray-400">
                      {k.replace(/_/g, " ")}: {typeof v === "boolean" ? (v ? "Yes" : "No") : String(v)}
                    </p>
                  ))}
                </div>
              )}
              <button
                onClick={() => handlePurchase(p.pack_id)}
                disabled={purchasing === p.pack_id}
                className="mt-3 w-full py-2 text-xs font-bold bg-cyan-600/20 text-cyan-300 rounded-lg border border-cyan-700/30 hover:bg-cyan-600/30 hover:border-cyan-500/50 transition-all disabled:opacity-50"
              >
                {purchasing === p.pack_id ? "Processing..." : "Purchase"}
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* COPILOT LINK */}
      <section className="border-t border-cyan-900/20 pt-6">
        <a href="/dashboard/copilot" className="inline-flex items-center gap-3 bg-gradient-to-r from-cyan-900/40 to-blue-900/40 border border-cyan-700/30 rounded-xl px-6 py-4 hover:border-cyan-500/50 transition-all group">
          <span className="w-3 h-3 rounded-full bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.6)] group-hover:shadow-[0_0_15px_rgba(34,211,238,0.8)] transition-all" />
          <div>
            <p className="text-cyan-300 font-bold">OPERATOR COPILOT</p>
            <p className="text-gray-500 text-xs">Ask about credits, plans, or revenue optimization</p>
          </div>
        </a>
      </section>
    </div>
  );
}
