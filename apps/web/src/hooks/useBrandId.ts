'use client';

import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { useAppStore } from '@/lib/store';

interface Brand {
  id: string;
  name: string;
  slug: string;
  is_active?: boolean;
}

/**
 * Canonical brand-context hook.
 *
 * Resolves the currently-selected brand for the operator, backed by:
 *   - useAppStore.selectedBrandId (persisted in localStorage)
 *   - brandsApi.list() (DB source of truth, active-only by default)
 *
 * Self-healing behavior:
 *   - If there is no stored brand, picks the first active brand
 *   - If the stored brand is no longer in the active list (archived/deleted),
 *     clears it and re-picks the first active brand
 *   - Never falls back to 'test' or any hardcoded default
 */
export function useBrandId(): string | null {
  const brandId = useAppStore((s) => s.selectedBrandId);
  const setSelectedBrandId = useAppStore((s) => s.setSelectedBrandId);

  // Fetch the live list of active brands (cached by React Query)
  const { data: brands } = useQuery<Brand[]>({
    queryKey: ['brands', 'active'],
    queryFn: () => brandsApi.list(1).then((r) => (r.data as Brand[]) || []),
    staleTime: 60_000,
  });

  useEffect(() => {
    if (!brands || brands.length === 0) return;

    const activeIds = new Set(brands.map((b) => b.id));

    // No brand cached → pick first active
    if (!brandId) {
      setSelectedBrandId(brands[0].id);
      return;
    }

    // Cached brand is stale (archived/deleted) → re-pick
    if (!activeIds.has(brandId)) {
      setSelectedBrandId(brands[0].id);
    }
  }, [brands, brandId, setSelectedBrandId]);

  return brandId;
}

/**
 * Helper hook that returns the full list of active brands plus the currently
 * selected brand id. Used by BrandSwitcher and any page that needs to render
 * a brand picker.
 */
export function useActiveBrands(): { brands: Brand[]; brandId: string | null; setBrandId: (id: string | null) => void } {
  const brandId = useBrandId();
  const setBrandId = useAppStore((s) => s.setSelectedBrandId);
  const { data: brands } = useQuery<Brand[]>({
    queryKey: ['brands', 'active'],
    queryFn: () => brandsApi.list(1).then((r) => (r.data as Brand[]) || []),
    staleTime: 60_000,
  });
  return { brands: brands || [], brandId, setBrandId };
}
