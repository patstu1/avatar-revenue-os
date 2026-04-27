/**
 * Public partial-result card for the AI Buyer Trust Test.
 *
 * Visual rules (locked by the design audit):
 *   - zinc-only palette — no electric blue, no amber, no navy
 *   - same card pattern as the existing ProofHook /about page:
 *     rounded-md border border-zinc-800 bg-zinc-900/40
 *   - same primary CTA styling as marketing-shell.CTA:
 *     border-zinc-100 bg-zinc-100 text-zinc-950 hover:bg-zinc-200
 *   - score state communicated via typography + border depth, NOT color hue
 *
 * Surfaces:
 *   - score number + label + confidence label
 *   - top 2 gaps via EvidenceList
 *   - quick win
 *   - 3 buyer-trust questions ("Questions your future customers may ask AI")
 *   - recommended package + rationale
 *   - platform hint copy (this is the first module of a larger platform)
 *   - disclaimer (no ranking guarantees, etc.)
 */

import Link from "next/link";

import type { TrustTestResult } from "@/lib/ai-buyer-trust-api";
import { PACKAGE_BY_SLUG, packagePriceDisplay } from "@/lib/proofhook-packages";

import { EvidenceList } from "./EvidenceList";

const SCORE_LABEL_DISPLAY: Record<TrustTestResult["score_label"], string> = {
  not_ready: "Not ready",
  weak: "Weak",
  developing: "Developing",
  strong: "Strong",
  authority_ready: "Authority-ready",
  not_assessed: "Not assessed",
};

const CONFIDENCE_LABEL_DISPLAY: Record<TrustTestResult["confidence_label"], string> = {
  low: "Low confidence",
  medium: "Medium confidence",
  high: "High confidence",
};

export function ScoreResultCard({
  result,
  onReset,
}: {
  result: TrustTestResult;
  onReset?: () => void;
}) {
  const labelText = SCORE_LABEL_DISPLAY[result.score_label] ?? "Not assessed";
  const confidenceText =
    CONFIDENCE_LABEL_DISPLAY[result.confidence_label] ?? "Low confidence";
  const primarySlug = result.recommended_package.primary_slug;
  const secondarySlug = result.recommended_package.secondary_slug;
  const creativeSlug = result.recommended_package.creative_proof_slug;
  const primaryPkg = primarySlug ? PACKAGE_BY_SLUG[primarySlug] : undefined;
  const secondaryPkg = secondarySlug ? PACKAGE_BY_SLUG[secondarySlug] : undefined;
  const creativePkg = creativeSlug ? PACKAGE_BY_SLUG[creativeSlug] : undefined;

  return (
    <article
      data-testid="trust-test-result"
      data-score-label={result.score_label}
      className="rounded-md border border-zinc-800 bg-zinc-900/40 p-6 sm:p-8"
    >
      <p className="font-mono text-xs uppercase tracking-wider text-zinc-500">
        Your AI Buyer Trust Score
      </p>
      <div className="mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-2">
        <span className="text-5xl font-semibold tracking-tight text-zinc-100">
          {result.total_score}
        </span>
        <span className="font-mono text-sm text-zinc-500">/ 100</span>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm">
        <span className="font-medium text-zinc-200">{labelText}</span>
        <span className="text-zinc-600" aria-hidden>·</span>
        <span className="text-zinc-400">{confidenceText}</span>
        <span className="text-zinc-600" aria-hidden>·</span>
        <span className="text-zinc-400">
          {result.submitted.website_url}
        </span>
      </div>

      {/* ── Top gaps ─────────────────────────────────────── */}
      <section className="mt-8">
        <h3 className="text-lg font-semibold tracking-tight text-zinc-100">
          Top gaps
        </h3>
        <EvidenceList gaps={result.top_gaps} />
      </section>

      {/* ── Quick win ────────────────────────────────────── */}
      {result.quick_win ? (
        <section className="mt-8">
          <h3 className="text-lg font-semibold tracking-tight text-zinc-100">
            Quick win
          </h3>
          <p className="mt-3 text-zinc-300 leading-relaxed">{result.quick_win}</p>
        </section>
      ) : null}

      {/* ── Buyer questions (the AI Decision Layer surface) ────────── */}
      {result.buyer_questions_preview &&
      result.buyer_questions_preview.length > 0 ? (
        <section className="mt-8">
          <h3 className="text-lg font-semibold tracking-tight text-zinc-100">
            Questions your future customers may ask AI
          </h3>
          <p className="mt-2 text-sm text-zinc-400 leading-relaxed">
            AI assistants answer trust and comparison questions before a buyer
            ever visits your site. These are the ones your business should be
            ready to answer publicly.
          </p>
          <ul className="mt-4 space-y-3">
            {result.buyer_questions_preview.map((q) => (
              <li
                key={q.question}
                className="rounded-md border border-zinc-800 bg-zinc-950 p-4"
              >
                <p className="font-medium text-zinc-100">{q.question}</p>
                <p className="mt-1 text-sm text-zinc-400 leading-relaxed">
                  {q.rationale}
                </p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {/* ── Recommended next step ────────────────────────────────── */}
      <section className="mt-8" data-testid="recommended-next-step">
        <h3 className="text-lg font-semibold tracking-tight text-zinc-100">
          Recommended next step
        </h3>
        <p className="mt-2 text-sm text-zinc-400 leading-relaxed">
          Your score maps to a buildable package on the ProofHook ladder. The
          Snapshot Review confirms this recommendation in writing before any
          proposal goes out.
        </p>
        {primaryPkg ? (
          <div className="mt-4 grid gap-3">
            <article
              data-testid="recommended-primary-pkg"
              data-package-slug={primaryPkg.slug}
              className="rounded-md border border-zinc-700 bg-zinc-950/50 p-4"
            >
              <p className="font-mono text-[11px] uppercase tracking-wider text-zinc-500">
                AI Authority lane · {packagePriceDisplay(primaryPkg)} · {primaryPkg.timeline}
              </p>
              <p className="mt-1.5 text-zinc-100 font-medium">
                {primaryPkg.name}
              </p>
              <p className="mt-1.5 text-sm text-zinc-300 leading-relaxed">
                {primaryPkg.tagline}
              </p>
              <p className="mt-2 text-xs text-zinc-500 leading-relaxed">
                <span className="text-zinc-400">Who it&rsquo;s for:</span>{" "}
                {primaryPkg.whoItsFor}
              </p>
            </article>
            {secondaryPkg ? (
              <article
                data-testid="recommended-secondary-pkg"
                data-package-slug={secondaryPkg.slug}
                className="rounded-md border border-zinc-800 bg-zinc-950/50 p-4"
              >
                <p className="font-mono text-[11px] uppercase tracking-wider text-zinc-500">
                  Pairs with · {packagePriceDisplay(secondaryPkg)} · {secondaryPkg.timeline}
                </p>
                <p className="mt-1.5 text-zinc-100 font-medium">
                  {secondaryPkg.name}
                </p>
                <p className="mt-1.5 text-sm text-zinc-300 leading-relaxed">
                  {secondaryPkg.tagline}
                </p>
              </article>
            ) : null}
            {creativePkg ? (
              <article
                data-testid="recommended-creative-pkg"
                data-package-slug={creativePkg.slug}
                className="rounded-md border border-zinc-800 bg-zinc-950/50 p-4"
              >
                <p className="font-mono text-[11px] uppercase tracking-wider text-zinc-500">
                  Creative Proof companion · {packagePriceDisplay(creativePkg)} · {creativePkg.timeline}
                </p>
                <p className="mt-1.5 text-zinc-100 font-medium">
                  {creativePkg.name}
                </p>
                <p className="mt-1.5 text-sm text-zinc-300 leading-relaxed">
                  {creativePkg.tagline}
                </p>
                <p className="mt-2 text-xs text-zinc-500 leading-relaxed">
                  <span className="text-zinc-400">Who it&rsquo;s for:</span>{" "}
                  {creativePkg.whoItsFor}
                </p>
              </article>
            ) : null}
            <p className="text-sm text-zinc-400 leading-relaxed">
              {result.recommended_package.rationale}
            </p>
          </div>
        ) : (
          <p className="mt-3 text-sm text-zinc-400">
            We couldn&apos;t recommend a package automatically. Re-run the test
            once your homepage is reachable.
          </p>
        )}

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Link
            href={result.cta.href}
            data-cta="trust-test-snapshot"
            className="inline-block rounded-md border border-zinc-100 bg-zinc-100 px-5 py-2.5 text-sm font-medium text-zinc-950 hover:bg-zinc-200"
          >
            {result.cta.label}
          </Link>
          <a
            href={`mailto:hello@proofhook.com?subject=${encodeURIComponent(
              `ProofHook — talk about ${primaryPkg?.name ?? "next step"}`,
            )}`}
            data-cta="trust-test-talk"
            className="inline-block rounded-md border border-zinc-700 px-5 py-2.5 text-sm font-medium text-zinc-200 hover:bg-zinc-900"
          >
            Talk to ProofHook
          </a>
          {onReset ? (
            <button
              type="button"
              onClick={onReset}
              className="text-sm text-zinc-400 hover:text-zinc-200"
            >
              Test another business
            </button>
          ) : null}
        </div>
      </section>

      {/* ── Platform hint — this is the first module ─────────────────── */}
      <section className="mt-8 border-t border-zinc-800 pt-6">
        <p className="font-mono text-xs uppercase tracking-wider text-zinc-500">
          About this report
        </p>
        <ul className="mt-3 space-y-2 text-sm text-zinc-400 leading-relaxed">
          <li>{result.platform_hint.first_snapshot}</li>
          <li>{result.platform_hint.history}</li>
          <li>{result.platform_hint.graph}</li>
          <li>{result.platform_hint.monitoring}</li>
        </ul>
      </section>

      <p className="mt-6 text-xs text-zinc-500 leading-relaxed">
        {result.disclaimer}
      </p>
    </article>
  );
}
