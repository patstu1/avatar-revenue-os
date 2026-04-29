"use client";

/**
 * AI Buyer Trust Test — public quiz client.
 *
 * Single-page form: identity → 13 yes/no/unknown questions → submit →
 * animated score reveal → Snapshot Review CTA → confirmation.
 *
 * Calls only the public endpoints documented in proofhook-api.ts:
 *   POST /api/v1/ai-search-authority/score
 *   POST /api/v1/ai-search-authority/reports/{report_id}/request-snapshot-review
 *
 * Visual primitives (mint + powder blue + cream on dark cinematic background,
 * frosted translucent cards, soft glow) are scoped to this page only — they
 * do not modify any other marketing surface or the global theme.
 */

import { useEffect, useId, useMemo, useState } from "react";

import {
  proofhookApi,
  type ScoreSubmitResponse,
} from "@/lib/proofhook-api";

type Answer = "yes" | "no" | "unknown";

type Question = {
  key: string;
  prompt: string;
  helper?: string;
};

// Mirrors apps/api/services/ai_search_authority_service._QUESTIONS — keys
// must match exactly so the backend's score rubric maps each answer.
const QUESTIONS: Question[] = [
  {
    key: "machine_readable_homepage",
    prompt: "Does your homepage explain who you are, what you sell, and who you sell to in plain language?",
  },
  {
    key: "about_page",
    prompt: "Do you have a real About / Company page with founder and team information?",
  },
  {
    key: "structured_data",
    prompt: "Does your site have Organization, Service, and Product structured data (JSON-LD)?",
    helper: "If you're not sure, choose Not sure.",
  },
  {
    key: "robots_allows_ai",
    prompt: "Does your robots.txt allow AI crawlers (GPTBot, ClaudeBot, PerplexityBot) — or at minimum not block them?",
  },
  {
    key: "sitemap_present",
    prompt: "Do you have a working sitemap.xml that lists every important page?",
  },
  {
    key: "faq_page",
    prompt: "Do you have a public FAQ page that answers buyer questions in your own voice?",
  },
  {
    key: "comparison_pages",
    prompt: "Do you have public pages comparing your offering to the alternatives buyers consider?",
  },
  {
    key: "proof_assets",
    prompt: "Do you have public case studies, testimonials, or named-customer references on your site?",
  },
  {
    key: "third_party_citations",
    prompt: "Do third parties (publications, podcasts, partners) cite or link to your company?",
  },
  {
    key: "answer_engine_pages",
    prompt: "Do you have content that directly answers the questions buyers ask AI search engines?",
  },
  {
    key: "internal_linking",
    prompt: "Do your pages link to each other in a coherent topic structure?",
  },
  {
    key: "analytics_tracking",
    prompt: "Can you tell when buyers arrive from AI search engines (referrer or UTM tracking)?",
  },
  {
    key: "public_pricing",
    prompt: "Is pricing or a starting cost publicly visible on a package or pricing page?",
  },
];

const VERTICALS: { value: string; label: string }[] = [
  { value: "", label: "Select vertical (optional)" },
  { value: "saas", label: "SaaS" },
  { value: "ai_startups", label: "AI startup" },
  { value: "ecommerce", label: "Ecommerce" },
  { value: "service", label: "Service business" },
  { value: "agency", label: "Agency" },
  { value: "consulting", label: "Consulting" },
  { value: "clinic", label: "Clinic / professional services" },
  { value: "other", label: "Other" },
];

const BUYER_TYPES: { value: string; label: string }[] = [
  { value: "", label: "Select buyer type (optional)" },
  { value: "founder_led", label: "Founder-led" },
  { value: "marketing_led", label: "Marketing-led" },
  { value: "operations_led", label: "Operations-led" },
  { value: "agency_buying", label: "Agency-buying" },
  { value: "other", label: "Other" },
];

type Identity = {
  submitter_name: string;
  submitter_email: string;
  submitter_company: string;
  submitter_url: string;
  submitter_role: string;
  vertical: string;
  buyer_type: string;
};

const EMPTY_IDENTITY: Identity = {
  submitter_name: "",
  submitter_email: "",
  submitter_company: "",
  submitter_url: "",
  submitter_role: "",
  vertical: "",
  buyer_type: "",
};

type ViewState =
  | { kind: "form"; identity: Identity; answers: Record<string, Answer | undefined>; submitting: boolean; error: string | null }
  | { kind: "result"; report: ScoreSubmitResponse; snapshotting: boolean; snapshotError: string | null; snapshotRequested: boolean };


// ─────────────────────────────────────────────────────────────────────
// Animated number — counts from 0 to target over `durationMs`.
// requestAnimationFrame keeps it smooth and pause-tolerant on mobile.
// ─────────────────────────────────────────────────────────────────────

function useCountUp(target: number, durationMs = 1600) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (target <= 0) {
      setValue(0);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      // ease-out cubic so the count decelerates near the final value
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(target * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, durationMs]);
  return value;
}


// ─────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────

export function QuizClient({ headlineFontClass }: { headlineFontClass: string }) {
  const [view, setView] = useState<ViewState>({
    kind: "form",
    identity: EMPTY_IDENTITY,
    answers: {},
    submitting: false,
    error: null,
  });

  const formId = useId();

  // Keep handlers stable across renders for accessibility tools that hash
  // them; the form itself is the canonical source of truth.
  const setIdentityField = (key: keyof Identity, value: string) =>
    setView((v) =>
      v.kind === "form" ? { ...v, identity: { ...v.identity, [key]: value } } : v,
    );

  const setAnswer = (key: string, value: Answer) =>
    setView((v) =>
      v.kind === "form" ? { ...v, answers: { ...v.answers, [key]: value } } : v,
    );

  const answeredCount = view.kind === "form"
    ? QUESTIONS.filter((q) => view.answers[q.key]).length
    : QUESTIONS.length;

  const allAnswered = answeredCount === QUESTIONS.length;

  const identityValid = useMemo(() => {
    if (view.kind !== "form") return false;
    const id = view.identity;
    const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(id.submitter_email.trim());
    return (
      id.submitter_name.trim().length > 0 &&
      emailOk &&
      id.submitter_company.trim().length > 0 &&
      id.submitter_url.trim().length > 0
    );
  }, [view]);

  const canSubmit = view.kind === "form" && identityValid && allAnswered && !view.submitting;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (view.kind !== "form" || !canSubmit) return;
    setView((v) => (v.kind === "form" ? { ...v, submitting: true, error: null } : v));
    try {
      const answersOut: Record<string, Answer> = {};
      for (const q of QUESTIONS) {
        answersOut[q.key] = view.answers[q.key] ?? "unknown";
      }
      const report = await proofhookApi.submitScore({
        ...view.identity,
        answers: answersOut,
      });
      setView({
        kind: "result",
        report,
        snapshotting: false,
        snapshotError: null,
        snapshotRequested: false,
      });
      // Scroll to top of result so the score reveal is visible on mobile.
      if (typeof window !== "undefined") {
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Submission failed";
      setView((v) =>
        v.kind === "form" ? { ...v, submitting: false, error: message } : v,
      );
    }
  }

  async function onRequestSnapshot() {
    if (view.kind !== "result") return;
    if (view.snapshotting || view.snapshotRequested) return;
    setView((v) =>
      v.kind === "result" ? { ...v, snapshotting: true, snapshotError: null } : v,
    );
    try {
      await proofhookApi.requestSnapshotReview(view.report.report_id);
      setView((v) =>
        v.kind === "result"
          ? { ...v, snapshotting: false, snapshotRequested: true }
          : v,
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : "Request failed";
      setView((v) =>
        v.kind === "result" ? { ...v, snapshotting: false, snapshotError: message } : v,
      );
    }
  }

  return (
    <div className="relative">
      {/* Cinematic ambient background — dark gradient with mint + powder
         blue glows. Scoped to this page via z-index 0 + pointer-events-none
         so it can never affect surrounding marketing chrome. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 overflow-hidden rounded-3xl"
      >
        <div className="absolute inset-0 bg-gradient-to-b from-zinc-950 via-zinc-950 to-black" />
        <div className="absolute -top-40 left-1/2 h-[480px] w-[480px] -translate-x-1/2 rounded-full bg-emerald-300/10 blur-[140px]" />
        <div className="absolute -bottom-32 left-10 h-[360px] w-[360px] rounded-full bg-sky-300/10 blur-[140px]" />
        <div className="absolute -bottom-24 right-0 h-[280px] w-[280px] rounded-full bg-emerald-200/[0.06] blur-[120px]" />
      </div>

      {view.kind === "form" ? (
        <form
          id={formId}
          onSubmit={onSubmit}
          data-page="ai-buyer-trust-test"
          data-cta="ai-buyer-trust-test-form"
          className="relative space-y-8 sm:space-y-10"
        >
          <Hero headlineFontClass={headlineFontClass} />

          <FrostedCard glow="mint">
            <CardHeading>About you</CardHeading>
            <p className="mt-2 text-sm text-stone-300">
              We use this to send your score and to follow up with the strongest
              next step. Required fields are marked with an asterisk.
            </p>
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <Field
                label="Name *"
                name="submitter_name"
                value={view.identity.submitter_name}
                onChange={(v) => setIdentityField("submitter_name", v)}
                required
                autoComplete="name"
              />
              <Field
                label="Email *"
                name="submitter_email"
                type="email"
                value={view.identity.submitter_email}
                onChange={(v) => setIdentityField("submitter_email", v)}
                required
                autoComplete="email"
              />
              <Field
                label="Company *"
                name="submitter_company"
                value={view.identity.submitter_company}
                onChange={(v) => setIdentityField("submitter_company", v)}
                required
                autoComplete="organization"
              />
              <Field
                label="Website URL *"
                name="submitter_url"
                type="url"
                placeholder="https://yourcompany.com"
                value={view.identity.submitter_url}
                onChange={(v) => setIdentityField("submitter_url", v)}
                required
                autoComplete="url"
              />
              <Field
                label="Role / title"
                name="submitter_role"
                value={view.identity.submitter_role}
                onChange={(v) => setIdentityField("submitter_role", v)}
                autoComplete="organization-title"
              />
              <SelectField
                label="Vertical / industry"
                name="vertical"
                value={view.identity.vertical}
                onChange={(v) => setIdentityField("vertical", v)}
                options={VERTICALS}
              />
              <SelectField
                label="Buyer type"
                name="buyer_type"
                value={view.identity.buyer_type}
                onChange={(v) => setIdentityField("buyer_type", v)}
                options={BUYER_TYPES}
              />
            </div>
          </FrostedCard>

          <FrostedCard glow="sky">
            <div className="flex items-baseline justify-between gap-4">
              <CardHeading>The 13 questions</CardHeading>
              <p className="font-mono text-xs text-stone-300">
                {answeredCount}/{QUESTIONS.length} answered
              </p>
            </div>
            <p className="mt-2 text-sm text-stone-300">
              Answer with what you know — Not sure is a valid answer and does
              not count against your score.
            </p>
            <ol className="mt-6 space-y-5">
              {QUESTIONS.map((q, idx) => (
                <li
                  key={q.key}
                  className="rounded-xl border border-white/5 bg-white/[0.02] p-4 sm:p-5"
                >
                  <p className="text-stone-100">
                    <span className="mr-2 font-mono text-xs text-emerald-200/80">
                      {String(idx + 1).padStart(2, "0")}
                    </span>
                    {q.prompt}
                  </p>
                  {q.helper && (
                    <p className="mt-1 text-xs text-stone-400">{q.helper}</p>
                  )}
                  <AnswerRow
                    name={q.key}
                    value={view.answers[q.key]}
                    onChange={(v) => setAnswer(q.key, v)}
                  />
                </li>
              ))}
            </ol>
          </FrostedCard>

          {view.error && (
            <p
              role="alert"
              className="rounded-lg border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200"
            >
              {view.error}
            </p>
          )}

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs text-stone-400">
              Free answer-based diagnostic. About 3 minutes.
            </p>
            <button
              type="submit"
              disabled={!canSubmit}
              className={
                "inline-flex w-full items-center justify-center gap-2 rounded-md px-6 py-3 text-sm font-semibold tracking-wide transition-all sm:w-auto " +
                (canSubmit
                  ? "bg-emerald-200 text-zinc-950 shadow-[0_0_30px_-6px_rgba(167,243,208,0.55)] hover:bg-emerald-100"
                  : "cursor-not-allowed bg-white/10 text-stone-400")
              }
            >
              {view.submitting ? "Scoring…" : "Check My Score"}
            </button>
          </div>
        </form>
      ) : (
        <ResultCard
          report={view.report}
          headlineFontClass={headlineFontClass}
          snapshotting={view.snapshotting}
          snapshotRequested={view.snapshotRequested}
          snapshotError={view.snapshotError}
          onRequestSnapshot={onRequestSnapshot}
        />
      )}
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────
// Hero
// ─────────────────────────────────────────────────────────────────────

function Hero({ headlineFontClass }: { headlineFontClass: string }) {
  return (
    <header className="text-center">
      <p className="font-mono text-xs uppercase tracking-[0.25em] text-emerald-200/80">
        AI Buyer Trust Test
      </p>
      <h1
        className={
          "mt-4 text-balance text-4xl uppercase leading-[1.05] tracking-tight text-stone-50 sm:text-5xl md:text-6xl " +
          headlineFontClass
        }
      >
        How easy is your business to find, trust, and choose?
      </h1>
      <p className="mx-auto mt-5 max-w-2xl text-base text-stone-200 sm:text-lg">
        Take the AI Buyer Trust Test and see where your proof, offer, answers,
        and creative presence need work.
      </p>
      <p className="mt-3 text-xs text-stone-400">
        Free answer-based diagnostic. About 3 minutes.
      </p>
    </header>
  );
}


// ─────────────────────────────────────────────────────────────────────
// Result card
// ─────────────────────────────────────────────────────────────────────

function ResultCard({
  report,
  headlineFontClass,
  snapshotting,
  snapshotRequested,
  snapshotError,
  onRequestSnapshot,
}: {
  report: ScoreSubmitResponse;
  headlineFontClass: string;
  snapshotting: boolean;
  snapshotRequested: boolean;
  snapshotError: string | null;
  onRequestSnapshot: () => void;
}) {
  const animatedScore = useCountUp(Math.round(report.score), 1700);
  const tier = report.tier as "cold" | "warm" | "hot" | string;
  const tierLabel: Record<string, string> = {
    cold: "Foundation needed",
    warm: "Mid-tier — sharpen the signals",
    hot: "Well-positioned — keep it sharp",
  };
  const tierTone: Record<string, string> = {
    cold: "bg-sky-300/10 text-sky-200 border-sky-300/30",
    warm: "bg-emerald-200/10 text-emerald-200 border-emerald-200/30",
    hot: "bg-emerald-200/15 text-emerald-100 border-emerald-200/40",
  };

  return (
    <section
      data-page="ai-buyer-trust-test-result"
      data-report-id={report.report_id}
      className="space-y-8"
    >
      <FrostedCard glow="mint">
        <div className="flex flex-col items-center text-center">
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-emerald-200/80">
            Your AI Buyer Trust Score
          </p>
          <div className="mt-6 flex items-end gap-3">
            <span
              className={
                "tabular-nums leading-none text-stone-50 " +
                headlineFontClass +
                " text-7xl sm:text-8xl"
              }
              aria-live="polite"
              aria-label={`Score ${Math.round(report.score)} out of 100`}
            >
              {Math.round(animatedScore)}
            </span>
            <span className="pb-3 font-mono text-sm text-stone-400">/ 100</span>
          </div>
          <p
            className={
              "mt-6 inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs uppercase tracking-wider " +
              (tierTone[tier] ?? tierTone.warm)
            }
          >
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-current" />
            {tier} · {tierLabel[tier] ?? "Result"}
          </p>
          <p className="mt-4 max-w-xl text-sm text-stone-300">
            {report.quick_win}
          </p>
        </div>
      </FrostedCard>

      <FrostedCard glow="sky">
        <CardHeading>Top gaps</CardHeading>
        {report.gaps.length === 0 ? (
          <p className="mt-3 text-sm text-stone-300">
            No major gaps surfaced from your answers. Keep the foundations in
            good standing — schema, FAQ, and proof assets drift over time.
          </p>
        ) : (
          <ul className="mt-4 space-y-3">
            {report.gaps.map((g) => (
              <li
                key={g.key}
                className="flex items-start gap-3 rounded-lg border border-white/5 bg-white/[0.02] p-3 sm:p-4"
              >
                <SeverityDot severity={g.severity} />
                <div>
                  <p className="text-sm text-stone-100">{g.label}</p>
                  <p className="mt-1 font-mono text-[11px] uppercase tracking-wider text-stone-400">
                    {g.severity} priority · weight {Math.round(g.weight)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </FrostedCard>

      <FrostedCard glow="mint">
        <CardHeading>Recommended next step</CardHeading>
        <p className="mt-2 text-sm text-stone-300">
          Based on your answers, the strongest next step in the ProofHook
          catalog is:
        </p>
        <a
          href={report.recommended_package_path}
          data-cta="ai-buyer-trust-test-recommend"
          data-package={report.recommended_package_slug}
          className="mt-4 inline-flex items-center gap-2 rounded-lg border border-emerald-200/30 bg-emerald-200/10 px-4 py-3 font-mono text-sm text-emerald-100 transition-colors hover:bg-emerald-200/20"
        >
          {report.recommended_package_slug.replace(/_/g, " ")} →
        </a>
        <p className="mt-3 text-xs text-stone-400">
          Recommendation reflects your answers only.
        </p>
      </FrostedCard>

      <FrostedCard glow="sky">
        <CardHeading>Get the Authority Snapshot review</CardHeading>
        {snapshotRequested ? (
          <p
            role="status"
            className="mt-3 rounded-lg border border-emerald-200/30 bg-emerald-200/10 p-4 text-sm text-emerald-100"
          >
            Snapshot Review requested. ProofHook will review your score and
            recommend the strongest next step.
          </p>
        ) : (
          <>
            <p className="mt-2 text-sm text-stone-300">
              ProofHook will review your score and recommend the strongest next
              step. We will reach out at the email you submitted with the
              recommendation.
            </p>
            <button
              type="button"
              onClick={onRequestSnapshot}
              disabled={snapshotting}
              className={
                "mt-4 inline-flex items-center gap-2 rounded-md px-5 py-2.5 text-sm font-semibold tracking-wide transition-all " +
                (snapshotting
                  ? "cursor-wait bg-white/10 text-stone-400"
                  : "bg-emerald-200 text-zinc-950 shadow-[0_0_30px_-6px_rgba(167,243,208,0.55)] hover:bg-emerald-100")
              }
            >
              {snapshotting ? "Requesting…" : "Request Snapshot Review"}
            </button>
            {snapshotError && (
              <p
                role="alert"
                className="mt-3 rounded-lg border border-red-400/30 bg-red-500/10 p-3 text-xs text-red-200"
              >
                {snapshotError}
              </p>
            )}
          </>
        )}
      </FrostedCard>
    </section>
  );
}


// ─────────────────────────────────────────────────────────────────────
// Card / form primitives — scoped to this page only
// ─────────────────────────────────────────────────────────────────────

function FrostedCard({
  children,
  glow,
}: {
  children: React.ReactNode;
  glow: "mint" | "sky";
}) {
  const glowClass =
    glow === "mint"
      ? "shadow-[0_30px_120px_-40px_rgba(167,243,208,0.35),inset_0_1px_0_0_rgba(255,255,255,0.04)]"
      : "shadow-[0_30px_120px_-40px_rgba(125,211,252,0.30),inset_0_1px_0_0_rgba(255,255,255,0.04)]";
  return (
    <div
      className={
        "relative rounded-2xl border border-white/10 bg-white/[0.035] p-6 backdrop-blur-xl sm:p-8 " +
        glowClass
      }
    >
      {children}
    </div>
  );
}

function CardHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-lg font-semibold tracking-tight text-stone-50">
      {children}
    </h2>
  );
}

function Field({
  label,
  name,
  value,
  onChange,
  type = "text",
  required,
  autoComplete,
  placeholder,
}: {
  label: string;
  name: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  required?: boolean;
  autoComplete?: string;
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="block text-xs uppercase tracking-wider text-stone-300">
        {label}
      </span>
      <input
        name={name}
        type={type}
        required={required}
        autoComplete={autoComplete}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-2 block w-full rounded-md border border-white/10 bg-white/5 px-3 py-2.5 text-sm text-stone-100 placeholder:text-stone-500 focus:border-emerald-200/40 focus:outline-none focus:ring-2 focus:ring-emerald-200/30"
      />
    </label>
  );
}

function SelectField({
  label,
  name,
  value,
  onChange,
  options,
}: {
  label: string;
  name: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="block">
      <span className="block text-xs uppercase tracking-wider text-stone-300">
        {label}
      </span>
      <select
        name={name}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-2 block w-full rounded-md border border-white/10 bg-white/5 px-3 py-2.5 text-sm text-stone-100 focus:border-sky-300/40 focus:outline-none focus:ring-2 focus:ring-sky-300/30"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value} className="bg-zinc-900">
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function AnswerRow({
  name,
  value,
  onChange,
}: {
  name: string;
  value: Answer | undefined;
  onChange: (v: Answer) => void;
}) {
  const choices: { value: Answer; label: string; tone: "mint" | "sky" | "neutral" }[] = [
    { value: "yes", label: "Yes", tone: "mint" },
    { value: "no", label: "No", tone: "sky" },
    { value: "unknown", label: "Not sure", tone: "neutral" },
  ];
  return (
    <div className="mt-3 grid grid-cols-3 gap-2">
      {choices.map((c) => {
        const selected = value === c.value;
        const base =
          "flex min-h-[44px] items-center justify-center rounded-md border px-3 py-2 text-sm font-medium tracking-wide transition-all";
        const tones = {
          mint: selected
            ? "border-emerald-200/40 bg-emerald-200/15 text-emerald-100 shadow-[0_0_24px_-8px_rgba(167,243,208,0.5)]"
            : "border-white/10 bg-white/5 text-stone-200 hover:border-emerald-200/20 hover:bg-emerald-200/5",
          sky: selected
            ? "border-sky-300/40 bg-sky-300/15 text-sky-100 shadow-[0_0_24px_-8px_rgba(125,211,252,0.5)]"
            : "border-white/10 bg-white/5 text-stone-200 hover:border-sky-300/20 hover:bg-sky-300/5",
          neutral: selected
            ? "border-white/30 bg-white/10 text-stone-100"
            : "border-white/10 bg-white/5 text-stone-300 hover:border-white/20 hover:bg-white/[0.07]",
        } as const;
        return (
          <button
            key={c.value}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(c.value)}
            data-question={name}
            data-answer={c.value}
            className={base + " " + tones[c.tone]}
          >
            {c.label}
          </button>
        );
      })}
    </div>
  );
}

function SeverityDot({ severity }: { severity: string }) {
  const tone =
    severity === "high"
      ? "bg-emerald-200 shadow-[0_0_14px_rgba(167,243,208,0.7)]"
      : severity === "medium"
      ? "bg-sky-300 shadow-[0_0_12px_rgba(125,211,252,0.55)]"
      : "bg-white/40";
  return (
    <span
      aria-hidden
      className={"mt-1.5 inline-block h-2 w-2 shrink-0 rounded-full " + tone}
    />
  );
}
