'use client';

/**
 * HeroStage
 *
 * The main ProofHook arrival surface that becomes active after the intro
 * dissolves. Dark premium canvas with slow ambient motion (the "hero
 * videos" layer — a volumetric gradient field that reads as moving
 * footage without blocking the message).
 *
 * Props:
 *   active  — when true, the stage fades/slides in. Parent flips this
 *             from the intro component's onComplete.
 */

import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

type Props = {
  active: boolean;
};

const PACKAGES = [
  {
    slug: 'ai-ugc-starter',
    label: 'AI UGC Starter',
    tagline: 'Short-form proof content at scale.',
  },
  {
    slug: 'beauty-content-pack',
    label: 'Content Pack',
    tagline: 'Ten custom pieces per cycle.',
  },
  {
    slug: 'full-creative-retainer',
    label: 'Creative Retainer',
    tagline: 'Full-stack monthly engine.',
  },
] as const;

export default function HeroStage({ active }: Props) {
  return (
    <section
      className={`hero-stage${active ? ' is-active' : ''}`}
      aria-hidden={!active}
    >
      {/* Ambient motion layer — the premium "hero video" surface. */}
      <div className="hero-stage__canvas" aria-hidden="true">
        <div className="hero-stage__orb hero-stage__orb--a" />
        <div className="hero-stage__orb hero-stage__orb--b" />
        <div className="hero-stage__orb hero-stage__orb--c" />
        <div className="hero-stage__grid" />
        <div className="hero-stage__vignette" />
      </div>

      {/* Foreground content. */}
      <div className="hero-stage__content">
        <div className="hero-stage__mark">
          <span className="hero-stage__mark-dot" />
          ProofHook
        </div>

        <h1 className="hero-stage__headline">
          Turn what you know
          <br />
          into what you&rsquo;re known for.
        </h1>

        <p className="hero-stage__sub">
          A premium content engine for operators who want proof, not promises.
          Pick a package. We deliver the work. You keep the authority.
        </p>

        <div className="hero-stage__ctas">
          <Link
            href="/offers/aesthetic-theory/ai-ugc-starter"
            className="hero-stage__cta hero-stage__cta--primary"
          >
            See the packages
            <ArrowRight size={16} />
          </Link>
          <Link href="/login" className="hero-stage__cta hero-stage__cta--ghost">
            Sign in
          </Link>
        </div>

        <div className="hero-stage__packages" role="list">
          {PACKAGES.map((p) => (
            <Link
              key={p.slug}
              href={`/offers/aesthetic-theory/${p.slug}`}
              className="hero-stage__package"
              role="listitem"
            >
              <span className="hero-stage__package-label">{p.label}</span>
              <span className="hero-stage__package-tagline">{p.tagline}</span>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
