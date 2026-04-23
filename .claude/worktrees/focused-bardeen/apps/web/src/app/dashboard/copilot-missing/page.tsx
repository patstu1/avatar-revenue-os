'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { copilotApi } from '@/lib/copilot-api';
import { AlertTriangle } from 'lucide-react';

type Brand = { id: string; name: string };

type MissingItem = {
  id: string;
  item_name: string;
  category: string;
  description: string;
  truth_level: string;
  action: string;
};

function categoryBadge(cat: string) {
  const c = String(cat).toLowerCase();
  if (c === 'credential') return 'bg-red-900/40 text-red-200 border-red-700/50';
  if (c === 'integration') return 'bg-orange-900/40 text-orange-200 border-orange-700/50';
  if (c === 'configuration') return 'bg-amber-900/40 text-amber-200 border-amber-700/50';
  if (c === 'data') return 'bg-blue-900/40 text-blue-200 border-blue-700/50';
  return 'bg-gray-800 text-gray-300 border-gray-700';
}

function truthLevelBadge(level: string) {
  const l = String(level).toLowerCase();
  if (l === 'live') return 'bg-emerald-900/40 text-emerald-200 border-emerald-700/50';
  if (l === 'configured_missing_credentials') return 'bg-red-900/40 text-red-200 border-red-700/50';
  if (l === 'architecturally_present') return 'bg-violet-900/40 text-violet-200 border-violet-700/50';
  if (l === 'blocked') return 'bg-red-900/40 text-red-200 border-red-700/50';
  return 'bg-gray-800 text-gray-300 border-gray-700';
}

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

export default function CopilotMissingPage() {
  const [selectedBrandId, setSelectedBrandId] = useState('');

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) setSelectedBrandId(String(brands[0].id));
  }, [brands, selectedBrandId]);

  const missingQ = useQuery({
    queryKey: ['copilot-missing', selectedBrandId],
    queryFn: () => copilotApi.missingItems(selectedBrandId).then((r) => r.data as MissingItem[]),
    enabled: Boolean(selectedBrandId),
  });

  if (brandsLoading) {
    return (
      <div className="min-h-[60vh] rounded-xl border border-gray-800 bg-gray-900 p-8 text-white">
        <div className="h-8 w-80 bg-gray-800 rounded animate-pulse mb-6" />
        <div className="h-40 bg-gray-800/80 rounded animate-pulse" />
        <p className="text-center text-brand-300 mt-8">Loading…</p>
      </div>
    );
  }

  if (brandsError) {
    return (
      <div className="rounded-xl border border-red-900/50 bg-gray-900 p-8 text-red-300 flex items-center gap-2">
        <AlertTriangle size={20} />
        {errMessage(brandsErr)}
      </div>
    );
  }

  if (!brands?.length) {
    return (
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-12 text-center text-gray-400">
        Create a brand to view Missing Items.
      </div>
    );
  }

  return (
    <div className="space-y-6 rounded-xl border border-gray-800 bg-gray-900 p-6 md:p-8 text-white">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2 text-white">
          <AlertTriangle className="text-brand-300" size={28} />
          Missing Items
        </h1>
        <p className="text-gray-400 mt-1 text-sm">Credentials, integrations, and configurations that need operator attention.</p>
      </div>

      <div className="max-w-xl rounded-lg border border-gray-800 bg-gray-950/50 p-4">
        <label className="block text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">Brand</label>
        <select
          aria-label="Select brand"
          className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 outline-none"
          value={selectedBrandId}
          onChange={(e) => setSelectedBrandId(e.target.value)}
        >
          {brands.map((b) => (
            <option key={b.id} value={String(b.id)}>{b.name}</option>
          ))}
        </select>
      </div>

      {missingQ.isLoading && <div className="py-16 text-center text-brand-300">Loading missing items…</div>}
      {missingQ.isError && (
        <div className="rounded-lg border border-red-900/50 p-6 text-red-300 flex gap-2">
          <AlertTriangle size={20} />
          {errMessage(missingQ.error)}
        </div>
      )}
      {!missingQ.isLoading && !missingQ.isError && !(missingQ.data?.length ?? 0) && (
        <div className="py-16 text-center text-gray-500 border border-dashed border-gray-800 rounded-lg">
          No missing items detected. System is fully configured.
        </div>
      )}

      {missingQ.data && missingQ.data.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {missingQ.data.map((item) => (
            <div key={item.id} className="rounded-xl border border-gray-800 bg-gray-950/40 p-4 space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="font-semibold text-white text-sm">{item.item_name}</h3>
              </div>
              <div className="flex flex-wrap gap-2">
                <span className={`inline-flex rounded-md border px-2 py-0.5 text-[10px] font-medium capitalize ${categoryBadge(item.category)}`}>
                  {item.category}
                </span>
                <span className={`inline-flex rounded-md border px-2 py-0.5 text-[10px] font-medium ${truthLevelBadge(item.truth_level)}`}>
                  {item.truth_level?.replace(/_/g, ' ')}
                </span>
              </div>
              <p className="text-sm text-gray-400">{item.description}</p>
              <div className="rounded-lg border border-brand-500/30 bg-brand-600/10 px-3 py-2">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Action Required</p>
                <p className="text-sm text-brand-300">{item.action}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
