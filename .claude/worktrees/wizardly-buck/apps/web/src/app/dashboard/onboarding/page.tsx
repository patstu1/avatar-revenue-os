"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

/* ------------------------------------------------------------------ */
/*  Types                                                             */
/* ------------------------------------------------------------------ */

interface OnboardingStatus {
  is_complete: boolean;
  current_step: number;
  has_brand: boolean;
  has_accounts: boolean;
  has_offer: boolean;
  has_content: boolean;
  first_brand_id: string | null;
  free_credits_remaining: number;
}

interface BrandResult {
  id: string;
  name: string;
  slug: string;
  niche: string;
}

interface OfferResult {
  id: string;
  name: string;
  monetization_method: string;
}

interface GenerateResult {
  brief_id: string;
  script_id: string;
  title: string;
  hook: string;
  body: string;
  cta: string;
  full_script: string;
  quality_score: number;
  credits_used: number;
  credits_remaining: number;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                         */
/* ------------------------------------------------------------------ */

const PLATFORMS = [
  { key: "youtube", label: "YouTube", icon: "▶️" },
  { key: "tiktok", label: "TikTok", icon: "🎵" },
  { key: "instagram", label: "Instagram", icon: "📸" },
  { key: "x", label: "X (Twitter)", icon: "𝕏" },
  { key: "threads", label: "Threads", icon: "🧵" },
  { key: "facebook", label: "Facebook", icon: "📘" },
  { key: "linkedin", label: "LinkedIn", icon: "💼" },
  { key: "reddit", label: "Reddit", icon: "🔴" },
  { key: "snapchat", label: "Snapchat", icon: "👻" },
  { key: "pinterest", label: "Pinterest", icon: "📌" },
  { key: "rumble", label: "Rumble", icon: "🎬" },
  { key: "twitch", label: "Twitch", icon: "🎮" },
  { key: "kick", label: "Kick", icon: "⚡" },
  { key: "clapper", label: "Clapper", icon: "👏" },
  { key: "lemon8", label: "Lemon8", icon: "🍋" },
  { key: "bereal", label: "BeReal", icon: "📷" },
  { key: "bluesky", label: "Bluesky", icon: "🦋" },
  { key: "mastodon", label: "Mastodon", icon: "🐘" },
  { key: "telegram", label: "Telegram", icon: "✈️" },
  { key: "discord", label: "Discord", icon: "💬" },
  { key: "whatsapp", label: "WhatsApp", icon: "📱" },
  { key: "wechat", label: "WeChat", icon: "🟢" },
  { key: "quora", label: "Quora", icon: "❓" },
  { key: "medium", label: "Medium", icon: "✍️" },
  { key: "substack", label: "Substack", icon: "📰" },
  { key: "spotify", label: "Spotify", icon: "🎧" },
  { key: "apple_podcasts", label: "Apple Podcasts", icon: "🎙️" },
  { key: "blog", label: "Blog / Website", icon: "🌐" },
  { key: "email_newsletter", label: "Email Newsletter", icon: "📧" },
  { key: "seo_authority", label: "SEO / Authority Site", icon: "🔍" },
];

const MONETIZATION_METHODS = [
  { key: "affiliate", label: "Affiliate", desc: "Earn commissions promoting products" },
  { key: "adsense", label: "Ad Revenue", desc: "YouTube/platform ad monetization" },
  { key: "product", label: "Product", desc: "Sell your own digital/physical products" },
  { key: "course", label: "Course", desc: "Sell educational content" },
  { key: "consulting", label: "Consulting", desc: "High-ticket 1:1 services" },
  { key: "membership", label: "Membership", desc: "Recurring subscription revenue" },
  { key: "sponsor", label: "Sponsorship", desc: "Brand deals and sponsorships" },
  { key: "lead_gen", label: "Lead Gen", desc: "Capture leads for services or funnels" },
];

const TOTAL_STEPS = 5;

/* ------------------------------------------------------------------ */
/*  Progress Bar                                                      */
/* ------------------------------------------------------------------ */

function ProgressBar({ step }: { step: number }) {
  return (
    <div className="w-full max-w-md mx-auto mb-8">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-400 font-mono">
          Step {step} of {TOTAL_STEPS}
        </span>
        <span className="text-xs text-cyan-400 font-mono">
          {Math.round((step / TOTAL_STEPS) * 100)}%
        </span>
      </div>
      <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full transition-all duration-700 ease-out"
          style={{ width: `${(step / TOTAL_STEPS) * 100}%` }}
        />
      </div>
      <div className="flex justify-between mt-2">
        {Array.from({ length: TOTAL_STEPS }, (_, i) => (
          <div
            key={i}
            className={`w-2 h-2 rounded-full transition-all duration-300 ${
              i + 1 <= step
                ? "bg-cyan-400 shadow-[0_0_6px_rgba(34,211,238,0.6)]"
                : "bg-gray-700"
            }`}
          />
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Step 1: Welcome & Brand Setup                                     */
/* ------------------------------------------------------------------ */

function StepWelcome({
  onNext,
}: {
  onNext: (brand: BrandResult) => void;
}) {
  const [name, setName] = useState("");
  const [niche, setNiche] = useState("");
  const [audience, setAudience] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!name.trim() || !niche.trim()) {
      setError("Brand name and niche are required.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const brand = await apiFetch<BrandResult>("/api/v1/onboarding/quick-brand", {
        method: "POST",
        body: JSON.stringify({ name, niche, target_audience: audience }),
      });
      onNext(brand);
    } catch (err: any) {
      setError(err?.message || "Failed to create brand");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-lg mx-auto text-center">
      <div className="mb-8">
        <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-cyan-500/20 to-blue-500/20 border border-cyan-800/50 flex items-center justify-center">
          <span className="text-3xl">⚡</span>
        </div>
        <h1 className="text-3xl font-black bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
          Welcome to Revenue OS
        </h1>
        <p className="text-gray-400 mt-2 text-sm">
          Let&apos;s set up your revenue machine in 5 minutes.
        </p>
      </div>

      <div className="space-y-4 text-left">
        <div>
          <label className="block text-xs text-gray-400 font-mono uppercase mb-1.5">
            Brand Name
          </label>
          <input
            type="text"
            placeholder="e.g. FitnessPro, TechReviews, CookingDaily"
            className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none transition-colors"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 font-mono uppercase mb-1.5">
            Niche
          </label>
          <input
            type="text"
            placeholder="e.g. fitness, tech reviews, personal finance"
            className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none transition-colors"
            value={niche}
            onChange={(e) => setNiche(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 font-mono uppercase mb-1.5">
            Target Audience{" "}
            <span className="text-gray-600">(optional)</span>
          </label>
          <input
            type="text"
            placeholder="e.g. 25-35 year old men interested in home workouts"
            className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none transition-colors"
            value={audience}
            onChange={(e) => setAudience(e.target.value)}
          />
        </div>
      </div>

      {error && (
        <p className="mt-3 text-sm text-red-400">{error}</p>
      )}

      <button
        onClick={handleSubmit}
        disabled={loading}
        className="mt-6 w-full py-3.5 bg-gradient-to-r from-cyan-600 to-blue-600 text-white font-bold rounded-xl hover:from-cyan-500 hover:to-blue-500 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            Creating...
          </span>
        ) : (
          "Create Brand & Continue"
        )}
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Step 2: Connect Accounts                                          */
/* ------------------------------------------------------------------ */

function StepConnect({
  brandId,
  onNext,
  onSkip,
}: {
  brandId: string;
  onNext: () => void;
  onSkip: () => void;
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [usernames, setUsernames] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<Set<string>>(new Set());

  const toggle = (key: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const setUsername = (key: string, value: string) => {
    setUsernames((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    const toCreate = Array.from(selected).filter(
      (k) => usernames[k]?.trim() && !saved.has(k)
    );
    if (toCreate.length === 0) {
      onNext();
      return;
    }
    setSaving(true);
    setError("");
    try {
      for (const platform of toCreate) {
        await apiFetch("/api/v1/accounts/", {
          method: "POST",
          body: JSON.stringify({
            brand_id: brandId,
            platform,
            platform_username: usernames[platform].trim(),
            account_type: "ORGANIC",
          }),
        });
        setSaved((prev) => new Set(prev).add(platform));
      }
      onNext();
    } catch (err: any) {
      setError(err?.message || "Failed to create account");
    } finally {
      setSaving(false);
    }
  };

  const selectedPlatforms = PLATFORMS.filter((p) => selected.has(p.key));

  return (
    <div className="max-w-2xl mx-auto text-center">
      <div className="mb-6">
        <h2 className="text-2xl font-black text-white">Connect Your Accounts</h2>
        <p className="text-gray-400 mt-2 text-sm">
          Select your platforms, then enter your username for each one.
        </p>
      </div>

      <div className="max-h-[280px] overflow-y-auto pr-1 mb-4">
        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2">
          {PLATFORMS.map((p) => (
            <button
              key={p.key}
              onClick={() => toggle(p.key)}
              className={`flex flex-col items-center gap-1.5 p-3 rounded-xl border transition-all ${
                selected.has(p.key)
                  ? "border-cyan-500 bg-cyan-950/30 shadow-[0_0_15px_rgba(34,211,238,0.15)]"
                  : "border-gray-700 bg-gray-900/60 hover:border-gray-600"
              }`}
            >
              <span className="text-xl">{p.icon}</span>
              <span className="text-xs text-white font-medium text-center leading-tight">{p.label}</span>
              {selected.has(p.key) && (
                <span className="text-[9px] text-cyan-400 font-mono">
                  {saved.has(p.key) ? "SAVED" : "SELECTED"}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {selectedPlatforms.length > 0 && (
        <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-4 mb-4 text-left space-y-3">
          <p className="text-xs text-cyan-400 font-mono uppercase">
            Enter your username for each platform
          </p>
          {selectedPlatforms.map((p) => (
            <div key={p.key} className="flex items-center gap-3">
              <span className="text-lg w-8 text-center shrink-0">{p.icon}</span>
              <span className="text-sm text-gray-300 w-28 shrink-0">{p.label}</span>
              <input
                type="text"
                placeholder={`@username`}
                className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none transition-colors"
                value={usernames[p.key] || ""}
                onChange={(e) => setUsername(p.key, e.target.value)}
                disabled={saved.has(p.key)}
              />
              {saved.has(p.key) && (
                <span className="text-xs text-green-400 font-mono">✓</span>
              )}
            </div>
          ))}
        </div>
      )}

      {error && <p className="mb-3 text-sm text-red-400">{error}</p>}

      <div className="flex gap-3">
        <button
          onClick={onSkip}
          className="flex-1 py-3 border border-gray-700 text-gray-400 rounded-xl hover:border-gray-600 hover:text-gray-300 transition-colors text-sm"
        >
          Skip for now
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex-1 py-3 bg-gradient-to-r from-cyan-600 to-blue-600 text-white font-bold rounded-xl hover:from-cyan-500 hover:to-blue-500 transition-all disabled:opacity-50"
        >
          {saving ? (
            <span className="flex items-center justify-center gap-2">
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Saving...
            </span>
          ) : selected.size > 0
            ? `Save ${selected.size} Account${selected.size > 1 ? "s" : ""} & Continue`
            : "Continue"}
        </button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Step 3: Add First Offer                                           */
/* ------------------------------------------------------------------ */

function StepOffer({
  brandId,
  onNext,
  onSkip,
}: {
  brandId: string;
  onNext: (offer: OfferResult) => void;
  onSkip: () => void;
}) {
  const [name, setName] = useState("");
  const [method, setMethod] = useState("affiliate");
  const [url, setUrl] = useState("");
  const [payout, setPayout] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError("Offer name is required.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const offer = await apiFetch<OfferResult>("/api/v1/onboarding/quick-offer", {
        method: "POST",
        body: JSON.stringify({
          brand_id: brandId,
          name,
          monetization_method: method,
          offer_url: url,
          payout_amount: parseFloat(payout) || 0,
        }),
      });
      onNext(offer);
    } catch (err: any) {
      setError(err?.message || "Failed to create offer");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-lg mx-auto text-center">
      <div className="mb-8">
        <h2 className="text-2xl font-black text-white">Add Your First Offer</h2>
        <p className="text-gray-400 mt-2 text-sm">
          What are you monetizing? We&apos;ll help you optimize this over time.
        </p>
      </div>

      <div className="space-y-4 text-left">
        <div>
          <label className="block text-xs text-gray-400 font-mono uppercase mb-1.5">
            Monetization Method
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {MONETIZATION_METHODS.map((m) => (
              <button
                key={m.key}
                onClick={() => setMethod(m.key)}
                className={`p-3 rounded-xl border text-left transition-all ${
                  method === m.key
                    ? "border-cyan-500 bg-cyan-950/30"
                    : "border-gray-700 bg-gray-900/60 hover:border-gray-600"
                }`}
              >
                <p className="text-sm font-medium text-white">{m.label}</p>
                <p className="text-[10px] text-gray-500 mt-0.5">{m.desc}</p>
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-xs text-gray-400 font-mono uppercase mb-1.5">
            Offer Name
          </label>
          <input
            type="text"
            placeholder="e.g. My Fitness E-Book, Affiliate Product X"
            className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none transition-colors"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-400 font-mono uppercase mb-1.5">
              URL <span className="text-gray-600">(optional)</span>
            </label>
            <input
              type="url"
              placeholder="https://..."
              className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none transition-colors"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 font-mono uppercase mb-1.5">
              Payout ($) <span className="text-gray-600">(optional)</span>
            </label>
            <input
              type="number"
              placeholder="0.00"
              className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none transition-colors"
              value={payout}
              onChange={(e) => setPayout(e.target.value)}
            />
          </div>
        </div>
      </div>

      {error && <p className="mt-3 text-sm text-red-400">{error}</p>}

      <div className="flex gap-3 mt-6">
        <button
          onClick={onSkip}
          className="flex-1 py-3 border border-gray-700 text-gray-400 rounded-xl hover:border-gray-600 hover:text-gray-300 transition-colors text-sm"
        >
          Skip for now
        </button>
        <button
          onClick={handleSubmit}
          disabled={loading}
          className="flex-1 py-3.5 bg-gradient-to-r from-cyan-600 to-blue-600 text-white font-bold rounded-xl hover:from-cyan-500 hover:to-blue-500 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Saving...
            </span>
          ) : (
            "Save Offer & Continue"
          )}
        </button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Step 4: Generate First Content                                    */
/* ------------------------------------------------------------------ */

function StepGenerate({
  brandId,
  onNext,
}: {
  brandId: string;
  onNext: (result: GenerateResult) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GenerateResult | null>(null);
  const [error, setError] = useState("");
  const [animScore, setAnimScore] = useState(0);

  const generate = async () => {
    setError("");
    setLoading(true);
    setAnimScore(0);

    const scoreInterval = setInterval(() => {
      setAnimScore((prev) => Math.min(prev + Math.random() * 12, 78));
    }, 200);

    try {
      const res = await apiFetch<GenerateResult>(
        `/api/v1/onboarding/quick-generate/${brandId}`,
        { method: "POST" }
      );
      clearInterval(scoreInterval);
      setAnimScore(res.quality_score);
      setResult(res);
    } catch (err: any) {
      clearInterval(scoreInterval);
      setError(err?.message || "Generation failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-lg mx-auto text-center">
      <div className="mb-8">
        <h2 className="text-2xl font-black text-white">
          {result ? "Your First Content Piece" : "Let\u2019s See the Magic"}
        </h2>
        <p className="text-gray-400 mt-2 text-sm">
          {result
            ? "Here's your AI-generated content brief and script."
            : "One click and our AI generates a content brief + script tailored to your niche and offer."}
        </p>
      </div>

      {!result && !loading && (
        <button
          onClick={generate}
          className="mx-auto flex items-center gap-3 px-8 py-4 bg-gradient-to-r from-cyan-600 to-blue-600 text-white font-bold rounded-2xl hover:from-cyan-500 hover:to-blue-500 transition-all shadow-[0_0_30px_rgba(34,211,238,0.2)] hover:shadow-[0_0_40px_rgba(34,211,238,0.3)]"
        >
          <span className="text-xl">✨</span>
          Generate My First Content
        </button>
      )}

      {loading && (
        <div className="space-y-6">
          <div className="w-20 h-20 mx-auto rounded-full border-2 border-cyan-500/30 flex items-center justify-center relative">
            <div className="absolute inset-0 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
            <span className="text-lg font-black text-cyan-400">{Math.round(animScore)}</span>
          </div>
          <p className="text-sm text-gray-400 animate-pulse">
            Generating content brief &amp; script...
          </p>
        </div>
      )}

      {result && (
        <div className="space-y-4 text-left">
          <div className="flex items-center justify-between bg-gray-900/80 border border-cyan-800/40 rounded-xl p-4">
            <div>
              <p className="text-xs text-gray-500 font-mono uppercase">Quality Score</p>
              <p className="text-3xl font-black text-cyan-400">{result.quality_score}</p>
            </div>
            <div className="text-right">
              <p className="text-xs text-gray-500 font-mono uppercase">Credits Used</p>
              <p className="text-lg font-bold text-white">{result.credits_used}</p>
              <p className="text-[10px] text-gray-500">{result.credits_remaining} remaining</p>
            </div>
          </div>

          <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-4">
            <p className="text-xs text-cyan-400 font-mono uppercase mb-2">{result.title}</p>
            <div className="space-y-3 text-sm text-gray-300">
              <div>
                <p className="text-[10px] text-gray-500 font-mono mb-1">HOOK</p>
                <p className="text-white font-medium">{result.hook}</p>
              </div>
              <div>
                <p className="text-[10px] text-gray-500 font-mono mb-1">BODY</p>
                <p>{result.body}</p>
              </div>
              <div>
                <p className="text-[10px] text-gray-500 font-mono mb-1">CTA</p>
                <p className="text-cyan-300">{result.cta}</p>
              </div>
            </div>
          </div>

          <button
            onClick={() => onNext(result)}
            className="w-full py-3.5 bg-gradient-to-r from-cyan-600 to-blue-600 text-white font-bold rounded-xl hover:from-cyan-500 hover:to-blue-500 transition-all"
          >
            Go to My Dashboard
          </button>
        </div>
      )}

      {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Step 5: Dashboard Tour                                            */
/* ------------------------------------------------------------------ */

function StepDashboard() {
  const router = useRouter();

  return (
    <div className="max-w-lg mx-auto text-center">
      <div className="mb-8">
        <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-green-500/20 to-cyan-500/20 border border-green-800/50 flex items-center justify-center">
          <span className="text-3xl">🚀</span>
        </div>
        <h2 className="text-2xl font-black text-white">You&apos;re All Set!</h2>
        <p className="text-gray-400 mt-2 text-sm">
          Your revenue machine is ready. Here&apos;s what to do next.
        </p>
      </div>

      <div className="bg-gradient-to-br from-cyan-950/40 to-blue-950/40 border border-cyan-800/30 rounded-2xl p-6 mb-6">
        <div className="flex items-center gap-3 mb-3">
          <span className="w-3 h-3 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)] animate-pulse" />
          <p className="text-sm font-bold text-cyan-300">Your first 50 credits are loaded</p>
        </div>
        <p className="text-sm text-gray-400 text-left">
          Each credit lets you generate content, run experiments, or optimize your offers.
          Use them to discover what works best for your audience.
        </p>
      </div>

      <div className="space-y-3 mb-6">
        <button
          onClick={() => router.push("/dashboard/command-center")}
          className="w-full flex items-center gap-4 p-4 bg-gray-900/60 border border-gray-800 rounded-xl hover:border-cyan-700 transition-all text-left group"
        >
          <div className="w-10 h-10 rounded-lg bg-cyan-900/40 flex items-center justify-center shrink-0">
            <span className="text-lg">📊</span>
          </div>
          <div>
            <p className="text-sm font-bold text-white group-hover:text-cyan-300 transition-colors">
              Generate More Content
            </p>
            <p className="text-xs text-gray-500">Create optimized content for every platform</p>
          </div>
        </button>

        <button
          onClick={() => router.push("/dashboard/revenue-intelligence")}
          className="w-full flex items-center gap-4 p-4 bg-gray-900/60 border border-gray-800 rounded-xl hover:border-cyan-700 transition-all text-left group"
        >
          <div className="w-10 h-10 rounded-lg bg-blue-900/40 flex items-center justify-center shrink-0">
            <span className="text-lg">💰</span>
          </div>
          <div>
            <p className="text-sm font-bold text-white group-hover:text-cyan-300 transition-colors">
              View Revenue Intelligence
            </p>
            <p className="text-xs text-gray-500">
              Track every dollar across platforms and offers
            </p>
          </div>
        </button>

        <button
          onClick={() => router.push("/dashboard/revenue-avenues")}
          className="w-full flex items-center gap-4 p-4 bg-gray-900/60 border border-gray-800 rounded-xl hover:border-cyan-700 transition-all text-left group"
        >
          <div className="w-10 h-10 rounded-lg bg-purple-900/40 flex items-center justify-center shrink-0">
            <span className="text-lg">🛤️</span>
          </div>
          <div>
            <p className="text-sm font-bold text-white group-hover:text-cyan-300 transition-colors">
              Explore Revenue Avenues
            </p>
            <p className="text-xs text-gray-500">
              Discover new monetization channels and opportunities
            </p>
          </div>
        </button>
      </div>

      <button
        onClick={() => router.push("/dashboard")}
        className="w-full py-3.5 bg-gradient-to-r from-cyan-600 to-blue-600 text-white font-bold rounded-xl hover:from-cyan-500 hover:to-blue-500 transition-all"
      >
        Enter Your Dashboard
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Wizard                                                       */
/* ------------------------------------------------------------------ */

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [brandId, setBrandId] = useState<string | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);

  const resumeFromStatus = useCallback(
    (status: OnboardingStatus) => {
      if (status.is_complete) {
        router.replace("/dashboard");
        return;
      }
      if (status.first_brand_id) setBrandId(status.first_brand_id);
      setStep(status.current_step);
    },
    [router]
  );

  useEffect(() => {
    apiFetch<OnboardingStatus>("/api/v1/onboarding/status")
      .then(resumeFromStatus)
      .catch(() => {})
      .finally(() => setInitialLoading(false));
  }, [resumeFromStatus]);

  if (initialLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
          <p className="text-sm text-gray-500 font-mono">Loading onboarding...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[80vh] flex flex-col items-center justify-center px-4 py-12">
      <ProgressBar step={step} />

      <div className="w-full transition-all duration-500">
        {step === 1 && (
          <StepWelcome
            onNext={(brand) => {
              setBrandId(brand.id);
              setStep(2);
            }}
          />
        )}

        {step === 2 && brandId && (
          <StepConnect
            brandId={brandId}
            onNext={() => setStep(3)}
            onSkip={() => setStep(3)}
          />
        )}

        {step === 3 && brandId && (
          <StepOffer
            brandId={brandId}
            onNext={() => setStep(4)}
            onSkip={() => setStep(4)}
          />
        )}

        {step === 4 && brandId && (
          <StepGenerate
            brandId={brandId}
            onNext={() => setStep(5)}
          />
        )}

        {step === 5 && <StepDashboard />}
      </div>
    </div>
  );
}
