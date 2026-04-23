'use client';

import { useEffect } from 'react';
import { api } from '@/lib/api';
import { useAppStore } from '@/lib/store';

/**
 * Resolves the active brand ID for the current user.
 * Uses useAppStore as the single source of truth, synced with localStorage.
 * Falls back to fetching the first brand from the API when none is stored.
 */
export function useBrandId(): string | null {
  const brandId = useAppStore((s) => s.selectedBrandId);
  const setSelectedBrandId = useAppStore((s) => s.setSelectedBrandId);

  useEffect(() => {
    if (brandId) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get('/api/v1/brands/', { params: { page: 1 } });
        const data = res.data;
        // Handle both array response and {items: [...]} response
        const brands = Array.isArray(data) ? data : data?.items ?? [];
        const first = brands[0];
        if (!cancelled && first?.id) {
          setSelectedBrandId(first.id);
        }
      } catch {
        // token missing or no brands — leave null
      }
    })();
    return () => { cancelled = true; };
  }, [brandId, setSelectedBrandId]);

  return brandId;
}
