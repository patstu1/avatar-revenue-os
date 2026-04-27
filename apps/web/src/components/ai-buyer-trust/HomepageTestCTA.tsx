/**
 * Compact AI Buyer Trust Test CTA card for the unified ProofHook homepage.
 *
 * The full interactive test lives at /ai-search-authority/score (the
 * direct ad landing) and inside the deep dive at /ai-search-authority.
 * The homepage hosts this CTA card so the test stays prominent without
 * pushing the existing creative-lane content below the fold.
 *
 * Visual rules (locked):
 *   - zinc-only palette (zinc-100/200/300/400/500/700/800/900/950)
 *   - same card pattern as the other ProofHook surfaces (rounded-md
 *     border border-zinc-800 bg-zinc-900/40)
 *   - primary CTA matches marketing-shell.CTA exactly
 */

import Link from "next/link";

export function HomepageTestCTA() {
  return (
    <article
      data-testid="homepage-test-cta"
      className="rounded-md border border-zinc-800 bg-zinc-900/40 p-6 sm:p-8"
    >
      <p className="font-mono text-xs uppercase tracking-wider text-zinc-500">
        AI Buyer Trust Test
      </p>
      <h3 className="mt-2 text-xl font-semibold tracking-tight text-zinc-100">
        Check your AI Buyer Trust Score
      </h3>
      <p className="mt-3 text-sm text-zinc-300 leading-relaxed">
        Take the free ProofHook test. We scan public website signals like
        offers, proof, FAQs, schema, comparisons, crawlability, and trust
        structure. You get an instant ProofHook Authority Score, top trust
        gaps, buyer questions, a quick win, and a recommended next step.
      </p>
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Link
          href="/ai-search-authority/score"
          data-cta="homepage-test-card"
          className="inline-block rounded-md border border-zinc-100 bg-zinc-100 px-5 py-2.5 text-sm font-medium text-zinc-950 hover:bg-zinc-200"
        >
          Take the AI Buyer Trust Test
        </Link>
        <Link
          href="/ai-search-authority"
          data-cta="homepage-ai-authority-packages"
          className="text-sm text-zinc-300 hover:text-zinc-100"
        >
          View AI Authority Packages →
        </Link>
      </div>
      <p className="mt-4 text-xs text-zinc-500 leading-relaxed">
        Free for early-adopter founding clients while we build out the
        platform. Based on public website signals only.
      </p>
    </article>
  );
}
