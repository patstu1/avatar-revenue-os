'use client';

import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { phase7Api } from '@/lib/phase7-api';
import { PiggyBank } from 'lucide-react';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

export default function CapitalAllocationPage() {
  const [selectedBrandId, setSelectedBrandId] = useState('');

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) {
      setSelectedBrandId(String(brands[0].id));
    }
  }, [brands, selectedBrandId]);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['capital-allocation', selectedBrandId],
    queryFn: () => phase7Api.capitalAllocation(selectedBrandId).then((r) => r.data),
    enabled: Boolean(selectedBrandId),
  });

  const selectedBrand = useMemo(
    () => brands?.find((b) => String(b.id) === selectedBrandId),
    [brands, selectedBrandId]
  );

  const allocations = (data?.allocations || data || []) as any[];
  const totalBudget = allocations.reduce((sum: number, a: any) => sum + Number(a.amount || a.dollar_amount || 0), 0);

  if (brandsLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-96 bg-gray-800 rounded animate-pulse" />
        <div className="card py-12 text-center text-gray-500">Loading…</div>
      </div>
    );
  }

  if (brandsError) {
    return <div className="card border-red-900/50 text-red-300 py-8 text-center">{errMessage(brandsErr)}</div>;
  }

  if (!brands?.length) {
    return <div className="card text-center py-12 text-gray-500">Create a brand to view capital allocation.</div>;
  }

  return (
    <div className="space-y-8 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <PiggyBank className="text-brand-500" size={28} aria-hidden />
          Capital Allocation
        </h1>
        <p className="text-gray-400 mt-1 max-w-3xl">
          Phase 7 budget allocation — where to deploy resources for maximum ROI.
        </p>
      </div>

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          value={selectedBrandId}
          onChange={(e) => setSelectedBrandId(e.target.value)}
          aria-label="Select brand for capital allocation"
        >
          {brands.map((b) => (
            <option key={b.id} value={String(b.id)}>
              {b.name}
            </option>
          ))}
        </select>
        {selectedBrand && <p className="text-sm text-gray-500 mt-2">Viewing: {selectedBrand.name}</p>}
      </div>

      {isLoading && <div className="card py-12 text-center text-gray-500">Computing capital allocation…</div>}
      {isError && <div className="card border-red-900/50 text-red-300 py-6">{errMessage(error)}</div>}

      {!isLoading && !isError && Array.isArray(allocations) && (
        <>
          {totalBudget > 0 && (
            <div className="card">
              <p className="text-gray-500 text-xs uppercase mb-1">Total Allocated Budget</p>
              <p className="text-3xl font-bold text-white">${totalBudget.toLocaleString()}</p>
            </div>
          )}

          <div className="space-y-3">
            {allocations.map((a: any, i: number) => {
              const pct = Number(a.percentage ?? a.allocation_pct ?? 0);
              const amount = Number(a.amount ?? a.dollar_amount ?? 0);
              const roi = Number(a.roi_multiplier ?? a.expected_roi ?? 0);
              return (
                <div key={a.id || i} className="card">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-3">
                    <h3 className="text-white font-medium">{a.target || a.category || a.channel || '—'}</h3>
                    <div className="flex items-center gap-4 text-sm shrink-0">
                      <span className="text-emerald-300 font-semibold">${amount.toLocaleString()}</span>
                      {roi > 0 && (
                        <span className="text-brand-300">{roi.toFixed(1)}× ROI</span>
                      )}
                    </div>
                  </div>

                  <div className="mb-2">
                    <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                      <span>Allocation</span>
                      <span>{pct.toFixed(1)}%</span>
                    </div>
                    <div className="w-full bg-gray-800 rounded-full h-2.5">
                      <div
                        className="bg-brand-500 h-2.5 rounded-full transition-all"
                        style={{ width: `${Math.min(pct, 100)}%` }}
                      />
                    </div>
                  </div>

                  {(a.rationale || a.reasoning) && (
                    <p className="text-sm text-gray-400">{a.rationale || a.reasoning}</p>
                  )}
                </div>
              );
            })}

            {!allocations.length && (
              <div className="card text-center py-12 text-gray-500">
                No capital allocation data yet. Run Phase 7 recompute to generate allocations.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
