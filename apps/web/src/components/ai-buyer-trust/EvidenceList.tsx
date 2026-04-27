/**
 * Per-dimension evidence renderer used in the public ScoreResultCard.
 *
 * Reuses the existing ProofHook visual language exactly:
 *   - dark zinc-only palette (zinc-100/200/300/400/500/700/800/900/950)
 *   - same card pattern as /about: rounded-md border border-zinc-800 bg-zinc-900/40
 *   - same Bullets dot-style as marketing-shell
 *   - mono eyebrow labels in zinc-500
 *   - no electric blue, no amber, no navy, no neon
 */

import type { TrustTestGap } from "@/lib/ai-buyer-trust-api";

export function EvidenceList({ gaps }: { gaps: TrustTestGap[] }) {
  if (gaps.length === 0) {
    return (
      <p className="text-sm text-zinc-400">
        No assessable gaps surfaced. Every measured dimension scored above
        the gap threshold.
      </p>
    );
  }

  return (
    <ul className="mt-4 space-y-4">
      {gaps.map((gap) => (
        <li
          key={gap.public_label}
          className="rounded-md border border-zinc-800 bg-zinc-900/40 p-5"
        >
          <div className="flex items-start justify-between gap-4">
            <p className="font-medium text-zinc-100">{gap.public_label}</p>
            <span className="font-mono text-xs text-zinc-500">
              {gap.score} / 100
            </span>
          </div>

          <dl className="mt-4 space-y-3 text-sm">
            <Block label="Detected" items={gap.detected} muted={false} />
            <Block label="Missing" items={gap.missing} muted />
            <Single label="Why it matters" value={gap.why_it_matters} />
            <Single label="Recommended fix" value={gap.recommended_fix} />
          </dl>
        </li>
      ))}
    </ul>
  );
}

function Block({
  label,
  items,
  muted,
}: {
  label: string;
  items: string[];
  muted: boolean;
}) {
  if (!items || items.length === 0) {
    return (
      <div>
        <dt className="font-mono text-[11px] uppercase tracking-wider text-zinc-500">
          {label}
        </dt>
        <dd className="mt-1 text-zinc-500">Not assessed</dd>
      </div>
    );
  }
  return (
    <div>
      <dt className="font-mono text-[11px] uppercase tracking-wider text-zinc-500">
        {label}
      </dt>
      <dd className="mt-1">
        <ul className="space-y-1.5">
          {items.map((item) => (
            <li key={item} className="flex gap-2 leading-relaxed">
              <span
                aria-hidden
                className="mt-1.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-zinc-500"
              />
              <span className={muted ? "text-zinc-400" : "text-zinc-300"}>
                {item}
              </span>
            </li>
          ))}
        </ul>
      </dd>
    </div>
  );
}

function Single({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-mono text-[11px] uppercase tracking-wider text-zinc-500">
        {label}
      </dt>
      <dd className="mt-1 text-zinc-300 leading-relaxed">{value}</dd>
    </div>
  );
}
