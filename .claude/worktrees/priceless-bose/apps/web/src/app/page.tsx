'use client';

/**
 * ProofHook arrival landing (`/`).
 *
 * First-load experience: dark canvas → cinematic text intro → hero stage
 * with ambient motion + optional ambient beat.
 *
 * The previous version of this file was a server-side redirect to
 * `/login`. The login route is still reachable directly and via the
 * hero CTA — middleware is unchanged.
 */

import { useCallback, useState } from 'react';
import ArrivalIntro from '@/components/arrival/ArrivalIntro';
import AmbientBeat from '@/components/arrival/AmbientBeat';
import HeroStage from '@/components/arrival/HeroStage';

export default function Home() {
  const [introDone, setIntroDone] = useState(false);

  const handleIntroComplete = useCallback(() => {
    setIntroDone(true);
  }, []);

  return (
    <main className="arrival-root">
      <HeroStage active={introDone} />
      <ArrivalIntro onComplete={handleIntroComplete} />
      <AmbientBeat armed={introDone} />
    </main>
  );
}
