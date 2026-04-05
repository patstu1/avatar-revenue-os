'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuthStore } from '@/lib/store';
import { apiFetch } from '@/lib/api';
import Sidebar from '@/components/Sidebar';
import TopBar from '@/components/TopBar';

interface SystemState {
  is_complete: boolean;
  system_state: 'empty' | 'partial' | 'ready';
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const hydrated = useAuthStore((s) => s.hydrated);
  const [stateChecked, setStateChecked] = useState(false);

  useEffect(() => {
    if (hydrated && !isAuthenticated) {
      router.push('/login');
    }
  }, [hydrated, isAuthenticated, router]);

  useEffect(() => {
    if (!hydrated || !isAuthenticated) return;

    // Allow GM, setup and onboarding pages without redirect loops
    if (pathname?.startsWith('/dashboard/gm') || pathname?.startsWith('/dashboard/setup') || pathname?.startsWith('/dashboard/onboarding')) {
      setStateChecked(true);
      return;
    }

    let cancelled = false;
    apiFetch<SystemState>('/api/v1/onboarding/status')
      .then((state) => {
        if (cancelled) return;

        if (state.system_state === 'empty') {
          // Nothing configured → GM takes over
          router.replace('/dashboard/gm');
        }
        // "partial" and "ready" both go to dashboard — no forced gate
        // Partial users see a setup banner on the dashboard instead
        setStateChecked(true);
      })
      .catch(() => {
        if (!cancelled) setStateChecked(true);
      });
    return () => { cancelled = true; };
  }, [hydrated, isAuthenticated, pathname, router]);

  if (!hydrated || (isAuthenticated && !stateChecked)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-950">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
          <p className="text-sm text-gray-500 font-mono">Initializing system...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) return null;

  const isSetup = pathname?.startsWith('/dashboard/setup');
  const isOnboarding = pathname?.startsWith('/dashboard/onboarding');

  // Setup and onboarding pages render without sidebar (full screen)
  if (isSetup || isOnboarding) {
    return (
      <div className="min-h-screen bg-gray-950 text-white">
        <main className="flex-1">
          <div className="p-8">
            {children}
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-x-hidden">
        <TopBar />
        <main className="flex-1">
          <div className="p-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
