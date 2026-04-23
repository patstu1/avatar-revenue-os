'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { copilotApi } from '@/lib/copilot-api';
import {
  Activity,
  AlertTriangle,
  Ban,
  ShieldAlert,
  Flame,
  Key,
  Server,
} from 'lucide-react';

type Brand = { id: string; name: string };

type QuickStatus = {
  urgency: string;
  blocked_count: number;
  failed_count: number;
  pending_actions_count: number;
  missing_credentials_count: number;
  live_providers_count: number;
  total_providers_count: number;
  top_blockers: { title: string; source: string }[];
  top_failures: { title: string; source: string }[];
  top_pending_actions: { title: string; source: string }[];
};

function urgencyColor(urgency: string) {
  const u = String(urgency).toLowerCase();
  if (u === 'critical') return 'bg-red-900/40 text-red-200 border-red-700/50';
  if (u === 'high') return 'bg-orange-900/40 text-orange-200 border-orange-700/50';
  if (u === 'medium') return 'bg-amber-900/40 text-amber-200 border-amber-700/50';
  if (u === 'low') return 'bg-emerald-900/40 text-emerald-200 border-emerald-700/50';
  return 'bg-gray-800 text-gray-300 border-gray-700';
}

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

export default function CopilotStatusPage() {
  const [selectedBrandId, setSelectedBrandId] = useState('');

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) setSelectedBrandId(String(brands[0].id));
  }, [brands, selectedBrandId]);

  const statusQ = useQuery({
    queryKey: ['copilot-quick-status', selectedBrandId],
    queryFn: () => copilotApi.quickStatus(selectedBrandId).then((r) => r.data as QuickStatus),
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
        Create a brand to view Quick Status.
      </div>
    );
  }

  const st = statusQ.data;

  return (
    <div className="space-y-6 rounded-xl border border-gray-800 bg-gray-900 p-6 md:p-8 text-white">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2 text-white">
          <Activity className="text-brand-300" size={28} />
          Quick Status
        </h1>
        <p className="text-gray-400 mt-1 text-sm">Real-time copilot status overview across blockers, failures, and actions.</p>
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

      {statusQ.isLoading && <div className="py-16 text-center text-brand-300">Loading status…</div>}
      {statusQ.isError && (
        <div className="rounded-lg border border-red-900/50 p-6 text-red-300 flex gap-2">
          <AlertTriangle size={20} />
          {errMessage(statusQ.error)}
        </div>
      )}

      {st && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-gray-800 bg-gray-950/40 p-4">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
                <Flame size={14} /> Urgency
              </div>
              <span className={`inline-flex items-center rounded-md border px-3 py-1 text-sm font-bold capitalize ${urgencyColor(st.urgency)}`}>
                {st.urgency}
              </span>
            </div>
            <div className="rounded-xl border border-gray-800 bg-gray-950/40 p-4">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
                <Ban size={14} /> Blocked
              </div>
              <p className="text-3xl font-bold text-red-300 tabular-nums">{st.blocked_count}</p>
            </div>
            <div className="rounded-xl border border-gray-800 bg-gray-950/40 p-4">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
                <ShieldAlert size={14} /> Failed
              </div>
              <p className="text-3xl font-bold text-orange-300 tabular-nums">{st.failed_count}</p>
            </div>
            <div className="rounded-xl border border-gray-800 bg-gray-950/40 p-4">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
                <Activity size={14} /> Pending Actions
              </div>
              <p className="text-3xl font-bold text-brand-300 tabular-nums">{st.pending_actions_count}</p>
            </div>
            <div className="rounded-xl border border-gray-800 bg-gray-950/40 p-4">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
                <Key size={14} /> Missing Credentials
              </div>
              <p className="text-3xl font-bold text-amber-300 tabular-nums">{st.missing_credentials_count}</p>
            </div>
            <div className="rounded-xl border border-gray-800 bg-gray-950/40 p-4">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
                <Server size={14} /> Providers
              </div>
              <p className="text-3xl font-bold text-white tabular-nums">
                {st.live_providers_count}
                <span className="text-lg text-gray-500 font-normal"> / {st.total_providers_count}</span>
              </p>
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <div className="rounded-xl border border-gray-800 bg-gray-950/40 p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-3">Top Blockers</h3>
              {st.top_blockers?.length ? (
                <ul className="space-y-2">
                  {st.top_blockers.map((b, i) => (
                    <li key={i} className="text-sm text-gray-300 border-l-2 border-red-500/50 pl-3">
                      <p className="font-medium text-white">{b.title}</p>
                      <p className="text-xs text-gray-500">{b.source}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-gray-500">No blockers</p>
              )}
            </div>
            <div className="rounded-xl border border-gray-800 bg-gray-950/40 p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-3">Top Failures</h3>
              {st.top_failures?.length ? (
                <ul className="space-y-2">
                  {st.top_failures.map((f, i) => (
                    <li key={i} className="text-sm text-gray-300 border-l-2 border-orange-500/50 pl-3">
                      <p className="font-medium text-white">{f.title}</p>
                      <p className="text-xs text-gray-500">{f.source}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-gray-500">No failures</p>
              )}
            </div>
            <div className="rounded-xl border border-gray-800 bg-gray-950/40 p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-3">Top Pending Actions</h3>
              {st.top_pending_actions?.length ? (
                <ul className="space-y-2">
                  {st.top_pending_actions.map((a, i) => (
                    <li key={i} className="text-sm text-gray-300 border-l-2 border-brand-500/50 pl-3">
                      <p className="font-medium text-white">{a.title}</p>
                      <p className="text-xs text-gray-500">{a.source}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-gray-500">No pending actions</p>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
