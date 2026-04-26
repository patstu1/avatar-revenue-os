/**
 * JSON-LD structured-data helpers for the ProofHook public marketing
 * surface. Each helper returns a ready-to-render <script type="application/ld+json">
 * tag. Used on every public marketing page so search engines and AI search
 * systems (Google, ChatGPT Search, Bing Copilot, Perplexity) can build a
 * cleaner entity graph for ProofHook.
 *
 * Copy rules: never claim guaranteed rankings or guaranteed AI placement.
 */

import { ORG, PACKAGES, SITE_URL, type ProofHookPackage } from "@/lib/proofhook-packages";

type JsonLdValue =
  | string
  | number
  | boolean
  | null
  | JsonLdValue[]
  | { [key: string]: JsonLdValue };

function ldScript(data: JsonLdValue) {
  // Render a deterministic JSON string. Using JSON.stringify with a stable
  // key order would require sorting; we instead trust callers to pass keys
  // in the order they want emitted.
  return (
    <script
      type="application/ld+json"
      // eslint-disable-next-line react/no-danger
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}

// ── Organization ────────────────────────────────────────────────────────

export function OrganizationJsonLd() {
  return ldScript({
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": `${SITE_URL}/#organization`,
    name: ORG.name,
    legalName: ORG.legalName,
    url: ORG.url,
    logo: ORG.logo,
    description: ORG.description,
    email: ORG.contactEmail,
    sameAs: ORG.sameAs,
  });
}

// ── WebSite ─────────────────────────────────────────────────────────────

export function WebSiteJsonLd() {
  return ldScript({
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": `${SITE_URL}/#website`,
    name: ORG.name,
    url: SITE_URL,
    publisher: { "@id": `${SITE_URL}/#organization` },
    description: ORG.description,
    inLanguage: "en-US",
  });
}

// ── Service ─────────────────────────────────────────────────────────────

export function ServiceJsonLd({
  pkg,
  pageUrl,
}: {
  pkg: ProofHookPackage;
  pageUrl: string;
}) {
  return ldScript({
    "@context": "https://schema.org",
    "@type": "Service",
    "@id": `${SITE_URL}${pageUrl}#service`,
    name: pkg.name,
    description: pkg.positioning,
    provider: { "@id": `${SITE_URL}/#organization` },
    serviceType: pkg.tagline,
    url: `${SITE_URL}${pageUrl}`,
    offers: {
      "@type": "Offer",
      "@id": `${SITE_URL}${pageUrl}#offer`,
      price: pkg.price,
      priceCurrency: "USD",
      url: `${SITE_URL}${pageUrl}`,
      availability: "https://schema.org/InStock",
      seller: { "@id": `${SITE_URL}/#organization` },
    },
  });
}

// ── Product / Offer for the full package catalog ────────────────────────

export function PackageCatalogOffersJsonLd() {
  return ldScript({
    "@context": "https://schema.org",
    "@graph": PACKAGES.map((p) => ({
      "@type": "Product",
      "@id": `${SITE_URL}${p.url}#product`,
      name: p.name,
      description: p.positioning,
      brand: { "@id": `${SITE_URL}/#organization` },
      offers: {
        "@type": "Offer",
        "@id": `${SITE_URL}${p.url}#offer`,
        price: p.price,
        priceCurrency: "USD",
        url: `${SITE_URL}${p.url}`,
        availability: "https://schema.org/InStock",
      },
    })),
  });
}

// ── FAQPage ─────────────────────────────────────────────────────────────

export type FaqQA = { question: string; answer: string };

export function FaqJsonLd({ qa }: { qa: FaqQA[] }) {
  return ldScript({
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: qa.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.answer,
      },
    })),
  });
}

// ── BreadcrumbList ──────────────────────────────────────────────────────

export type Crumb = { label: string; url: string };

export function BreadcrumbJsonLd({ items }: { items: Crumb[] }) {
  return ldScript({
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, idx) => ({
      "@type": "ListItem",
      position: idx + 1,
      name: item.label,
      item: `${SITE_URL}${item.url}`,
    })),
  });
}
