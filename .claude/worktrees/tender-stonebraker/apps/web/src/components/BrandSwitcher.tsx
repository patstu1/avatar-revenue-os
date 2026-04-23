"use client";

import { useActiveBrands } from "@/hooks/useBrandId";
import { ChevronDown } from "lucide-react";

/**
 * Canonical brand switcher shown in the TopBar.
 *
 * Uses the same source of truth (`useActiveBrands`) as every operating page,
 * so every brand-scoped view reconciles to the same selection.
 */
export default function BrandSwitcher() {
  const { brands, brandId, setBrandId } = useActiveBrands();

  if (!brands || brands.length === 0) {
    return (
      <span className="text-xs text-gray-500 font-mono px-2 py-1 border border-gray-800 rounded">
        no active brands
      </span>
    );
  }

  const current = brands.find((b) => b.id === brandId) || brands[0];

  return (
    <div className="relative">
      <select
        value={brandId || current.id}
        onChange={(e) => setBrandId(e.target.value)}
        className="appearance-none bg-gray-800/60 text-gray-200 text-xs font-medium pl-3 pr-7 py-1.5 rounded-md border border-gray-700 hover:bg-gray-800 focus:outline-none focus:ring-1 focus:ring-brand-500 cursor-pointer min-w-[160px]"
        aria-label="Active brand"
      >
        {brands.map((b) => (
          <option key={b.id} value={b.id} className="bg-gray-900">
            {b.name}
          </option>
        ))}
      </select>
      <ChevronDown
        size={12}
        className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none"
      />
    </div>
  );
}
