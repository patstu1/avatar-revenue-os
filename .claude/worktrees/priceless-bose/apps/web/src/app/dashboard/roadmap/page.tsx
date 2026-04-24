'use client';

import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { phase7Api } from '@/lib/phase7-api';
import { Map, ArrowUpDown } from 'lucide-react';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

const categoryColors: Record<string, string> = {
  content: 'bg-brand-600/25 text-brand-300',
  monetization: 'bg-emerald-600/25 text-emerald-300',
  growth: 'bg-blue-600/25 text-blue-300',
  infrastructure: 'bg-purple-600/25 text-purple-300',
  partnerships: 'bg-amber-600/25 text-amber-300',
  audience: 'bg-rose-600/25 text-rose-300',
};

const effortColors: Record<string, string> = {
  low: 'text-emerald-400',
  medium: 'text-amber-400',
  high: 'text-red-400',
};

export default function RoadmapPage() {
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
    queryKey: ['roadmap', selectedBrandId],
    queryFn: () => phase7Api.roadmap(selectedBrandId).then((r) => r.data),
    enabled: Boolean(selectedBrandId),
  });

  const selectedBrand = useMemo(
    () => brands?.find((b) => String(b.id) === selectedBrandId),
    [brands, selectedBrandId]
  );

  const items = useMemo(() => {
    const raw = (data?.items || data || []) as any[];
    return [...raw].sort((a, b) => (Number(b.priority_score ?? b.priority ?? 0)) - (Number(a.priority_score ?? a.priority ?? 0)));
  }, [data]);

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
    return <div className="card text-center py-12 text-gray-500">Create a brand to view the autonomous roadmap.</div>;
  }

  return (
    <div className="space-y-8 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Map className="text-brand-500" size={28} aria-hidden />
          Autonomous Roadmap
        </h1>
        <p className="text-gray-400 mt-1 max-w-3xl">
          Phase 7 AI-generated roadmap — prioritized actions sorted by impact and effort.
        </p>
      </div>

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          value={selectedBrandId}
          onChange={(e) => setSelectedBrandId(e.target.value)}
          aria-label="Select brand for roadmap"
        >
          {brands.map((b) => (
            <option key={b.id} value={String(b.id)}>
              {b.name}
            </option>
          ))}
        </select>
        {selectedBrand && <p className="text-sm text-gray-500 mt-2">Viewing: {selectedBrand.name}</p>}
      </div>

      {isLoading && <div className="card py-12 text-center text-gray-500">Generating roadmap…</div>}
      {isError && <div className="card border-red-900/50 text-red-300 py-6">{errMessage(error)}</div>}

      {!isLoading && !isError && Array.isArray(items) && (
        <div className="space-y-3">
          {items.map((item: any, i: number) => {
            const category = String(item.category || 'general').toLowerCase();
            const effort = String(item.effort_level || item.effort || '').toLowerCase();
            const priority = Number(item.priority_score ?? item.priority ?? 0);
            return (
              <div key={item.id || i} className="card">
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`inline-block px-2 py-0.5 rounded text-xs uppercase tracking-wide ${categoryColors[category] || 'bg-gray-700 text-gray-300'}`}>
                        {category}
                      </span>
                      <span className="text-xs text-gray-500 flex items-center gap-1">
                        <ArrowUpDown size={12} aria-hidden />
                        Priority: {priority.toFixed(1)}
                      </span>
                    </div>
                    <h3 className="text-white font-medium">{item.title || '—'}</h3>
                    <p className="text-sm text-gray-400 mt-1">{item.description || '—'}</p>
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0 text-sm">
                    {item.estimated_impact != null && (
                      <span className="text-emerald-300">
                        Impact: ${Number(item.estimated_impact).toLocaleString()}
                      </span>
                    )}
                    {effort && (
                      <span className={`text-xs ${effortColors[effort] || 'text-gray-400'}`}>
                        Effort: {effort}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}

          {!items.length && (
            <div className="card text-center py-12 text-gray-500">
              No roadmap items generated yet. Run Phase 7 recompute to build the roadmap.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
