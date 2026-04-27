/**
 * Minimal layout shell for the public marketing pages. Header with the
 * ProofHook wordmark + nav links, optional breadcrumb, and a footer with
 * a contact email + the same nav for crawlers. Plain dark theme matching
 * the rest of the app — no redesign, no new component library.
 */

import Link from "next/link";

import { ORG } from "@/lib/proofhook-packages";
import { BreadcrumbJsonLd, type Crumb } from "@/components/jsonld";

const NAV_LINKS = [
  { href: "/ai-search-authority", label: "AI Search Authority" },
  { href: "/how-it-works", label: "How it works" },
  { href: "/faq", label: "FAQ" },
];

export function MarketingShell({
  breadcrumbs,
  pageId,
  children,
}: {
  breadcrumbs?: Crumb[];
  /** Analytics hook — emitted as data-page on the <main> root so a
   * future analytics layer can identify which marketing surface a
   * click happened on. Examples: "ai-search-authority", "faq",
   * "answers/what-is-proof-based-content", "industries/saas". */
  pageId?: string;
  children: React.ReactNode;
}) {
  return (
    <main
      data-page={pageId}
      className="min-h-screen bg-zinc-950 text-zinc-100 font-sans antialiased"
    >
      <header className="border-b border-zinc-800">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <Link href="/" className="font-mono text-sm tracking-wider text-zinc-100">
            ProofHook
          </Link>
          <nav className="flex items-center gap-5 text-sm text-zinc-400">
            {NAV_LINKS.map((l) => (
              <Link key={l.href} href={l.href} className="hover:text-zinc-100">
                {l.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      {breadcrumbs && breadcrumbs.length > 0 && (
        <>
          <BreadcrumbJsonLd items={breadcrumbs} />
          <nav
            aria-label="Breadcrumb"
            className="mx-auto max-w-5xl px-6 pt-6 text-xs text-zinc-500"
          >
            <ol className="flex flex-wrap gap-1.5">
              {breadcrumbs.map((c, i) => (
                <li key={c.url} className="flex items-center gap-1.5">
                  {i > 0 && <span aria-hidden>/</span>}
                  {i === breadcrumbs.length - 1 ? (
                    <span className="text-zinc-300">{c.label}</span>
                  ) : (
                    <Link href={c.url} className="hover:text-zinc-200">
                      {c.label}
                    </Link>
                  )}
                </li>
              ))}
            </ol>
          </nav>
        </>
      )}

      <div className="mx-auto max-w-5xl px-6 py-10">{children}</div>

      <footer className="mt-16 border-t border-zinc-800">
        <div className="mx-auto flex max-w-5xl flex-col gap-4 px-6 py-8 text-sm text-zinc-500 sm:flex-row sm:items-center sm:justify-between">
          <p className="font-mono">
            ProofHook ·{" "}
            <a href={`mailto:${ORG.contactEmail}`} className="hover:text-zinc-300">
              {ORG.contactEmail}
            </a>
          </p>
          <nav className="flex flex-wrap gap-4">
            {NAV_LINKS.map((l) => (
              <Link key={l.href} href={l.href} className="hover:text-zinc-300">
                {l.label}
              </Link>
            ))}
          </nav>
        </div>
      </footer>
    </main>
  );
}

export function CTA({
  email,
  label,
  subject,
  ctaId,
  packageSlug,
  className,
}: {
  email?: string;
  label: string;
  subject: string;
  /** Analytics hook — emitted as data-cta on the rendered element so a
   * future analytics layer (GA4 dataLayer, Posthog, server-side) can
   * read clicks without coupling to a specific provider. Common values:
   * "ai-search-authority", "contact", "answers", "package-buy". */
  ctaId?: string;
  /** Optional universal package slug for package-related CTAs. Renders
   * as data-package — analytics groups CTAs by universal slug, never by
   * niche. */
  packageSlug?: string;
  /** Optional className override for in-card / compact placements.
   * When omitted, renders the default primary-button styling. */
  className?: string;
}) {
  const to = email ?? ORG.contactEmail;
  return (
    <a
      href={`mailto:${to}?subject=${encodeURIComponent(subject)}`}
      data-cta={ctaId ?? "contact"}
      data-package={packageSlug}
      className={
        className ??
        "inline-block rounded-md border border-zinc-100 bg-zinc-100 px-5 py-2.5 text-sm font-medium text-zinc-950 hover:bg-zinc-200"
      }
    >
      {label}
    </a>
  );
}

export function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mt-12 text-lg font-semibold tracking-tight text-zinc-100">
      {children}
    </h2>
  );
}

export function Bullets({ items }: { items: string[] }) {
  return (
    <ul className="mt-4 space-y-2 text-zinc-300">
      {items.map((item) => (
        <li key={item} className="flex gap-2.5 leading-relaxed">
          <span aria-hidden className="mt-1 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-zinc-500" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}
