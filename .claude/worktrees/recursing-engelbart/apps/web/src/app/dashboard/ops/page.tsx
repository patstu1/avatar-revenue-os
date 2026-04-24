'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { brandsApi, accountsApi, offersApi, apiFetch } from '@/lib/api';
import { controlLayerApi } from '@/lib/control-layer-api';
import { pipelineApi } from '@/lib/pipeline-api';
import {
  Activity, AlertTriangle, BarChart3, CheckCircle2, Clock,
  DollarSign, Layers, Loader2, Shield, Users, XCircle, Zap,
} from 'lucide-react';

/* ─── Types ─── */

type Brand = { id: string; name: string; niche?: string; sub_niche?: string };
type Account = { id: string; platform: string; platform_username: string; credential_status: string; is_active: boolean; follower_count: number };
type OfferRow = { id: string; name: string; monetization_method: string; is_active: boolean; payout_amount: number };
type OperatorAction = { id: string; title: string; description?: string; priority: string; category: string; status: string; created_at?: string };
type RevenueAssignment = { id: string; assignment_type: string; target_name: string | null; platform: string | null; is_active: boolean };

const TABS = ['overview', 'accounts', 'readiness', 'blockers', 'revenue', 'publishing'] as const;
type Tab = (typeof TABS)[number];

const TAB_LABELS: Record<Tab, string> = {
  overview: 'Overview',
  accounts: 'Accounts',
  readiness: 'Readiness',
  blockers: 'Blockers',
  revenue: 'Revenue Map',
  publishing: 'Publishing',
};

const PLATFORM_COLORS: Record<string, string> = {
  youtube: 'text-red-400', tiktok: 'text-cyan-400', instagram: 'text-fuchsia-400',
  x: 'text-zinc-100', facebook: 'text-blue-400', linkedin: 'text-indigo-400',
};

function statusDot(s: string) {
  const c = s === 'connected' ? 'bg-emerald-400' : s === 'expiring' ? 'bg-yellow-400' : 'bg-red-400';
  return <span className={`w-2 h-2 rounded-full inline-block ${c}`} />;
}

/* ─── Page ─── */

export default function OpsPage() {
  const [brandId, setBrandId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('overview');

  const { data: brands } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => {
      const d = r.data;
      return (Array.isArray(d) ? d : d?.items ?? []) as Brand[];
    }),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(brands[0].id);
  }, [brands, brandId]);

  const selectedBrand = brands?.find((b) => b.id === brandId);

  const { data: accounts } = useQuery({
    queryKey: ['ops-accounts', brandId],
    queryFn: () => accountsApi.list({ brand_id: brandId }).then((r) => {
      const d = r.data;
      return (Array.isArray(d) ? d : d?.items ?? []) as Account[];
    }),
    enabled: !!brandId,
  });

  const { data: offers } = useQuery({
    queryKey: ['ops-offers', brandId],
    queryFn: () => offersApi.list(brandId!).then((r) => (r.data ?? []) as OfferRow[]),
    enabled: !!brandId,
  });

  const { data: assignments } = useQuery({
    queryKey: ['ops-assignments', brandId],
    queryFn: () => apiFetch(`/api/v1/revenue-assignments/?brand_id=${brandId}`) as Promise<RevenueAssignment[]>,
    enabled: !!brandId,
  });

  const { data: actions } = useQuery({
    queryKey: ['ops-blockers', brandId],
    queryFn: () => controlLayerApi.actions({ category: 'blocker', limit: 50 }).then((r) => (r.data ?? []) as OperatorAction[]),
    enabled: !!brandId,
  });

  const { data: health } = useQuery({
    queryKey: ['ops-health'],
    queryFn: () => controlLayerApi.health().then((r) => r.data as Record<string, unknown>),
  });

  const acctList = accounts ?? [];
  const connectedAccounts = acctList.filter((a) => a.credential_status === 'connected');
  const activeOffers = (offers ?? []).filter((o) => o.is_active);
  const blockers = (actions ?? []).filter((a) => a.category === 'blocker' && a.status === 'pending');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-start gap-3">
          <Shield className="text-brand-400 shrink-0 mt-1" size={28} />
          <div>
            <h1 className="text-2xl font-bold text-white">Operator Command</h1>
            <p className="text-gray-400 mt-1">
              Cluster: <span className="text-white font-medium">{selectedBrand?.name ?? '—'}</span>
              {selectedBrand?.niche && <span className="text-gray-500"> / {selectedBrand.niche}</span>}
            </p>
          </div>
        </div>
        <select className="input-field min-w-[200px]" value={brandId ?? ''} onChange={(e) => setBrandId(e.target.value || null)}>
          {!brands?.length && <option value="">No clusters</option>}
          {brands?.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-800 pb-0">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-mono transition-colors border-b-2 -mb-px ${
              tab === t
                ? 'text-white border-brand-500'
                : 'text-gray-500 border-transparent hover:text-gray-300'
            }`}
          >
            {TAB_LABELS[t]}
            {t === 'blockers' && blockers.length > 0 && (
              <span className="ml-2 chip-red text-[10px]">{blockers.length}</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {tab === 'overview' && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="card">
              <p className="metric-label">Accounts</p>
              <p className="metric-value text-cyan-400">{acctList.length}</p>
              <p className="text-xs text-gray-500 font-mono mt-1">{connectedAccounts.length} connected</p>
            </div>
            <div className="card">
              <p className="metric-label">Offers</p>
              <p className="metric-value text-emerald-400">{activeOffers.length}</p>
              <p className="text-xs text-gray-500 font-mono mt-1">{(offers ?? []).length} total</p>
            </div>
            <div className="card">
              <p className="metric-label">Assignments</p>
              <p className="metric-value text-brand-400">{(assignments ?? []).filter((a) => a.is_active).length}</p>
            </div>
            <div className="card">
              <p className="metric-label">Blockers</p>
              <p className={`metric-value ${blockers.length > 0 ? 'text-red-400' : 'text-emerald-400'}`}>{blockers.length}</p>
            </div>
          </div>
        </div>
      )}

      {tab === 'accounts' && (
        <div className="card p-0 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="text-left px-4 py-3 metric-label">Platform</th>
                <th className="text-left px-4 py-3 metric-label">Username</th>
                <th className="text-left px-4 py-3 metric-label">Status</th>
                <th className="text-right px-4 py-3 metric-label">Followers</th>
              </tr>
            </thead>
            <tbody>
              {acctList.map((a) => (
                <tr key={a.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className={`px-4 py-3 text-sm font-mono font-medium ${PLATFORM_COLORS[a.platform] ?? 'text-gray-300'}`}>{a.platform}</td>
                  <td className="px-4 py-3 text-gray-200 text-sm">{a.platform_username}</td>
                  <td className="px-4 py-3 flex items-center gap-2">{statusDot(a.credential_status)} <span className="text-xs text-gray-400">{a.credential_status}</span></td>
                  <td className="px-4 py-3 text-right font-mono text-sm text-gray-300">{a.follower_count.toLocaleString()}</td>
                </tr>
              ))}
              {!acctList.length && <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-500">No accounts connected</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'readiness' && (
        <div className="space-y-3">
          {acctList.map((a) => {
            const connected = a.credential_status === 'connected';
            const active = a.is_active;
            const ready = connected && active;
            return (
              <div key={a.id} className={`card flex items-center justify-between ${!ready ? 'border-amber-900/30' : 'border-emerald-900/30'}`}>
                <div className="flex items-center gap-3">
                  <span className={`font-mono text-sm font-medium ${PLATFORM_COLORS[a.platform] ?? 'text-gray-300'}`}>{a.platform}</span>
                  <span className="text-gray-400 text-sm">{a.platform_username}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="flex items-center gap-1 text-xs">
                    {connected ? <CheckCircle2 size={14} className="text-emerald-400" /> : <XCircle size={14} className="text-red-400" />}
                    Auth
                  </span>
                  <span className="flex items-center gap-1 text-xs">
                    {active ? <CheckCircle2 size={14} className="text-emerald-400" /> : <XCircle size={14} className="text-red-400" />}
                    Active
                  </span>
                  <span className={`chip ${ready ? 'chip-green' : 'chip-amber'}`}>
                    {ready ? 'READY' : 'NOT READY'}
                  </span>
                </div>
              </div>
            );
          })}
          {!acctList.length && <div className="card text-center py-8 text-gray-500">No accounts to check</div>}
        </div>
      )}

      {tab === 'blockers' && (
        <div className="space-y-3">
          {blockers.length === 0 ? (
            <div className="card text-center py-8">
              <CheckCircle2 className="mx-auto text-emerald-400 mb-2" size={24} />
              <p className="text-gray-400">No active blockers</p>
            </div>
          ) : (
            blockers.map((b) => (
              <div key={b.id} className="card border-red-900/30">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-white font-medium text-sm">{b.title}</p>
                    {b.description && <p className="text-gray-500 text-xs mt-1">{b.description}</p>}
                  </div>
                  <span className={`chip ${b.priority === 'critical' ? 'chip-red' : b.priority === 'high' ? 'chip-amber' : 'chip'}`}>
                    {b.priority}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {tab === 'revenue' && (
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <DollarSign size={16} className="text-emerald-400" /> Active Offers
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {activeOffers.map((o) => (
              <div key={o.id} className="card">
                <p className="text-white text-sm font-medium">{o.name}</p>
                <div className="flex items-center gap-2 mt-2">
                  <span className="chip-cyan">{o.monetization_method}</span>
                  <span className="font-mono text-emerald-400 text-sm">${o.payout_amount}</span>
                </div>
              </div>
            ))}
            {!activeOffers.length && <p className="text-gray-500 text-sm col-span-3">No active offers</p>}
          </div>

          <h3 className="text-sm font-semibold text-white flex items-center gap-2 mt-6">
            <Layers size={16} className="text-brand-400" /> Revenue Assignments
          </h3>
          {(assignments ?? []).length === 0 ? (
            <p className="text-gray-500 text-sm">No revenue assignments configured</p>
          ) : (
            <div className="card p-0 overflow-hidden">
              <table className="w-full">
                <thead><tr className="border-b border-gray-800">
                  <th className="text-left px-4 py-3 metric-label">Type</th>
                  <th className="text-left px-4 py-3 metric-label">Target</th>
                  <th className="text-left px-4 py-3 metric-label">Platform</th>
                  <th className="text-left px-4 py-3 metric-label">Status</th>
                </tr></thead>
                <tbody>
                  {(assignments ?? []).map((a) => (
                    <tr key={a.id} className="border-b border-gray-800/50">
                      <td className="px-4 py-3"><span className="chip-cyan">{a.assignment_type}</span></td>
                      <td className="px-4 py-3 text-gray-200 text-sm">{a.target_name || '—'}</td>
                      <td className="px-4 py-3 text-gray-400 text-sm font-mono">{a.platform || 'all'}</td>
                      <td className="px-4 py-3">{a.is_active ? <span className="chip-green">Active</span> : <span className="chip">Inactive</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === 'publishing' && (
        <div className="card text-center py-12">
          <Activity className="mx-auto text-gray-600 mb-3" size={32} />
          <p className="text-gray-400">Publishing status coming from real-time pipeline</p>
          <p className="text-gray-600 text-sm mt-1">View content pipeline for detailed publish job tracking</p>
        </div>
      )}
    </div>
  );
}
