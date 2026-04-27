"use client";

/**
 * Full Authority Snapshot landing page.
 *
 * Two states driven by the ?report_id= query param:
 *
 *   - report_id present  → personalized "Your AI Buyer Trust result is
 *     ready for review." + Request Snapshot Review POSTs to the API.
 *   - report_id absent   → generic explainer + Request Snapshot Review
 *     routes back to /ai-search-authority/score.
 *
 * Visual rules (locked by the audit):
 *   - zinc-only palette (zinc-100/200/300/400/500/700/800/900/950)
 *   - same MarketingShell + card pattern as the rest of the site
 *   - affirmative positioning only — no "we do not" copy
 *   - no Stripe checkout in this patch; CTA is a review request, not a
 *     purchase
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import {
  CTA,
  MarketingShell,
  SectionHeading,
} from "@/components/marketing-shell";
import {
  OrganizationJsonLd,
  WebSiteJsonLd,
} from "@/components/jsonld";
import {
  TrustTestError,
  requestSnapshotReview,
} from "@/lib/ai-buyer-trust-api";
import {
  PACKAGE_BY_SLUG,
  SITE_URL,
  packagePriceDisplay,
} from "@/lib/proofhook-packages";

const PAGE_URL = "/ai-search-authority/snapshot";

export default function SnapshotPage() {
  return (
    <Suspense fallback={null}>
      <SnapshotPageInner />
    </Suspense>
  );
}

function SnapshotPageInner() {
  const params = useSearchParams();
  const reportId = params?.get("report_id") ?? null;

  return (
    <MarketingShell
      pageId="ai-search-authority-snapshot"
      breadcrumbs={[
        { label: "Home", url: "/" },
        { label: "AI Buyer Trust", url: "/ai-search-authority" },
        { label: "Full Authority Snapshot", url: PAGE_URL },
      ]}
    >
      <OrganizationJsonLd />
      <WebSiteJsonLd />

      <header>
        <p className="font-mono text-xs uppercase tracking-wider text-zinc-500">
          Full Authority Snapshot
        </p>
        <h1 className="mt-3 text-3xl font-semibold leading-tight tracking-tight text-zinc-100 sm:text-4xl">
          {reportId
            ? "Your AI Buyer Trust result is ready for review."
            : "The Full Authority Snapshot."}
        </h1>
        <p className="mt-5 max-w-2xl text-lg text-zinc-200 leading-relaxed">
          A reviewed, operator-led version of your AI Buyer Trust Score.
          The Snapshot maps how clearly AI-assisted buyers can understand
          and trust your business — and what to fix first.
        </p>
        <p className="mt-4 max-w-2xl text-zinc-300 leading-relaxed">
          The launch version is free with email for early-adopter founding
          clients while we build out the platform.
        </p>
      </header>

      <SectionHeading>What the Snapshot includes</SectionHeading>
      <ul className="mt-4 space-y-2 text-zinc-300">
        {[
          "Reviewed Authority Snapshot (PDF)",
          "Per-dimension evidence: detected, missing, why it matters, recommended fix",
          "5–10 buyer questions you should be prepared to answer publicly",
          "Recommended pages, schema, and proof assets",
          "Recommended package + scoping note across both lanes",
        ].map((item) => (
          <li key={item} className="flex gap-2.5 leading-relaxed">
            <span
              aria-hidden
              className="mt-1 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-zinc-500"
            />
            <span>{item}</span>
          </li>
        ))}
      </ul>

      <SectionHeading>How the Snapshot fits the AI decision layer</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        The Snapshot is the deeper read than the public AI Buyer Trust
        Test — sized for businesses that want operator-reviewed evidence
        before scoping a Sprint or Buildout. Every recommendation maps
        directly to the public proof, offers, FAQs, comparisons, schema,
        hooks, and trust signals AI assistants read.
      </p>

      <SectionHeading>How the request flow works</SectionHeading>
      <ol
        className="mt-4 max-w-3xl space-y-3"
        data-testid="snapshot-request-flow"
      >
        {[
          {
            step: "01",
            title: "Take the AI Buyer Trust Test",
            body: "Submit your website. ProofHook scans the public signals and returns your Authority Score in seconds, plus a recommended package.",
          },
          {
            step: "02",
            title: "Request your Snapshot Review",
            body: "From your test result (or this page when your report_id is in the URL), click Request Snapshot Review. The request is queued for an operator.",
          },
          {
            step: "03",
            title: "Operator review",
            body: "A ProofHook operator reviews your scan, the per-dimension evidence, and the recommended package, and prepares your written Snapshot.",
          },
          {
            step: "04",
            title: "Snapshot delivery + recommended package",
            body: "You receive the Full Authority Snapshot at the email on file, with a recommended ProofHook package and a written proposal you can review and accept.",
          },
        ].map((s) => (
          <li
            key={s.step}
            className="flex items-start gap-4 rounded-md border border-zinc-800 bg-zinc-900/40 p-4"
          >
            <span className="font-mono text-xs uppercase tracking-wider text-zinc-500 pt-0.5">
              {s.step}
            </span>
            <div>
              <p className="text-zinc-100 font-medium">{s.title}</p>
              <p className="mt-1 text-sm text-zinc-300 leading-relaxed">
                {s.body}
              </p>
            </div>
          </li>
        ))}
      </ol>

      <SectionHeading>Where the Snapshot leads next</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        Every Snapshot includes a recommended package on the AI Authority
        ladder — chosen by the operator based on your score, evidence, and
        gaps.
      </p>
      <ul
        className="mt-5 grid gap-4 sm:grid-cols-2"
        data-testid="snapshot-package-ladder"
      >
        {[
          "ai_search_authority_sprint",
          "proof_infrastructure_buildout",
          "authority_monitoring_retainer",
          "ai_search_authority_system",
        ].map((slug) => {
          const pkg = PACKAGE_BY_SLUG[slug];
          if (!pkg) return null;
          return (
            <li
              key={pkg.slug}
              className="rounded-md border border-zinc-800 bg-zinc-900/40 p-4"
            >
              <p className="font-mono text-[11px] uppercase tracking-wider text-zinc-500">
                {packagePriceDisplay(pkg)} · {pkg.timeline}
              </p>
              <p className="mt-1 text-zinc-100 font-medium">{pkg.name}</p>
              <p className="mt-1.5 text-xs text-zinc-300 leading-relaxed">
                {pkg.tagline}
              </p>
            </li>
          );
        })}
      </ul>

      <div className="mt-10">
        <SnapshotActions reportId={reportId} />
      </div>

      <p className="mt-12 text-xs text-zinc-500 leading-relaxed">
        Built to improve the clarity, structure, and machine-readability
        of your public business signals. Based on public website signals:
        offers, proof, FAQs, schema, comparisons, crawlability, and trust
        structure.
      </p>
    </MarketingShell>
  );
}

function SnapshotActions({ reportId }: { reportId: string | null }) {
  const [requesting, setRequesting] = useState(false);
  const [requested, setRequested] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onRequestReview = async () => {
    if (!reportId || requesting || requested) return;
    setRequesting(true);
    setError(null);
    try {
      await requestSnapshotReview(reportId);
      setRequested(true);
    } catch (err) {
      if (err instanceof TrustTestError) {
        setError(err.message);
      } else {
        setError(
          "Something went wrong submitting the request. Email hello@proofhook.com.",
        );
      }
    } finally {
      setRequesting(false);
    }
  };

  return (
    <article
      data-testid="snapshot-actions"
      className="rounded-md border border-zinc-800 bg-zinc-900/40 p-6 sm:p-8"
    >
      {requested ? (
        <div data-testid="snapshot-requested">
          <p className="font-mono text-xs uppercase tracking-wider text-zinc-500">
            Request received
          </p>
          <h3 className="mt-2 text-lg font-semibold tracking-tight text-zinc-100">
            Your Snapshot is queued for operator review.
          </h3>
          <p className="mt-3 text-sm text-zinc-300 leading-relaxed">
            A ProofHook operator will review your AI Buyer Trust result
            and reach out at the email on file with your Full Authority
            Snapshot.
          </p>
        </div>
      ) : (
        <>
          <p className="font-mono text-xs uppercase tracking-wider text-zinc-500">
            Take the next step
          </p>
          <h3 className="mt-2 text-lg font-semibold tracking-tight text-zinc-100">
            {reportId
              ? "Request your operator-reviewed Snapshot."
              : "Run the test, then request your Snapshot."}
          </h3>
          <p className="mt-3 text-sm text-zinc-300 leading-relaxed">
            {reportId
              ? "We will review the gaps, buyer questions, and recommended package, then send the Full Authority Snapshot."
              : "Take the AI Buyer Trust Test first to generate your evidence-based result. Then request the Snapshot from the result page."}
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <Link
              href="/ai-search-authority/score"
              data-cta="snapshot-take-test"
              className="inline-block rounded-md border border-zinc-100 bg-zinc-100 px-5 py-2.5 text-sm font-medium text-zinc-950 hover:bg-zinc-200"
            >
              Take the AI Buyer Trust Test
            </Link>
            {reportId ? (
              <button
                type="button"
                onClick={onRequestReview}
                disabled={requesting}
                data-cta="snapshot-request-review"
                className="inline-block rounded-md border border-zinc-700 px-5 py-2.5 text-sm text-zinc-200 hover:bg-zinc-900 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {requesting ? "Submitting…" : "Request Snapshot Review"}
              </button>
            ) : (
              <Link
                href="/ai-search-authority/score"
                data-cta="snapshot-request-review-no-report"
                className="inline-block rounded-md border border-zinc-700 px-5 py-2.5 text-sm text-zinc-200 hover:bg-zinc-900"
              >
                Request Snapshot Review
              </Link>
            )}
          </div>
          {error ? (
            <p
              role="alert"
              className="mt-4 rounded-md border border-zinc-700 bg-zinc-950 p-3 text-sm text-zinc-300"
            >
              {error}
            </p>
          ) : null}
        </>
      )}

      <div className="mt-6 border-t border-zinc-800 pt-4">
        <CTA
          label="Talk to ProofHook"
          subject="ProofHook — Full Authority Snapshot"
          ctaId="snapshot-talk"
        />
      </div>
    </article>
  );
}

// Static metadata — Next.js does not allow `export const metadata` from a
// "use client" file, so the canonical/SEO bits are surfaced via the JSON-LD
// helpers above + the root layout's metadataBase. The page title is set
// here for completeness; Next falls back to the layout title otherwise.
if (typeof document !== "undefined") {
  document.title = "Full Authority Snapshot | ProofHook";
}

// Export for downstream tooling that resolves `SITE_URL`.
export { SITE_URL };
