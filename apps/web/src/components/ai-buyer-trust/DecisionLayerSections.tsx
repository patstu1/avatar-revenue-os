/**
 * AI Decision Layer site sections — shared between the homepage and the
 * /ai-search-authority page so the campaign copy stays in one place.
 *
 * Visual rules (locked by the audit):
 *   - zinc-only palette (zinc-100/200/300/400/500/700/800/900/950)
 *   - same card pattern as the existing /about page
 *   - same SectionHeading + Bullets primitives from marketing-shell
 *   - no electric blue, no amber, no navy, no gradients, no neon
 *   - affirmative positioning only — no "we do not / we don't" copy
 */

import { Bullets, SectionHeading } from "@/components/marketing-shell";

export function ThirdShiftSection() {
  return (
    <>
      <SectionHeading>The third shift in search</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        There have been two major shifts in how businesses were discovered
        online.
      </p>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        The first was search. Businesses that understood Google early gained
        an advantage.
      </p>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        The second was mobile. Businesses that adapted to faster, mobile-first
        behavior captured attention and market share.
      </p>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        The third shift is happening now.
      </p>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        This shift is different because it changes who is doing the searching.
        Customers are starting to use AI systems to scan, compare, and
        organize options before they ever visit a website.
      </p>
    </>
  );
}

export function DecisionLayerSection() {
  return (
    <>
      <SectionHeading>AI is becoming the decision layer</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        AI systems scan differently than people. They extract information,
        compare options, and look for clear offers, proof, FAQs, schema,
        trust signals, and decision-ready content.
      </p>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        Your website is now also a source of structured signals for the
        systems helping buyers decide.
      </p>
      <p className="mt-4 max-w-2xl text-zinc-200 leading-relaxed">
        The question is no longer only,{" "}
        <span className="text-zinc-100">
          &ldquo;Can customers find you?&rdquo;
        </span>{" "}
        It is,{" "}
        <span className="text-zinc-100">
          &ldquo;Can AI understand you well enough to recommend you?&rdquo;
        </span>
      </p>
    </>
  );
}

export function WhatProofHookChecksSection() {
  return (
    <>
      <SectionHeading>What ProofHook checks</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        The AI Buyer Trust Test scans public website signals to show how
        clearly your business can be understood, compared, and trusted in
        the AI decision layer. It evaluates:
      </p>
      <Bullets
        items={[
          "What your business does",
          "Who you serve",
          "How clearly your offers are explained",
          "How your proof is structured",
          "Whether buyer questions are answered",
          "Whether comparison signals exist",
          "Whether schema and crawlability support machine readability",
          "Whether trust signals are easy to find",
        ]}
      />
    </>
  );
}

export function WhatTheScoreRevealsSection() {
  return (
    <>
      <SectionHeading>What the score reveals</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        Your ProofHook Authority Score shows where your public business
        signals are strong and where structure is missing. Each result
        includes:
      </p>
      <Bullets
        items={[
          "Total score",
          "Confidence level",
          "Top trust gaps",
          "Proof and comparison gaps",
          "Buyer questions your site should answer",
          "Quick wins",
          "Recommended next step",
        ]}
      />
    </>
  );
}

export function ScatteredToStructuredSection() {
  return (
    <>
      <SectionHeading>From scattered proof to structured authority</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        ProofHook turns scattered public signals into a clearer authority
        system:
      </p>
      <ol
        aria-label="Authority Graph"
        className="mt-4 max-w-2xl rounded-md border border-zinc-800 bg-zinc-900/40 p-5 font-mono text-sm leading-7 text-zinc-200"
      >
        <li>Company</li>
        <li>→ Category</li>
        <li>→ Offers</li>
        <li>→ Proof</li>
        <li>→ Buyer Questions</li>
        <li>→ FAQs</li>
        <li>→ Comparisons</li>
        <li>→ Schema</li>
        <li>→ Answer Pages</li>
        <li>→ CTAs</li>
      </ol>
      <p className="mt-4 max-w-2xl text-zinc-300 leading-relaxed">
        This gives buyers, search engines, and AI systems clearer inputs
        when they evaluate your business.
      </p>
    </>
  );
}

export function HowItWorksSection() {
  const steps = [
    {
      n: "01",
      title: "Take the AI Buyer Trust Test",
      body: "Submit your website. ProofHook scans the public signals AI systems and AI-assisted buyers actually read — entity, offers, proof, FAQs, comparisons, schema, trust signals.",
    },
    {
      n: "02",
      title: "Receive your Authority Score",
      body: "An instant scorecard with total score, top trust gaps, buyer questions you should be answering, a quick win, and a recommended next step.",
    },
    {
      n: "03",
      title: "Request a reviewed Authority Snapshot",
      body: "A ProofHook operator reviews your scan and delivers a written Authority Snapshot — the full per-dimension diagnostic with prioritized fixes and a recommended ProofHook package.",
    },
    {
      n: "04",
      title: "Build the authority + creative your buyers need",
      body: "Pick the package that fits the gap. Authority work publishes the structured surfaces. Creative work fills them with proof your buyers and AI assistants can both read.",
    },
  ];
  return (
    <>
      <SectionHeading>How ProofHook works</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        A short path from one free test to a buildable, sellable engagement.
      </p>
      <ol className="mt-6 grid gap-4 sm:grid-cols-2" data-testid="how-it-works-steps">
        {steps.map((s) => (
          <li
            key={s.n}
            className="rounded-md border border-zinc-800 bg-zinc-900/40 p-5"
          >
            <p className="font-mono text-xs uppercase tracking-wider text-zinc-500">
              Step {s.n}
            </p>
            <p className="mt-2 text-zinc-100 font-medium">{s.title}</p>
            <p className="mt-2 text-sm text-zinc-300 leading-relaxed">{s.body}</p>
          </li>
        ))}
      </ol>
    </>
  );
}

export function AfterTheTestSection() {
  const stages = [
    {
      title: "Authority Snapshot",
      body: "Reviewed by a ProofHook operator. Per-dimension evidence, prioritized fixes, recommended package.",
    },
    {
      title: "Recommended package",
      body: "The Authority Snapshot includes a primary package recommendation and (where it fits) a creative companion package.",
    },
    {
      title: "Proposal",
      body: "The operator turns the recommendation into a written proposal you can review, edit, and accept.",
    },
    {
      title: "Fulfillment",
      body: "ProofHook builds the surfaces, schema, proof pages, FAQ structure, comparisons, and creative your score said you need.",
    },
    {
      title: "Authority Monitoring",
      body: "Optional monthly retainer that keeps score, schema, FAQs, comparisons, and proof current as buyer questions change.",
    },
  ];
  return (
    <>
      <SectionHeading>What happens after the test</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        Every test result has a buildable next step. The path is the same for
        every buyer:
      </p>
      <ol
        className="mt-6 max-w-3xl space-y-3"
        data-testid="after-test-stages"
      >
        {stages.map((s, i) => (
          <li
            key={s.title}
            className="flex items-start gap-4 rounded-md border border-zinc-800 bg-zinc-900/40 p-4"
          >
            <span className="font-mono text-xs uppercase tracking-wider text-zinc-500 pt-0.5">
              {String(i + 1).padStart(2, "0")}
            </span>
            <div>
              <p className="text-zinc-100 font-medium">{s.title}</p>
              <p className="mt-1 text-sm text-zinc-300 leading-relaxed">{s.body}</p>
            </div>
          </li>
        ))}
      </ol>
    </>
  );
}

export function BuyerPsychologySection() {
  return (
    <>
      <SectionHeading>How buyers actually search now</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        Search used to start with a query and end with a list of links.
      </p>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        AI-assisted buyers start with a question and end with a shortlist. The
        AI assistant has already read the websites, extracted the offers,
        compared the proof, and decided which businesses are clear enough to
        recommend — before the buyer ever clicks.
      </p>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        That changes what your website is for. It is now also the source of
        structured signals the assistant reads on the buyer&rsquo;s behalf.
      </p>
      <p className="mt-4 max-w-2xl text-zinc-200 leading-relaxed">
        ProofHook builds the signals AI assistants can extract, the proof they
        can verify, and the comparisons they can quote — so your business is
        included in the shortlist instead of left out of it.
      </p>
    </>
  );
}

export function WhatProofHookBuildsSection() {
  const groups = [
    {
      heading: "Authority surfaces",
      items: [
        "Entity / About page",
        "Offer pages with clear pricing and outcomes",
        "FAQ architecture answering top buyer questions",
        "Comparison surfaces (vs. alternatives, best-of category, how-to-choose)",
        "Proof, case-study, and testimonial pages",
        "Answer-engine pages that match real buyer queries",
      ],
    },
    {
      heading: "Machine-readable structure",
      items: [
        "Organization / WebSite / Service / Product / Offer JSON-LD",
        "FAQPage + BreadcrumbList JSON-LD",
        "Review / AggregateRating where supported",
        "robots.txt + sitemap + canonical URL review",
        "Authority Graph (internal linking + breadcrumb schema)",
      ],
    },
    {
      heading: "Creative your buyers and AI assistants both read",
      items: [
        "Short-form proof video assets",
        "Hook variations per asset",
        "Founder-led launch clips",
        "Paid-media-ready creative + offer alignment",
        "Recurring creative production at upper-throughput cadence",
      ],
    },
  ];
  return (
    <>
      <SectionHeading>What ProofHook builds</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        Two connected lanes. AI Authority publishes the structured surfaces.
        Creative Proof fills them with the asset types AI-assisted buyers
        verify.
      </p>
      <div className="mt-6 grid gap-4 md:grid-cols-3" data-testid="what-proofhook-builds">
        {groups.map((g) => (
          <div
            key={g.heading}
            className="rounded-md border border-zinc-800 bg-zinc-900/40 p-5"
          >
            <p className="text-zinc-100 font-medium">{g.heading}</p>
            <ul className="mt-3 space-y-2 text-sm text-zinc-300 leading-relaxed">
              {g.items.map((item) => (
                <li key={item} className="flex gap-2">
                  <span className="text-zinc-500">·</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </>
  );
}

export function ResultToPackageSection() {
  const rows = [
    {
      score: "Below 40",
      reads: "Weak entity, thin offers, missing proof, no comparisons, low schema coverage.",
      build: "AI Search Authority Sprint + Proof Infrastructure Buildout. Optional creative companion: UGC Starter Pack.",
    },
    {
      score: "40 – 65",
      reads: "Some structure exists. Offer clarity, FAQ, or comparison surfaces are missing or thin.",
      build: "AI Search Authority Sprint. Optional creative companion: Proof Video Pack.",
    },
    {
      score: "65 – 85",
      reads: "Strong structure. Drift, missing comparisons, or new buyer questions are the risk.",
      build: "Authority Monitoring Retainer. Optional creative companion: Hook Pack or Paid Social Creative Pack.",
    },
    {
      score: "85 +",
      reads: "Authority surface is mature.",
      build: "Authority Monitoring Retainer to keep score, schema, and proof current as buyer questions and competitors change.",
    },
  ];
  return (
    <>
      <SectionHeading>Result to package</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        Every Authority Score maps to a buildable next step. This is the
        mapping ProofHook operators use to recommend a package.
      </p>
      <div
        className="mt-6 overflow-hidden rounded-md border border-zinc-800"
        data-testid="result-to-package-table"
      >
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-900/60 text-xs uppercase tracking-wider text-zinc-400">
            <tr>
              <th className="px-4 py-3 font-mono">Score band</th>
              <th className="px-4 py-3 font-mono">What the score reads</th>
              <th className="px-4 py-3 font-mono">Recommended build</th>
            </tr>
          </thead>
          <tbody className="bg-zinc-900/30">
            {rows.map((r) => (
              <tr key={r.score} className="border-t border-zinc-800 align-top">
                <td className="px-4 py-3 font-mono text-zinc-200">{r.score}</td>
                <td className="px-4 py-3 text-zinc-300 leading-relaxed">{r.reads}</td>
                <td className="px-4 py-3 text-zinc-200 leading-relaxed">{r.build}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export function CommercialFlowSection() {
  const stages = [
    "Take the test",
    "Receive Authority Score",
    "Request reviewed Snapshot",
    "Operator-recommended package",
    "Written proposal",
    "Build + fulfillment",
    "Authority monitoring",
  ];
  return (
    <>
      <SectionHeading>The full ProofHook engagement</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        From a single free test to a sellable, buildable engagement and an
        ongoing authority surface.
      </p>
      <ol
        aria-label="ProofHook commercial flow"
        className="mt-4 max-w-3xl rounded-md border border-zinc-800 bg-zinc-900/40 p-5 font-mono text-sm leading-7 text-zinc-200"
        data-testid="commercial-flow"
      >
        {stages.map((stage, i) => (
          <li key={stage}>
            {i === 0 ? "" : "→ "}
            {stage}
          </li>
        ))}
      </ol>
    </>
  );
}

/**
 * Video placeholder section — no asset shipped today; the script renders
 * as visible text below the placeholder so it doubles as the transcript
 * (and remains AI-readable regardless of whether a future video file is
 * mounted at apps/web/public/ai-buyer-trust-explainer.mp4).
 */
export function ExplainerVideoSection() {
  return (
    <>
      <SectionHeading>The buyer journey is changing before your website ever loads</SectionHeading>
      <div
        className="mt-4 rounded-md border border-zinc-800 bg-zinc-900/40 p-6 sm:p-8"
        data-testid="explainer-video-placeholder"
      >
        <div
          aria-label="ProofHook AI Decision Layer explainer — video placeholder"
          className="flex aspect-video items-center justify-center rounded-md border border-zinc-800 bg-zinc-950 text-center"
        >
          <div className="px-6">
            <p className="font-mono text-xs uppercase tracking-wider text-zinc-500">
              Explainer video
            </p>
            <p className="mt-3 text-zinc-200">
              Google helped customers find businesses.
              <br />
              AI is helping them decide who to trust.
            </p>
            <p className="mt-3 text-xs text-zinc-500">
              Coming soon. Transcript below.
            </p>
          </div>
        </div>

        <div className="mt-6 space-y-3 text-sm text-zinc-300 leading-relaxed">
          <p>Google helped customers find businesses.</p>
          <p>AI is helping them decide who to trust.</p>
          <p>A new era of search is here — and it is bigger than Google.</p>
          <p>
            Customers are no longer browsing websites the same way. They are
            beginning to ask AI systems who to compare, hire, and buy from
            before they ever reach a website.
          </p>
          <p>
            Those systems scan your public information, extract signals,
            compare options, and organize recommendations.
          </p>
          <p>That changes the role of your website.</p>
          <p>Your website is now also a source of structured signals for the decision layer.</p>
          <p>ProofHook helps you understand how clearly your business is positioned for this shift.</p>
          <p>
            The AI Buyer Trust Test scans public website signals like offers,
            proof, FAQs, schema, comparison readiness, crawlability, and trust
            structure.
          </p>
          <p>
            You get a ProofHook Authority Score, buyer questions, trust gaps,
            quick wins, and a recommended next step.
          </p>
          <p>Take the test. See how clearly your business can be understood, compared, and trusted.</p>
          <p className="text-zinc-200">Don&rsquo;t get left behind.</p>
        </div>
      </div>
    </>
  );
}
