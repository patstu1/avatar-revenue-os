'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuthStore } from '@/lib/store';
import { apiFetch } from '@/lib/api';
import Sidebar from '@/components/Sidebar';
import TopBar from '@/components/TopBar';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const hydrated = useAuthStore((s) => s.hydrated);
  const [onboardingChecked, setOnboardingChecked] = useState(false);

  useEffect(() => {
    if (hydrated && !isAuthenticated) {
      router.push('/login');
    }
  }, [hydrated, isAuthenticated, router]);

  useEffect(() => {
    if (!hydrated || !isAuthenticated) return;
    if (pathname?.startsWith('/dashboard/onboarding')) {
      setOnboardingChecked(true);
      return;
    }

    let cancelled = false;
    apiFetch<{ is_complete: boolean }>('/api/v1/onboarding/status')
      .then((status) => {
        if (cancelled) return;
        if (!status.is_complete) {
          router.replace('/dashboard/onboarding');
        }
        setOnboardingChecked(true);
      })
      .catch(() => {
        if (!cancelled) setOnboardingChecked(true);
      });
    return () => { cancelled = true; };
  }, [hydrated, isAuthenticated, pathname, router]);

  if (!hydrated || (isAuthenticated && !onboardingChecked)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-950">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
          <p className="text-sm text-gray-500 font-mono">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) return null;

  const isOnboarding = pathname?.startsWith('/dashboard/onboarding');

  if (isOnboarding) {
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
