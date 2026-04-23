import type { Metadata, Viewport } from 'next';
import './proof.css';
import ProofExperience from './ProofExperience';

export const metadata: Metadata = {
  title: 'ProofHook — Turn what you know into what you\u2019re known for',
  description:
    'A premium creative engine for turning expertise into attention, audience, and measurable proof.',
  openGraph: {
    title: 'ProofHook',
    description: 'Turn what you know into what you\u2019re known for.',
    type: 'website',
  },
};

// Dark theme ambient meta so mobile browser chrome matches the page.
export const viewport: Viewport = {
  themeColor: '#05070a',
  colorScheme: 'dark',
};

interface ProofPageProps {
  searchParams: { replay?: string };
}

/**
 * Public /proof route.
 *
 * Server component wrapper — the cinematic experience itself is a client
 * component (`ProofExperience`) that owns stage orchestration, audio,
 * persistence, and all interaction. Keeping this wrapper thin means the
 * initial HTML shell loads instantly, and the client takes over from there.
 *
 * Query params:
 *   ?replay=1 — force the intro to play even if the session flag is set.
 *               Useful for QA, for hard-resets after a bad cached state,
 *               and for linking directly to the full sequence.
 */
export default function ProofPage({ searchParams }: ProofPageProps) {
  const forceIntro = searchParams?.replay !== undefined;
  return <ProofExperience forceIntro={forceIntro} />;
}
