'use client';

/**
 * AmbientBeat
 *
 * A subtle system pulse synthesized via the Web Audio API — no audio files.
 *
 * Pulse = low sine + second-harmonic through a lowpass filter, ~48 BPM,
 * very low peak gain. Uses a look-ahead scheduler so timing survives
 * setTimeout jitter.
 *
 * Audio never starts until the user clicks the toggle (browser autoplay
 * policies), and can be paused with the same control. The control is a
 * small, low-contrast pill in the bottom-right that stays out of the way.
 *
 * Props:
 *   armed  — when false, the toggle is disabled & hidden. The parent flips
 *            this to true after the intro completes so the control never
 *            appears during the greeting.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Volume2, VolumeX } from 'lucide-react';

type Props = {
  armed: boolean;
};

// Pulse rhythm
const BPM = 48;
const INTERVAL_SEC = 60 / BPM; // 1.25s
// Scheduler look-ahead
const LOOK_AHEAD_SEC = 0.5;
const SCHED_TICK_MS = 80;
// Pulse synthesis
const PEAK_GAIN = 0.055;
const FUNDAMENTAL_HZ = 62;
const HARMONIC_HZ = 124;
const FILTER_CUTOFF_HZ = 240;

type AudioRefs = {
  ctx: AudioContext | null;
  master: GainNode | null;
  nextPulse: number;
  schedHandle: number | null;
};

export default function AmbientBeat({ armed }: Props) {
  const [playing, setPlaying] = useState(false);
  const [supported, setSupported] = useState(true);
  const [visible, setVisible] = useState(false);
  const refs = useRef<AudioRefs>({
    ctx: null,
    master: null,
    nextPulse: 0,
    schedHandle: null,
  });

  // Detect Web Audio support on mount.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const hasAudio =
      typeof window.AudioContext !== 'undefined' ||
      typeof (window as unknown as { webkitAudioContext?: unknown }).webkitAudioContext !==
        'undefined';
    setSupported(hasAudio);
  }, []);

  // Reveal the control with a short fade once the intro hands off.
  useEffect(() => {
    if (!armed) {
      setVisible(false);
      return;
    }
    const t = window.setTimeout(() => setVisible(true), 280);
    return () => window.clearTimeout(t);
  }, [armed]);

  // Schedule individual pulses inside the look-ahead window.
  const scheduleAhead = useCallback(() => {
    const r = refs.current;
    if (!r.ctx || !r.master) return;
    const horizon = r.ctx.currentTime + LOOK_AHEAD_SEC;
    while (r.nextPulse < horizon) {
      scheduleSinglePulse(r.ctx, r.master, r.nextPulse);
      r.nextPulse += INTERVAL_SEC;
    }
  }, []);

  const ensureContext = useCallback(() => {
    const r = refs.current;
    if (r.ctx) return r.ctx;
    const Ctor =
      (typeof window !== 'undefined' && window.AudioContext) ||
      (typeof window !== 'undefined' &&
        (window as unknown as { webkitAudioContext?: typeof AudioContext })
          .webkitAudioContext);
    if (!Ctor) return null;
    const ctx = new Ctor();
    const master = ctx.createGain();
    master.gain.value = 0; // start at zero; fade up on play
    master.connect(ctx.destination);
    r.ctx = ctx;
    r.master = master;
    r.nextPulse = ctx.currentTime + 0.1;
    return ctx;
  }, []);

  const startBeat = useCallback(async () => {
    const ctx = ensureContext();
    const r = refs.current;
    if (!ctx || !r.master) {
      setSupported(false);
      return;
    }
    if (ctx.state === 'suspended') {
      try {
        await ctx.resume();
      } catch {
        /* user may have navigated away */
      }
    }
    // Reset the schedule so the first pulse feels "on time".
    r.nextPulse = ctx.currentTime + 0.15;
    // Smooth fade-in of master gain (no clicks).
    const now = ctx.currentTime;
    r.master.gain.cancelScheduledValues(now);
    r.master.gain.setValueAtTime(r.master.gain.value, now);
    r.master.gain.linearRampToValueAtTime(1, now + 0.6);

    scheduleAhead();
    if (r.schedHandle == null) {
      r.schedHandle = window.setInterval(scheduleAhead, SCHED_TICK_MS);
    }
    setPlaying(true);
  }, [ensureContext, scheduleAhead]);

  const stopBeat = useCallback(() => {
    const r = refs.current;
    if (!r.ctx || !r.master) {
      setPlaying(false);
      return;
    }
    const now = r.ctx.currentTime;
    r.master.gain.cancelScheduledValues(now);
    r.master.gain.setValueAtTime(r.master.gain.value, now);
    r.master.gain.linearRampToValueAtTime(0, now + 0.35);

    if (r.schedHandle != null) {
      window.clearInterval(r.schedHandle);
      r.schedHandle = null;
    }
    setPlaying(false);
  }, []);

  // Teardown on unmount.
  useEffect(() => {
    return () => {
      const r = refs.current;
      if (r.schedHandle != null) {
        window.clearInterval(r.schedHandle);
        r.schedHandle = null;
      }
      if (r.ctx) {
        r.ctx.close().catch(() => {});
      }
      r.ctx = null;
      r.master = null;
    };
  }, []);

  if (!supported || !armed) return null;

  const label = playing ? 'Mute ambient beat' : 'Enable ambient beat';

  return (
    <button
      type="button"
      className={`arrival-beat${visible ? ' is-visible' : ''}${
        playing ? ' is-playing' : ''
      }`}
      onClick={() => (playing ? stopBeat() : void startBeat())}
      aria-label={label}
      title={label}
    >
      {playing ? <Volume2 size={14} /> : <VolumeX size={14} />}
      <span className="arrival-beat__dot" aria-hidden="true" />
    </button>
  );
}

// ──────────────────────────────────────────────────────────────────────
// Single pulse: sine + harmonic through lowpass, short envelope.
// ──────────────────────────────────────────────────────────────────────
function scheduleSinglePulse(ctx: AudioContext, master: GainNode, t: number) {
  const env = ctx.createGain();
  env.gain.setValueAtTime(0, t);
  env.gain.linearRampToValueAtTime(PEAK_GAIN, t + 0.018);
  env.gain.exponentialRampToValueAtTime(PEAK_GAIN * 0.35, t + 0.14);
  env.gain.exponentialRampToValueAtTime(0.0001, t + 0.42);

  const lp = ctx.createBiquadFilter();
  lp.type = 'lowpass';
  lp.frequency.value = FILTER_CUTOFF_HZ;
  lp.Q.value = 0.7;

  const osc1 = ctx.createOscillator();
  osc1.type = 'sine';
  osc1.frequency.value = FUNDAMENTAL_HZ;

  const osc2 = ctx.createOscillator();
  osc2.type = 'sine';
  osc2.frequency.value = HARMONIC_HZ;

  const harmGain = ctx.createGain();
  harmGain.gain.value = 0.35;

  osc1.connect(lp);
  osc2.connect(harmGain);
  harmGain.connect(lp);
  lp.connect(env);
  env.connect(master);

  osc1.start(t);
  osc2.start(t);
  osc1.stop(t + 0.5);
  osc2.stop(t + 0.5);
}
