'use client';

/**
 * ProofExperience
 * ----------------
 * Cinematic arrival for the ProofHook wall.
 *
 * The wall is conceptually a 16-screen installation but visually it is
 * ONE continuous surface. At all times the entire wall is a single
 * canvas. It never splits into independent tiles.
 *
 *   Stage 1  welcome  — the surface is dimmed, the welcome text composes
 *                        across the full wall, line by line.
 *   Stage 2  hero     — the welcome fades out, the surface brightens, and
 *                        the hero video plays on loop across the whole wall.
 *                        This is the permanent final state.
 *
 * The welcome plays exactly once per browser session. Subsequent loads
 * jump straight to `hero` so the user never waits again. `?replay=1`
 * forces the welcome regardless of session state.
 */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import {
  SESSION_KEY,
  STAGE_TIMINGS,
  UNIFIED_HERO,
  WELCOME_LINES,
} from './tile-config';

type Stage = 'welcome' | 'hero';

interface ProofExperienceProps {
  /**
   * Force the welcome to play even if the session flag is set. Used by
   * `?replay=1` and by any internal "replay intro" affordance.
   */
  forceIntro?: boolean;
}

// --------------------------------------------------------------------
// Session persistence
// --------------------------------------------------------------------

function readSessionFlag(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return window.sessionStorage.getItem(SESSION_KEY) === 'true';
  } catch {
    return false;
  }
}

function writeSessionFlag() {
  if (typeof window === 'undefined') return;
  try {
    window.sessionStorage.setItem(SESSION_KEY, 'true');
  } catch {
    /* ignore quota / privacy mode */
  }
}

// --------------------------------------------------------------------
// Welcome overlay — one unified text composition above the wall
// --------------------------------------------------------------------

function WelcomeOverlay({ visibleCount }: { visibleCount: number }) {
  return (
    <div className="proof-welcome" aria-live="polite">
      <div className="proof-welcome-stack">
        {WELCOME_LINES.map((line, idx) => {
          const isVisible = idx < visibleCount;
          // Line 1 contains "ProofHook" — wrap it in a span so CSS can shimmer it.
          if (idx === 1) {
            const [before, , after] = line.split(/(ProofHook)/);
            return (
              <p
                key={idx}
                className="proof-welcome-line"
                data-idx={idx}
                data-visible={isVisible ? 'true' : 'false'}
              >
                {before}
                <span>ProofHook</span>
                {after}
              </p>
            );
          }
          return (
            <p
              key={idx}
              className="proof-welcome-line"
              data-idx={idx}
              data-visible={isVisible ? 'true' : 'false'}
            >
              {line}
            </p>
          );
        })}
        <span className="proof-welcome-rule" aria-hidden="true" />
      </div>
    </div>
  );
}

// --------------------------------------------------------------------
// Audio pulse — soft sine-wave beat generated via Web Audio
// Muted by default; user can unmute via the HUD button.
// --------------------------------------------------------------------

function useAmbientPulse(enabled: boolean) {
  const ctxRef = useRef<AudioContext | null>(null);
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    if (!enabled) {
      if (intervalRef.current) {
        window.clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      if (ctxRef.current) {
        void ctxRef.current.close().catch(() => {});
        ctxRef.current = null;
      }
      return;
    }

    const Ctx =
      (typeof window !== 'undefined' &&
        (window.AudioContext ||
          (window as typeof window & { webkitAudioContext?: typeof AudioContext })
            .webkitAudioContext)) ||
      null;
    if (!Ctx) return;

    const ctx = new Ctx();
    ctxRef.current = ctx;

    const master = ctx.createGain();
    master.gain.value = 0.045;
    master.connect(ctx.destination);

    const pulse = () => {
      const now = ctx.currentTime;
      // Low sub thump
      const sub = ctx.createOscillator();
      sub.type = 'sine';
      sub.frequency.value = 58;
      const subEnv = ctx.createGain();
      subEnv.gain.setValueAtTime(0, now);
      subEnv.gain.linearRampToValueAtTime(1, now + 0.04);
      subEnv.gain.exponentialRampToValueAtTime(0.001, now + 0.45);
      sub.connect(subEnv);
      subEnv.connect(master);
      sub.start(now);
      sub.stop(now + 0.5);

      // Airy shimmer on top
      const hi = ctx.createOscillator();
      hi.type = 'sine';
      hi.frequency.value = 820;
      const hiEnv = ctx.createGain();
      hiEnv.gain.setValueAtTime(0, now);
      hiEnv.gain.linearRampToValueAtTime(0.18, now + 0.08);
      hiEnv.gain.exponentialRampToValueAtTime(0.001, now + 0.5);
      const hiFilter = ctx.createBiquadFilter();
      hiFilter.type = 'lowpass';
      hiFilter.frequency.value = 1600;
      hi.connect(hiFilter);
      hiFilter.connect(hiEnv);
      hiEnv.connect(master);
      hi.start(now);
      hi.stop(now + 0.55);
    };

    ctx.resume().then(() => {
      pulse();
      intervalRef.current = window.setInterval(pulse, 2200);
    });

    return () => {
      if (intervalRef.current) {
        window.clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      void ctx.close().catch(() => {});
      ctxRef.current = null;
    };
  }, [enabled]);
}

// --------------------------------------------------------------------
// Icon primitives — inline SVG, no external dependency
// --------------------------------------------------------------------

function IconVolumeOn() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M11 5L6 9H2v6h4l5 4V5z" />
      <path d="M15.54 8.46a5 5 0 010 7.07" />
      <path d="M19.07 4.93a10 10 0 010 14.14" />
    </svg>
  );
}

function IconVolumeOff() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M11 5L6 9H2v6h4l5 4V5z" />
      <line x1="23" y1="9" x2="17" y2="15" />
      <line x1="17" y1="9" x2="23" y2="15" />
    </svg>
  );
}

function IconArrow() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  );
}

// --------------------------------------------------------------------
// Main component
// --------------------------------------------------------------------

export default function ProofExperience({ forceIntro = false }: ProofExperienceProps) {
  const [stage, setStage] = useState<Stage>('welcome');
  const [visibleLines, setVisibleLines] = useState(0);
  const [audioOn, setAudioOn] = useState(false);
  const [heroFailed, setHeroFailed] = useState(false);

  const videoRef = useRef<HTMLVideoElement | null>(null);

  // On mount: if the session flag is set and we're not forcing, jump
  // straight to hero. Reading sessionStorage inside an effect avoids
  // SSR hydration mismatch.
  useEffect(() => {
    if (!forceIntro && readSessionFlag()) {
      setStage('hero');
      setVisibleLines(WELCOME_LINES.length);
    }
  }, [forceIntro]);

  // Welcome line scheduler
  useEffect(() => {
    if (stage !== 'welcome') return;
    const schedule = [
      STAGE_TIMINGS.welcomeLine1,
      STAGE_TIMINGS.welcomeLine2,
      STAGE_TIMINGS.welcomeLine3,
      STAGE_TIMINGS.welcomeLine4,
    ];
    const timers = schedule.map((delay, i) =>
      window.setTimeout(() => {
        setVisibleLines((prev) => Math.max(prev, i + 1));
      }, delay),
    );
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, [stage]);

  // Welcome → hero progression (only one transition in the whole sequence)
  useEffect(() => {
    if (stage !== 'welcome') return;
    const timer = window.setTimeout(() => {
      writeSessionFlag();
      setStage('hero');
    }, STAGE_TIMINGS.welcomeEnd);
    return () => window.clearTimeout(timer);
  }, [stage]);

  // Start hero video playback when we enter hero stage
  useEffect(() => {
    const video = videoRef.current;
    if (!video || heroFailed) return;
    if (stage === 'hero') {
      const p = video.play();
      if (p && typeof p.then === 'function') {
        p.catch(() => {
          /* autoplay refused — fallback remains behind the video */
        });
      }
    }
  }, [stage, heroFailed]);

  // Skip → straight to hero
  const handleSkip = useCallback(() => {
    setVisibleLines(WELCOME_LINES.length);
    writeSessionFlag();
    setStage('hero');
  }, []);

  // ESC / Enter skip during welcome
  useEffect(() => {
    if (stage !== 'welcome') return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' || e.key === 'Enter') handleSkip();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [stage, handleSkip]);

  useAmbientPulse(audioOn);

  const heroHasVideo = Boolean(UNIFIED_HERO.videoSrc) && !heroFailed;

  return (
    <div className="proof-shell" data-stage={stage}>
      {/* Deep ambient backdrop — subtle drift behind the wall */}
      <div className="proof-ambient" aria-hidden="true" />

      {/* The wall itself — one continuous unified surface */}
      <div className="proof-wall-wrap">
        <div className="proof-wall">
          <div className="proof-unified" aria-hidden="true">
            {/* CSS composition is always beneath — acts as fallback + blend target */}
            <div className="proof-unified-fallback" />
            {heroHasVideo && (
              <video
                ref={videoRef}
                src={UNIFIED_HERO.videoSrc}
                poster={UNIFIED_HERO.posterSrc}
                muted
                playsInline
                loop
                preload="auto"
                aria-hidden="true"
                onError={() => setHeroFailed(true)}
              />
            )}
          </div>
        </div>
      </div>

      {/* Grain + vignette */}
      <div className="proof-grain" aria-hidden="true" />
      <div className="proof-vignette" aria-hidden="true" />

      {/* Welcome text composition (stage 1) */}
      <WelcomeOverlay visibleCount={visibleLines} />

      {/* HUD: brand mark + skip + audio */}
      <div className="proof-hud">
        <div className="proof-mark">
          <span className="proof-mark-dot" aria-hidden="true" />
          ProofHook
        </div>
        <div className="proof-hud-actions">
          {stage === 'welcome' && (
            <button
              type="button"
              className="proof-skip"
              onClick={handleSkip}
              aria-label="Skip welcome sequence"
            >
              Skip
            </button>
          )}
          <button
            type="button"
            className="proof-icon-btn"
            onClick={() => setAudioOn((v) => !v)}
            aria-label={audioOn ? 'Mute ambient beat' : 'Unmute ambient beat'}
            aria-pressed={audioOn}
          >
            {audioOn ? <IconVolumeOn /> : <IconVolumeOff />}
          </button>
        </div>
      </div>

      {/* Footer: tagline + CTA — appears in hero stage */}
      <div className="proof-footer">
        <div className="proof-tagline">Turn what you know into what you&rsquo;re known for.</div>
        <a href="/login" className="proof-cta">
          Step inside
          <IconArrow />
        </a>
      </div>
    </div>
  );
}
