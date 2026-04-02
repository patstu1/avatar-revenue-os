'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';

/**
 * Resolves the active brand ID for the current user.
 * Checks localStorage first, then fetches the first brand from the API.
 */
export function useBrandId(): string | null {
  const [brandId, setBrandId] = useState<string | null>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('aro_brand_id');
    }
    return null;
  });

  useEffect(() => {
    if (brandId) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get<{ items: { id: string }[] }>('/api/v1/brands/', { params: { page: 1 } });
        const first = res.data?.items?.[0];
        if (!cancelled && first?.id) {
          localStorage.setItem('aro_brand_id', first.id);
          setBrandId(first.id);
        }
      } catch {
        // token missing or no brands — leave null
      }
    })();
    return () => { cancelled = true; };
  }, [brandId]);

  return brandId;
}
