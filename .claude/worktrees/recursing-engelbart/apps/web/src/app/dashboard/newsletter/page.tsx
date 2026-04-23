'use client';

import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi, apiFetch } from '@/lib/api';
import {
  Loader2, Mail, Plus, RefreshCw, Trash2, Users, X, BarChart3, MousePointerClick,
} from 'lucide-react';

/* ─── Types ─── */

type Brand = { id: string; name: string };

interface Connection {
  id: string;
  brand_id: string;
  provider: string;
  publication_id: string;
  publication_name: string | null;
  subscriber_count: number;
  last_synced_at: string | null;
  is_active: boolean;
  created_at: string;
}

interface Campaign {
  id: string;
  external_campaign_id: string;
  subject: string | null;
  status: string;
  sent_at: string | null;
  open_rate: number;
  click_rate: number;
  unsubscribe_count: number;
  revenue: number;
}

/* ─── API ─── */

const nlApi = {
  listConnections: (brandId: string) => apiFetch(`/api/v1/newsletter/connections?brand_id=${brandId}`),
  createConnection: (data: Record<string, unknown>) =>
    apiFetch('/api/v1/newsletter/connections', { method: 'POST', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } }),
  syncConnection: (id: string) =>
    apiFetch(`/api/v1/newsletter/connections/${id}/sync`, { method: 'POST' }),
  deleteConnection: (id: string) =>
    apiFetch(`/api/v1/newsletter/connections/${id}`, { method: 'DELETE' }),
  listCampaigns: (brandId: string) => apiFetch(`/api/v1/newsletter/campaigns?brand_id=${brandId}`),
};

function timeAgo(iso: string | null) {
  if (!iso) return 'Never';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

const pct = (n: number) => `${(n * 100).toFixed(1)}%`;

/* ─── Page ─── */

export default function NewsletterPage() {
  const queryClient = useQueryClient();
  const [brandId, setBrandId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ api_key: '', publication_id: '', publication_name: '' });

  const { data: brands } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : d?.items ?? [];
    }),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(brands[0].id);
  }, [brands, brandId]);

  const { data: connections, isLoading: connLoading } = useQuery({
    queryKey: ['newsletter-connections', brandId],
    queryFn: () => nlApi.listConnections(brandId!) as Promise<Connection[]>,
    enabled: !!brandId,
  });

  const { data: campaigns } = useQuery({
    queryKey: ['newsletter-campaigns', brandId],
    queryFn: () => nlApi.listCampaigns(brandId!) as Promise<Campaign[]>,
    enabled: !!brandId,
  });

  const createMut = useMutation({
    mutationFn: (data: Record<string, unknown>) => nlApi.createConnection(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['newsletter-connections', brandId] });
      setShowForm(false);
      setForm({ api_key: '', publication_id: '', publication_name: '' });
    },
  });

  const syncMut = useMutation({
    mutationFn: (id: string) => nlApi.syncConnection(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['newsletter-connections', brandId] });
      queryClient.invalidateQueries({ queryKey: ['newsletter-campaigns', brandId] });
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => nlApi.deleteConnection(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['newsletter-connections', brandId] }),
  });

  const handleCreate = () => {
    if (!brandId || !form.api_key || !form.publication_id) return;
    createMut.mutate({
      brand_id: brandId,
      api_key: form.api_key,
      publication_id: form.publication_id,
      publication_name: form.publication_name || null,
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-start gap-3">
          <Mail className="text-brand-400 shrink-0 mt-1" size={28} />
          <div>
            <h1 className="text-2xl font-bold text-white">Newsletter</h1>
            <p className="text-gray-400 mt-1">Beehiiv subscriber sync and campaign analytics</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <select className="input-field min-w-[180px]" value={brandId ?? ''} onChange={(e) => setBrandId(e.target.value || null)}>
            {!brands?.length && <option value="">No brands</option>}
            {(brands as Brand[] | undefined)?.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
          <button className="btn-primary flex items-center gap-2" onClick={() => setShowForm(!showForm)}>
            {showForm ? <X size={16} /> : <Plus size={16} />}
            {showForm ? 'Cancel' : 'Connect Beehiiv'}
          </button>
        </div>
      </div>

      {/* Connect Form */}
      {showForm && (
        <div className="card border-brand-600/30 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="metric-label mb-1 block">API Key</label>
              <input type="password" className="input-field w-full" placeholder="bh_..." value={form.api_key} onChange={(e) => setForm((f) => ({ ...f, api_key: e.target.value }))} />
            </div>
            <div>
              <label className="metric-label mb-1 block">Publication ID</label>
              <input className="input-field w-full" placeholder="pub_..." value={form.publication_id} onChange={(e) => setForm((f) => ({ ...f, publication_id: e.target.value }))} />
            </div>
            <div>
              <label className="metric-label mb-1 block">Name (optional)</label>
              <input className="input-field w-full" placeholder="My Newsletter" value={form.publication_name} onChange={(e) => setForm((f) => ({ ...f, publication_name: e.target.value }))} />
            </div>
          </div>
          <button className="btn-primary flex items-center gap-2" onClick={handleCreate} disabled={createMut.isPending || !form.api_key || !form.publication_id}>
            {createMut.isPending ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />} Connect
          </button>
          {createMut.isError && <p className="text-sm text-red-400">Failed to connect. Check your API key and publication ID.</p>}
        </div>
      )}

      {/* Connection Cards */}
      {connLoading ? (
        <div className="card flex items-center justify-center py-12"><Loader2 className="animate-spin text-gray-500" size={24} /></div>
      ) : !connections?.length ? (
        <div className="card text-center py-12">
          <Mail className="mx-auto text-gray-600 mb-3" size={32} />
          <p className="text-gray-400">No newsletter connections</p>
          <p className="text-gray-600 text-sm mt-1">Connect your Beehiiv publication to sync subscribers and campaigns</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {connections.map((c) => (
            <div key={c.id} className="card space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded bg-orange-900/40 flex items-center justify-center text-orange-400 font-mono font-bold text-sm">BH</div>
                  <div>
                    <p className="text-white font-medium">{c.publication_name || c.publication_id}</p>
                    <p className="text-gray-500 text-xs font-mono">{c.provider}</p>
                  </div>
                </div>
                <span className="chip-green">{c.is_active ? 'Connected' : 'Inactive'}</span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-gray-800/50 rounded p-3">
                  <p className="metric-label">Subscribers</p>
                  <p className="metric-value text-lg text-cyan-400">{c.subscriber_count.toLocaleString()}</p>
                </div>
                <div className="bg-gray-800/50 rounded p-3">
                  <p className="metric-label">Last Sync</p>
                  <p className="text-sm font-mono text-gray-300">{timeAgo(c.last_synced_at)}</p>
                </div>
              </div>
              <div className="flex gap-2">
                <button className="btn-secondary flex items-center gap-2 text-sm" onClick={() => syncMut.mutate(c.id)} disabled={syncMut.isPending}>
                  {syncMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />} Sync
                </button>
                <button className="text-gray-500 hover:text-red-400 p-2" onClick={() => deleteMut.mutate(c.id)}>
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Campaign Table */}
      {campaigns && campaigns.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
            <BarChart3 size={16} className="text-brand-400" /> Campaign Performance
          </h3>
          <div className="card p-0 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="text-left px-4 py-3 metric-label">Subject</th>
                  <th className="text-left px-4 py-3 metric-label">Status</th>
                  <th className="text-right px-4 py-3 metric-label">Open Rate</th>
                  <th className="text-right px-4 py-3 metric-label">Click Rate</th>
                  <th className="text-right px-4 py-3 metric-label">Unsubs</th>
                  <th className="text-left px-4 py-3 metric-label">Sent</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map((c) => (
                  <tr key={c.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="px-4 py-3 text-gray-200 text-sm max-w-[300px] truncate">{c.subject || '—'}</td>
                    <td className="px-4 py-3"><span className="chip-green">{c.status}</span></td>
                    <td className="px-4 py-3 text-right font-mono text-sm text-emerald-400">{pct(c.open_rate)}</td>
                    <td className="px-4 py-3 text-right font-mono text-sm text-cyan-400">{pct(c.click_rate)}</td>
                    <td className="px-4 py-3 text-right font-mono text-sm text-gray-400">{c.unsubscribe_count}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{timeAgo(c.sent_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
