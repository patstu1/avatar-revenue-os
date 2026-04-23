'use client';

/**
 * ArrivalIntro
 *
 * First-load cinematic greeting for the ProofHook website.
 * A premium, restrained 4-line text sequence on a dark stage.
 *
 * Timing (total ~4.8s):
 *   280ms  pre-hold
 *   900ms  "Hello."
 *   900ms  "Welcome to ProofHook."
 *   900ms  "Turn what you know into what you're known for."
 *   900ms  "Well, let me show you around."
 *   320ms  final hold
 *   620ms  dissolve to hero
 *
 * Persistence: sessionStorage key `proofhook_intro_seen_v1` — skipped on
 * internal navigation within the same tab session, replayed on new tab /
 * new session.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

const LINES = [
  'Hello.',
  'Welcome to ProofHook.',
  "Turn what you know into what you're known for.",
  'Well, let me show you around.',
] as const;

// Timing (ms).
const FIRST_DELAY = 280;
const LINE_INTERVAL = 900;
const FINAL_HOLD = 320;
const DISSOLVE_MS = 620;
// Total ≈ 280 + 4*900 + 320 + 620 = 4820ms

const STORAGE_KEY = 'proofhook_intro_seen_v1';

type Phase = 'pending' | 'running' | 'dissolving' | 'done';

type Props = {
  onComplete: () => void;
};

export default function ArrivalIntro({ onComplete }: Props) {
  const [phase, setPhase] = useState<Phase>('pending');
  const [currentLine, setCurrentLine] = useState<number>(-1);
  const timersRef = useRef<number[]>([]);
  const completedRef = useRef(false);
  const onCompleteRef = useRef(onComplete);

  // Keep latest onComplete without re-running the schedule effect.
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  const complete = useCallback(() => {
    if (completedRef.current) return;
    completedRef.current = true;
    try {
      sessionStorage.setItem(STORAGE_KEY, '1');
    } catch {
      /* private mode / storage unavailable — still complete */
    }
    setPhase('done');
    onCompleteRef.current();
  }, []);

  useEffect(() => {
    // SSR-safe guard.
    if (typeof window === 'undefined') return;

    // Skip if this tab session has already seen the intro.
    let alreadySeen = false;
    try {
      alreadySeen = sessionStorage.getItem(STORAGE_KEY) === '1';
    } catch {
      /* ignore */
    }
    if (alreadySeen) {
      complete();
      return;
    }

    setPhase('running');

    // Schedule each line reveal.
    for (let i = 0; i < LINES.length; i++) {
      const t = window.setTimeout(() => {
        setCurrentLine(i);
      }, FIRST_DELAY + i * LINE_INTERVAL);
      timersRef.current.push(t);
    }

    // Schedule dissolve.
    const dissolveAt = FIRST_DELAY + LINES.length * LINE_INTERVAL + FINAL_HOLD;
    const tDissolve = window.setTimeout(() => setPhase('dissolving'), dissolveAt);
    timersRef.current.push(tDissolve);

    // Schedule hand-off to the hero.
    const tDone = window.setTimeout(complete, dissolveAt + DISSOLVE_MS);
    timersRef.current.push(tDone);

    return () => {
      timersRef.current.forEach((t) => window.clearTimeout(t));
      timersRef.current = [];
    };
  }, [complete]);

  const handleSkip = useCallback(() => {
    if (completedRef.current) return;
    timersRef.current.forEach((t) => window.clearTimeout(t));
    timersRef.current = [];
    setPhase('dissolving');
    const t = window.setTimeout(complete, DISSOLVE_MS);
    timersRef.current.push(t);
  }, [complete]);

  if (phase === 'pending' || phase === 'done') return null;

  return (
    <div
      className={`arrival-intro${phase === 'dissolving' ? ' is-dissolving' : ''}`}
      role="presentation"
    >
      <div className="arrival-intro__bg" aria-hidden="true" />
      <div className="arrival-intro__glow" aria-hidden="true" />
      <div className="arrival-intro__stage" aria-live="polite">
        {LINES.map((line, i) => {
          const state =
            i < currentLine ? 'gone' : i === currentLine ? 'active' : 'waiting';
          return (
            <p
              key={i}
              className="arrival-intro__line"
              data-state={state}
              aria-hidden={state !== 'active'}
            >
              {line}
            </p>
          );
        })}
      </div>
      <button
        type="button"
        className="arrival-intro__skip"
        onClick={handleSkip}
        aria-label="Skip intro"
      >
        Skip
      </button>
    </div>
  );
}
