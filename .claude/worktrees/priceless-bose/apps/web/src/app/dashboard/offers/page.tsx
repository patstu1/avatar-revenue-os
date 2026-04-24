'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi, offersApi } from '@/lib/api';
import { DollarSign, Plus, ShoppingBag, Trash2, TrendingUp } from 'lucide-react';

const MONETIZATION_METHODS = [
  'affiliate',
  'adsense',
  'sponsor',
  'product',
  'course',
  'membership',
  'consulting',
  'lead_gen',
] as const;

const PAYOUT_TYPES = ['cpa', 'cpl', 'cps', 'rev_share', 'cpm', 'flat', 'direct'] as const;

type Brand = { id: string; name: string };

type OfferRow = {
  id: string;
  brand_id: string;
  name: string;
  description?: string | null;
  monetization_method: string;
  offer_url?: string | null;
  payout_amount: number;
  payout_type?: string;
  epc: number;
  conversion_rate: number;
  average_order_value?: number;
  is_active: boolean;
  priority: number;
  created_at: string;
};

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Number(n) || 0);

/** Stored as fraction (e.g. 0.038); display as percent */
const formatConversion = (rate: number) => `${((Number(rate) || 0) * 100).toFixed(2)}%`;

function formatMethod(method: string) {
  return method.replace(/_/g, ' ');
}

const initialForm = {
  name: '',
  description: '',
  monetization_method: 'affiliate' as (typeof MONETIZATION_METHODS)[number],
  offer_url: '',
  payout_amount: '' as string | number,
  payout_type: 'cpa' as (typeof PAYOUT_TYPES)[number],
  epc: '' as string | number,
  conversion_rate_pct: '' as string | number,
  average_order_value: '' as string | number,
  priority: 0 as string | number,
};

export default function OffersPage() {
  const queryClient = useQueryClient();
  const [brandId, setBrandId] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState(initialForm);
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);

  const {
    data: brands,
    isLoading: brandsLoading,
    isError: brandsError,
    error: brandsErr,
  } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) {
      setBrandId(brands[0].id);
    }
  }, [brands, brandId]);

  const {
    data: offers,
    isLoading: offersLoading,
    isError: offersError,
    error: offersErr,
  } = useQuery({
    queryKey: ['offers', brandId],
    queryFn: () => offersApi.list(brandId).then((r) => r.data as OfferRow[]),
    enabled: Boolean(brandId),
  });

  const createMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => offersApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['offers', brandId] });
      setShowCreate(false);
      setForm(initialForm);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => offersApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['offers', brandId] });
      setDeleteTarget(null);
    },
  });

  const selectedBrand = useMemo(() => brands?.find((b) => b.id === brandId), [brands, brandId]);

  const onCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!brandId) return;
    const crPct = parseFloat(String(form.conversion_rate_pct));
    const conversion_rate = Number.isFinite(crPct) ? crPct / 100 : 0;
    createMutation.mutate({
      brand_id: brandId,
      name: form.name.trim(),
      description: form.description.trim() || null,
      monetization_method: form.monetization_method,
      offer_url: form.offer_url.trim() || null,
      payout_amount: parseFloat(String(form.payout_amount)) || 0,
      payout_type: form.payout_type,
      epc: parseFloat(String(form.epc)) || 0,
      conversion_rate,
      average_order_value: parseFloat(String(form.average_order_value)) || 0,
      priority: parseInt(String(form.priority), 10) || 0,
    });
  };

  const errMessage = (e: unknown) =>
    e && typeof e === 'object' && 'response' in e
      ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? 'Request failed')
      : 'Something went wrong';

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <ShoppingBag className="text-brand-500" size={28} />
            Offer Catalog
          </h1>
          <p className="text-gray-400 mt-1">
            Manage monetization offers, affiliate programs, and sponsor deals
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowCreate((v) => !v)}
          className="btn-primary flex items-center justify-center gap-2 shrink-0"
          disabled={!brandId}
        >
          <Plus size={16} /> New offer
        </button>
      </div>

      <div className="card">
        <label className="block text-sm font-medium text-gray-300 mb-2">Brand</label>
        {brandsLoading ? (
          <div className="h-10 bg-gray-800 rounded-lg animate-pulse border border-gray-700" />
        ) : brandsError ? (
          <p className="text-red-400 text-sm">{errMessage(brandsErr)}</p>
        ) : !brands?.length ? (
          <p className="text-gray-500 text-sm">No brands available. Create a brand first.</p>
        ) : (
          <select
            className="input-field w-full max-w-md"
            aria-label="Select brand"
            title="Select brand"
            value={brandId}
            onChange={(e) => setBrandId(e.target.value)}
          >
            {brands.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {showCreate && brandId && (
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">Create offer</h3>
          <form onSubmit={onCreateSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <input
              required
              placeholder="Name"
              className="input-field"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <select
              className="input-field"
              aria-label="Monetization method"
              title="Monetization method"
              value={form.monetization_method}
              onChange={(e) =>
                setForm({ ...form, monetization_method: e.target.value as (typeof MONETIZATION_METHODS)[number] })
              }
            >
              {MONETIZATION_METHODS.map((m) => (
                <option key={m} value={m}>
                  {formatMethod(m)}
                </option>
              ))}
            </select>
            <input
              placeholder="Offer URL"
              className="input-field md:col-span-2"
              type="url"
              value={form.offer_url}
              onChange={(e) => setForm({ ...form, offer_url: e.target.value })}
            />
            <textarea
              placeholder="Description"
              className="input-field md:col-span-2"
              rows={3}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
            <input
              placeholder="Payout amount (USD)"
              className="input-field"
              type="number"
              step="0.01"
              min="0"
              value={form.payout_amount}
              onChange={(e) => setForm({ ...form, payout_amount: e.target.value })}
            />
            <select
              className="input-field"
              aria-label="Payout type"
              title="Payout type"
              value={form.payout_type}
              onChange={(e) =>
                setForm({ ...form, payout_type: e.target.value as (typeof PAYOUT_TYPES)[number] })
              }
            >
              {PAYOUT_TYPES.map((p) => (
                <option key={p} value={p}>
                  {p.replace('_', ' ').toUpperCase()}
                </option>
              ))}
            </select>
            <input
              placeholder="EPC"
              className="input-field"
              type="number"
              step="0.01"
              min="0"
              value={form.epc}
              onChange={(e) => setForm({ ...form, epc: e.target.value })}
            />
            <input
              placeholder="Conversion rate (%)"
              className="input-field"
              type="number"
              step="0.01"
              min="0"
              value={form.conversion_rate_pct}
              onChange={(e) => setForm({ ...form, conversion_rate_pct: e.target.value })}
            />
            <input
              placeholder="Average order value"
              className="input-field"
              type="number"
              step="0.01"
              min="0"
              value={form.average_order_value}
              onChange={(e) => setForm({ ...form, average_order_value: e.target.value })}
            />
            <input
              placeholder="Priority"
              className="input-field"
              type="number"
              step="1"
              value={form.priority}
              onChange={(e) => setForm({ ...form, priority: e.target.value })}
            />
            {createMutation.isError && (
              <p className="text-red-400 text-sm md:col-span-2">{errMessage(createMutation.error)}</p>
            )}
            <div className="md:col-span-2 flex gap-3">
              <button type="submit" className="btn-primary" disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Creating…' : 'Create offer'}
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  setShowCreate(false);
                  setForm(initialForm);
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {brandId && offersLoading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="card animate-pulse h-24 bg-gray-900 border-gray-800" />
          ))}
        </div>
      )}

      {brandId && offersError && (
        <div className="card border-red-900/50">
          <p className="text-red-400">Failed to load offers: {errMessage(offersErr)}</p>
        </div>
      )}

      {brandId && !offersLoading && !offersError && offers?.length === 0 && (
        <div className="card text-center py-12">
          <DollarSign size={48} className="mx-auto text-gray-600 mb-4" />
          <p className="text-gray-400">
            No offers for {selectedBrand?.name ?? 'this brand'} yet. Create one to get started.
          </p>
        </div>
      )}

      {brandId && !offersLoading && !offersError && offers && offers.length > 0 && (
        <div className="space-y-3">
          {offers.map((offer) => (
            <div key={offer.id} className="card-hover flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0 flex-1 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-lg font-semibold text-white truncate">{offer.name}</h3>
                  <span
                    className={offer.is_active ? 'badge-green' : 'badge-yellow'}
                    title={offer.is_active ? 'Active' : 'Inactive'}
                  >
                    {offer.is_active ? 'Active' : 'Inactive'}
                  </span>
                  <span className="badge-blue">P{offer.priority ?? 0}</span>
                </div>
                {offer.description ? (
                  <p className="text-sm text-gray-400 line-clamp-2">{offer.description}</p>
                ) : (
                  <p className="text-sm text-gray-600 italic">No description</p>
                )}
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-400">
                  <span className="capitalize">{formatMethod(offer.monetization_method)}</span>
                  <span className="flex items-center gap-1 text-emerald-300/90">
                    <DollarSign size={14} />
                    {money(offer.payout_amount)}
                  </span>
                  <span className="flex items-center gap-1">
                    <TrendingUp size={14} className="text-brand-400" />
                    EPC {money(offer.epc)}
                  </span>
                  <span>Conv. {formatConversion(offer.conversion_rate)}</span>
                </div>
              </div>
              <button
                type="button"
                className="btn-secondary text-red-300 border-red-900/40 hover:bg-red-950/30 shrink-0 self-start flex items-center gap-2"
                onClick={() => setDeleteTarget({ id: offer.id, name: offer.name })}
                aria-label={`Delete ${offer.name}`}
              >
                <Trash2 size={16} />
                Delete
              </button>
            </div>
          ))}
        </div>
      )}

      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
          <div className="card max-w-md w-full border-gray-700 shadow-xl">
            <h3 className="text-lg font-semibold text-white mb-2">Delete offer?</h3>
            <p className="text-gray-400 text-sm mb-6">
              This cannot be undone. Remove <span className="text-gray-200 font-medium">{deleteTarget.name}</span>?
            </p>
            {deleteMutation.isError && (
              <p className="text-red-400 text-sm mb-4">{errMessage(deleteMutation.error)}</p>
            )}
            <div className="flex gap-3 justify-end">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  setDeleteTarget(null);
                  deleteMutation.reset();
                }}
                disabled={deleteMutation.isPending}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-primary bg-red-700 hover:bg-red-800"
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate(deleteTarget.id)}
              >
                {deleteMutation.isPending ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
