'use client';

import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi, offersApi, apiFetch } from '@/lib/api';
import {
  DollarSign, Link2, Loader2, Plus, Trash2, X,
  ToggleLeft, ToggleRight, ChevronDown,
} from 'lucide-react';

/* ─── Types ─── */

type Brand = { id: string; name: string };
type OfferRow = { id: string; name: string; monetization_method: string };

type RevenueAssignment = {
  id: string;
  brand_id: string;
  assignment_type: string;
  target_id: string;
  target_name: string | null;
  account_id: string | null;
  platform: string | null;
  priority: number;
  is_active: boolean;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

const ASSIGNMENT_TYPES = ['offer', 'affiliate', 'newsletter', 'b2b'] as const;

const TYPE_LABELS: Record<string, string> = {
  offer: 'Offer',
  affiliate: 'Affiliate',
  newsletter: 'Newsletter',
  b2b: 'B2B',
};

const TYPE_COLORS: Record<string, string> = {
  offer: 'chip-green',
  affiliate: 'chip-cyan',
  newsletter: 'chip-amber',
  b2b: 'chip-red',
};

/* ─── API ─── */

const raApi = {
  list: (brandId: string) => apiFetch(`/api/v1/revenue-assignments/?brand_id=${brandId}`),
  create: (data: Record<string, unknown>) =>
    apiFetch('/api/v1/revenue-assignments/', { method: 'POST', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } }),
  patch: (id: string, data: Record<string, unknown>) =>
    apiFetch(`/api/v1/revenue-assignments/${id}`, { method: 'PATCH', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } }),
  del: (id: string) =>
    apiFetch(`/api/v1/revenue-assignments/${id}`, { method: 'DELETE' }),
};

/* ─── Page ─── */

export default function RevenueAssignmentsPage() {
  const queryClient = useQueryClient();
  const [brandId, setBrandId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    assignment_type: 'offer' as string,
    target_id: '',
    target_name: '',
    platform: '',
    priority: 0,
  });

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

  const { data: assignments, isLoading } = useQuery({
    queryKey: ['revenue-assignments', brandId],
    queryFn: () => raApi.list(brandId!).then((r) => r as RevenueAssignment[]),
    enabled: !!brandId,
  });

  const { data: offers } = useQuery({
    queryKey: ['offers', brandId],
    queryFn: () => offersApi.list(brandId!).then((r) => (r.data ?? []) as OfferRow[]),
    enabled: !!brandId,
  });

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => raApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['revenue-assignments', brandId] });
      setShowForm(false);
      setForm({ assignment_type: 'offer', target_id: '', target_name: '', platform: '', priority: 0 });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      raApi.patch(id, { is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['revenue-assignments', brandId] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => raApi.del(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['revenue-assignments', brandId] }),
  });

  const handleCreate = () => {
    if (!brandId || !form.target_id) return;
    createMutation.mutate({
      brand_id: brandId,
      assignment_type: form.assignment_type,
      target_id: form.target_id,
      target_name: form.target_name || null,
      platform: form.platform || null,
      priority: form.priority,
    });
  };

  const selectedOffer = offers?.find((o) => o.id === form.target_id);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-start gap-3">
          <Link2 className="text-brand-400 shrink-0 mt-1" size={28} />
          <div>
            <h1 className="text-2xl font-bold text-white">Revenue Assignments</h1>
            <p className="text-gray-400 mt-1">Link offers, affiliates, and newsletters to brands</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <select
            className="input-field min-w-[180px]"
            value={brandId ?? ''}
            onChange={(e) => setBrandId(e.target.value || null)}
          >
            {!brands?.length && <option value="">No brands</option>}
            {(brands as Brand[] | undefined)?.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </select>
          <button className="btn-primary flex items-center gap-2" onClick={() => setShowForm(!showForm)}>
            {showForm ? <X size={16} /> : <Plus size={16} />}
            {showForm ? 'Cancel' : 'Add Assignment'}
          </button>
        </div>
      </div>

      {/* Create Form */}
      {showForm && (
        <div className="card border-brand-600/30">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            <div>
              <label className="metric-label mb-1 block">Type</label>
              <select
                className="input-field w-full"
                value={form.assignment_type}
                onChange={(e) => setForm((f) => ({ ...f, assignment_type: e.target.value, target_id: '', target_name: '' }))}
              >
                {ASSIGNMENT_TYPES.map((t) => (
                  <option key={t} value={t}>{TYPE_LABELS[t]}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="metric-label mb-1 block">Target</label>
              {form.assignment_type === 'offer' && offers?.length ? (
                <select
                  className="input-field w-full"
                  value={form.target_id}
                  onChange={(e) => {
                    const o = offers.find((x) => x.id === e.target.value);
                    setForm((f) => ({ ...f, target_id: e.target.value, target_name: o?.name ?? '' }));
                  }}
                >
                  <option value="">Select offer...</option>
                  {offers.map((o) => (
                    <option key={o.id} value={o.id}>{o.name}</option>
                  ))}
                </select>
              ) : (
                <input
                  className="input-field w-full"
                  placeholder="Target name"
                  value={form.target_name}
                  onChange={(e) => setForm((f) => ({ ...f, target_name: e.target.value, target_id: crypto.randomUUID() }))}
                />
              )}
            </div>
            <div>
              <label className="metric-label mb-1 block">Platform</label>
              <input
                className="input-field w-full"
                placeholder="All platforms"
                value={form.platform}
                onChange={(e) => setForm((f) => ({ ...f, platform: e.target.value }))}
              />
            </div>
            <div>
              <label className="metric-label mb-1 block">Priority</label>
              <input
                type="number"
                className="input-field w-full"
                value={form.priority}
                onChange={(e) => setForm((f) => ({ ...f, priority: parseInt(e.target.value) || 0 }))}
              />
            </div>
            <div className="flex items-end">
              <button
                className="btn-primary w-full flex items-center justify-center gap-2"
                onClick={handleCreate}
                disabled={createMutation.isPending || !form.target_id}
              >
                {createMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
                Create
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Assignments Table */}
      {isLoading ? (
        <div className="card flex items-center justify-center py-12">
          <Loader2 className="animate-spin text-gray-500" size={24} />
        </div>
      ) : !assignments?.length ? (
        <div className="card text-center py-12">
          <DollarSign className="mx-auto text-gray-600 mb-3" size={32} />
          <p className="text-gray-400">No revenue assignments yet</p>
          <p className="text-gray-600 text-sm mt-1">Link offers and monetization targets to this brand</p>
        </div>
      ) : (
        <div className="card p-0 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="text-left px-4 py-3 metric-label">Type</th>
                <th className="text-left px-4 py-3 metric-label">Target</th>
                <th className="text-left px-4 py-3 metric-label">Platform</th>
                <th className="text-left px-4 py-3 metric-label">Priority</th>
                <th className="text-left px-4 py-3 metric-label">Status</th>
                <th className="text-right px-4 py-3 metric-label">Actions</th>
              </tr>
            </thead>
            <tbody>
              {assignments.map((a) => (
                <tr key={a.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="px-4 py-3">
                    <span className={TYPE_COLORS[a.assignment_type] ?? 'chip'}>
                      {TYPE_LABELS[a.assignment_type] ?? a.assignment_type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-200 text-sm">
                    {a.target_name || a.target_id.slice(0, 8)}
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-sm font-mono">
                    {a.platform || 'all'}
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-sm font-mono">{a.priority}</td>
                  <td className="px-4 py-3">
                    <button
                      className="text-gray-400 hover:text-white transition-colors"
                      onClick={() => toggleMutation.mutate({ id: a.id, is_active: !a.is_active })}
                    >
                      {a.is_active
                        ? <ToggleRight size={20} className="text-emerald-400" />
                        : <ToggleLeft size={20} className="text-gray-600" />
                      }
                    </button>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      className="text-gray-500 hover:text-red-400 transition-colors"
                      onClick={() => deleteMutation.mutate(a.id)}
                    >
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
