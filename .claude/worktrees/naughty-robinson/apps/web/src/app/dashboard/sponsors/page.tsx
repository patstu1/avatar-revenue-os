'use client';

import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { phase7Api } from '@/lib/phase7-api';
import { Handshake, Star, TrendingUp } from 'lucide-react';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

export default function SponsorsPage() {
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
    queryKey: ['sponsors', selectedBrandId],
    queryFn: () => phase7Api.sponsorOpportunities(selectedBrandId).then((r) => r.data),
    enabled: Boolean(selectedBrandId),
  });

  const selectedBrand = useMemo(
    () => brands?.find((b) => String(b.id) === selectedBrandId),
    [brands, selectedBrandId]
  );

  const packages = (data?.packages || []) as any[];
  const profiles = (data?.profiles || []) as any[];
  const opportunities = (data?.opportunities || []) as any[];

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
    return <div className="card text-center py-12 text-gray-500">Create a brand to view sponsor opportunities.</div>;
  }

  return (
    <div className="space-y-8 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Handshake className="text-brand-500" size={28} aria-hidden />
          Sponsor Opportunities
        </h1>
        <p className="text-gray-400 mt-1 max-w-3xl">
          Phase 7 sponsor package matching, rate suggestions, and opportunity scoring.
        </p>
      </div>

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          value={selectedBrandId}
          onChange={(e) => setSelectedBrandId(e.target.value)}
          aria-label="Select brand for sponsor opportunities"
        >
          {brands.map((b) => (
            <option key={b.id} value={String(b.id)}>
              {b.name}
            </option>
          ))}
        </select>
        {selectedBrand && <p className="text-sm text-gray-500 mt-2">Viewing: {selectedBrand.name}</p>}
      </div>

      {isLoading && <div className="card py-12 text-center text-gray-500">Loading sponsor data…</div>}
      {isError && <div className="card border-red-900/50 text-red-300 py-6">{errMessage(error)}</div>}

      {data && !isLoading && (
        <>
          <div className="card overflow-x-auto">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Star size={18} className="text-amber-400" aria-hidden />
              Sponsor Packages
            </h2>
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="text-gray-500 text-xs border-b border-gray-800">
                  <th className="py-2 pr-4">Package</th>
                  <th className="py-2 pr-4">Suggested Rate</th>
                  <th className="py-2 pr-4">Priority</th>
                  <th className="py-2">Rationale</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800 text-gray-300">
                {packages.map((p: any, i: number) => (
                  <tr key={p.id || i}>
                    <td className="py-2 pr-4 text-white font-medium">{p.package_name || p.name || '—'}</td>
                    <td className="py-2 pr-4 text-emerald-300">${Number(p.suggested_rate || 0).toLocaleString()}</td>
                    <td className="py-2 pr-4">
                      <span className="inline-block px-2 py-0.5 rounded text-xs bg-brand-600/25 text-brand-300">
                        {p.priority || '—'}
                      </span>
                    </td>
                    <td className="py-2 text-gray-400 max-w-md">{p.rationale || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!packages.length && <p className="text-gray-500 text-sm mt-2">No sponsor packages generated yet.</p>}
          </div>

          {profiles.length > 0 && (
            <div className="card">
              <h2 className="text-lg font-semibold text-white mb-4">Sponsor Profiles</h2>
              <ul className="space-y-3">
                {profiles.map((p: any, i: number) => (
                  <li key={p.id || i} className="rounded-lg border border-gray-800 bg-gray-900/40 p-4 text-sm">
                    <p className="text-white font-medium">{p.sponsor_name || p.name || 'Unknown sponsor'}</p>
                    <p className="text-gray-400 mt-1">{p.industry || ''} {p.fit_score != null && `· Fit: ${p.fit_score}`}</p>
                    {p.notes && <p className="text-xs text-gray-500 mt-2">{p.notes}</p>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {opportunities.length > 0 && (
            <div className="card">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <TrendingUp size={18} className="text-emerald-400" aria-hidden />
                Opportunities
              </h2>
              <ul className="space-y-3">
                {opportunities.map((o: any, i: number) => (
                  <li key={o.id || i} className="rounded-lg border border-gray-800 bg-gray-900/40 p-4 text-sm">
                    <div className="flex justify-between items-start gap-4">
                      <div>
                        <p className="text-white font-medium">{o.title || o.opportunity_type || 'Opportunity'}</p>
                        <p className="text-gray-400 mt-1">{o.description || o.rationale || '—'}</p>
                      </div>
                      {o.estimated_value != null && (
                        <span className="text-emerald-300 font-medium shrink-0">
                          ${Number(o.estimated_value).toLocaleString()}
                        </span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}
