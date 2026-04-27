import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import Providers from '@/components/Providers';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains-mono',
  display: 'swap',
});

// Resolved at build time so Next.js can build absolute Open Graph and
// Twitter card URLs from per-page relative paths. Falls back to the
// production domain if the env var is missing.
const SITE_URL = (
  process.env.NEXT_PUBLIC_SITE_URL ?? 'https://app.nvironments.com'
).replace(/\/$/, '');

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: 'ProofHook — Creative Proof + AI Buyer Trust Infrastructure',
    template: '%s | ProofHook',
  },
  description:
    'ProofHook builds the proof, hooks, and trust signals businesses need to be understood, trusted, and chosen in the AI decision era. Take the AI Buyer Trust Test.',
  applicationName: 'ProofHook',
  authors: [{ name: 'ProofHook' }],
  keywords: [
    'AI Buyer Trust Infrastructure',
    'AI decision layer',
    'AI search authority',
    'short-form creative',
    'proof video',
    'paid social creative',
    'authority graph',
    'ProofHook',
  ],
  alternates: { canonical: SITE_URL + '/' },
  openGraph: {
    type: 'website',
    siteName: 'ProofHook',
    title: 'ProofHook — Creative Proof + AI Buyer Trust Infrastructure',
    description:
      'Google helped customers find businesses. AI is helping them decide who to trust. Take the AI Buyer Trust Test.',
    url: SITE_URL + '/',
    locale: 'en_US',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'ProofHook — Creative Proof + AI Buyer Trust Infrastructure',
    description:
      'Google helped customers find businesses. AI is helping them decide who to trust. Take the AI Buyer Trust Test.',
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-snippet': -1,
      'max-image-preview': 'large',
    },
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable} dark`}>
      <body className="min-h-screen font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
