'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { accountsApi, brandsApi } from '@/lib/api';
import { Users, Plus, Trash2, Globe, BarChart3 } from 'lucide-react';

const PLATFORMS = [
  'youtube',
  'tiktok',
  'instagram',
  'twitter',
  'facebook',
  'linkedin',
  'pinterest',
  'snapchat',
  'threads',
] as const;

const ACCOUNT_TYPES = ['organic', 'paid', 'hybrid'] as const;

type CreatorAccount = {
  id: string;
  brand_id: string;
  platform: string;
  account_type: string;
  platform_username: string;
  account_health: string;
  total_revenue: number;
  total_profit: number;
  profit_per_post: number;
  revenue_per_mille: number;
  ctr: number;
  conversion_rate: number;
  follower_count: number;
  is_active: boolean;
  created_at: string;
  niche_focus?: string | null;
  sub_niche_focus?: string | null;
  language?: string | null;
  geography?: string | null;
  monetization_focus?: string | null;
  posting_capacity_per_day?: number | null;
};

function formatMoney(n: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(
    n ?? 0
  );
}

function formatPercent(value: number) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  const v = Number(value);
  const scaled = v <= 1 && v >= 0 ? v * 100 : v;
  return `${scaled.toFixed(2)}%`;
}

function platformBadgeClass(platform: string) {
  const p = platform.toLowerCase();
  const base = 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border capitalize';
  const map: Record<string, string> = {
    youtube: 'bg-red-900/40 text-red-200 border-red-800',
    tiktok: 'bg-cyan-900/40 text-cyan-200 border-cyan-800',
    instagram: 'bg-fuchsia-900/40 text-fuchsia-200 border-fuchsia-800',
    twitter: 'bg-sky-900/40 text-sky-200 border-sky-800',
    facebook: 'bg-blue-900/40 text-blue-200 border-blue-800',
    linkedin: 'bg-indigo-900/40 text-indigo-200 border-indigo-800',
    pinterest: 'bg-rose-900/40 text-rose-200 border-rose-800',
    snapchat: 'bg-yellow-900/40 text-yellow-200 border-yellow-800',
    threads: 'bg-zinc-800 text-zinc-200 border-zinc-600',
  };
  return `${base} ${map[p] ?? 'bg-gray-800 text-gray-300 border-gray-600'}`;
}

function healthBadgeClass(health: string) {
  const h = health.toLowerCase();
  if (h === 'healthy') return 'badge-green';
  if (h === 'warning') return 'badge-yellow';
  return 'badge-red';
}

type AccountForm = {
  platform: (typeof PLATFORMS)[number];
  account_type: (typeof ACCOUNT_TYPES)[number];
  platform_username: string;
  niche_focus: string;
  sub_niche_focus: string;
  language: string;
  geography: string;
  monetization_focus: string;
  posting_capacity_per_day: number;
};

const defaultForm = (): AccountForm => ({
  platform: 'youtube',
  account_type: 'organic',
  platform_username: '',
  niche_focus: '',
  sub_niche_focus: '',
  language: 'en',
  geography: '',
  monetization_focus: '',
  posting_capacity_per_day: 1,
});

export default function AccountsPage() {
  const queryClient = useQueryClient();
  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<AccountForm>(defaultForm);
  const [deleteTarget, setDeleteTarget] = useState<CreatorAccount | null>(null);

  const {
    data: brands,
    isLoading: brandsLoading,
    isError: brandsError,
    error: brandsErr,
  } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) {
      setSelectedBrandId(String(brands[0].id));
    }
  }, [brands, selectedBrandId]);

  const {
    data: accounts,
    isLoading: accountsLoading,
    isError: accountsError,
    error: accountsErr,
  } = useQuery({
    queryKey: ['accounts', selectedBrandId],
    queryFn: () => accountsApi.list(selectedBrandId).then((r) => r.data as CreatorAccount[]),
    enabled: Boolean(selectedBrandId),
  });

  const createMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => accountsApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts', selectedBrandId] });
      setForm(defaultForm());
      setShowCreate(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => accountsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts', selectedBrandId] });
      setDeleteTarget(null);
    },
  });

  const selectedBrand = useMemo(
    () => brands?.find((b: { id: string }) => String(b.id) === selectedBrandId),
    [brands, selectedBrandId]
  );

  const errMessage = (e: unknown) =>
    e && typeof e === 'object' && 'response' in e && (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
      ? String((e as { response: { data: { detail: string } } }).response.data.detail)
      : e instanceof Error
        ? e.message
        : 'Something went wrong';

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Users className="text-brand-500" size={28} aria-hidden />
            Creator Accounts
          </h1>
          <p className="text-gray-400 mt-1">Portfolio of creator accounts and performance by brand</p>
        </div>
        <button
          type="button"
          onClick={() => setShowCreate((s) => !s)}
          className="btn-primary flex items-center justify-center gap-2 shrink-0"
          disabled={!selectedBrandId}
        >
          <Plus size={16} aria-hidden />
          New Account
        </button>
      </div>

      <div className="card">
        <label htmlFor="account-brand-select" className="stat-label block mb-2">
          Brand
        </label>
        {brandsLoading ? (
          <p className="text-gray-500 text-sm">Loading brands…</p>
        ) : brandsError ? (
          <p className="text-red-400 text-sm">{errMessage(brandsErr)}</p>
        ) : !brands?.length ? (
          <p className="text-gray-500 text-sm">No brands yet. Create a brand first.</p>
        ) : (
          <select
            id="account-brand-select"
            className="input-field max-w-md w-full"
            value={selectedBrandId}
            onChange={(e) => setSelectedBrandId(e.target.value)}
          >
            {brands.map((b: { id: string; name: string }) => (
              <option key={b.id} value={String(b.id)}>
                {b.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {showCreate && selectedBrandId && (
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Plus size={18} className="text-brand-500" aria-hidden />
            Create creator account
          </h3>
          <form
            className="grid grid-cols-1 md:grid-cols-2 gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              createMutation.mutate({
                brand_id: selectedBrandId,
                platform: form.platform,
                account_type: form.account_type,
                platform_username: form.platform_username.trim(),
                niche_focus: form.niche_focus.trim() || null,
                sub_niche_focus: form.sub_niche_focus.trim() || null,
                language: form.language.trim() || 'en',
                geography: form.geography.trim() || null,
                monetization_focus: form.monetization_focus.trim() || null,
                posting_capacity_per_day: Math.max(1, Number(form.posting_capacity_per_day) || 1),
              });
            }}
          >
            <input type="hidden" name="brand_id" value={selectedBrandId} readOnly aria-hidden="true" />
            <div className="md:col-span-2 text-sm text-gray-500">
              Brand: <span className="text-gray-300">{selectedBrand?.name ?? selectedBrandId}</span>
            </div>
            <div>
              <label htmlFor="new-account-platform" className="stat-label block mb-1.5">
                Platform
              </label>
              <select
                id="new-account-platform"
                className="input-field w-full"
                value={form.platform}
                onChange={(e) => setForm({ ...form, platform: e.target.value as AccountForm['platform'] })}
              >
                {PLATFORMS.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="new-account-type" className="stat-label block mb-1.5">
                Account type
              </label>
              <select
                id="new-account-type"
                className="input-field w-full"
                value={form.account_type}
                onChange={(e) => setForm({ ...form, account_type: e.target.value as AccountForm['account_type'] })}
              >
                {ACCOUNT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div className="md:col-span-2">
              <label htmlFor="new-account-username" className="stat-label block mb-1.5">
                Platform username
              </label>
              <input
                id="new-account-username"
                className="input-field w-full"
                placeholder="@handle or channel name"
                value={form.platform_username}
                onChange={(e) => setForm({ ...form, platform_username: e.target.value })}
                required
              />
            </div>
            <div>
              <label htmlFor="new-account-niche" className="stat-label block mb-1.5">
                Niche focus
              </label>
              <input
                id="new-account-niche"
                className="input-field w-full"
                placeholder="Primary niche"
                value={form.niche_focus}
                onChange={(e) => setForm({ ...form, niche_focus: e.target.value })}
              />
            </div>
            <div>
              <label htmlFor="new-account-subniche" className="stat-label block mb-1.5">
                Sub-niche
              </label>
              <input
                id="new-account-subniche"
                className="input-field w-full"
                placeholder="Sub-niche"
                value={form.sub_niche_focus}
                onChange={(e) => setForm({ ...form, sub_niche_focus: e.target.value })}
              />
            </div>
            <div>
              <label htmlFor="new-account-language" className="stat-label block mb-1.5">
                Language
              </label>
              <input
                id="new-account-language"
                className="input-field w-full"
                placeholder="en"
                value={form.language}
                onChange={(e) => setForm({ ...form, language: e.target.value })}
              />
            </div>
            <div>
              <label htmlFor="new-account-geography" className="stat-label block mb-1.5">
                Geography
              </label>
              <input
                id="new-account-geography"
                className="input-field w-full"
                placeholder="Region or country"
                value={form.geography}
                onChange={(e) => setForm({ ...form, geography: e.target.value })}
              />
            </div>
            <div>
              <label htmlFor="new-account-monetization" className="stat-label block mb-1.5">
                Monetization focus
              </label>
              <input
                id="new-account-monetization"
                className="input-field w-full"
                placeholder="e.g. affiliate, ads"
                value={form.monetization_focus}
                onChange={(e) => setForm({ ...form, monetization_focus: e.target.value })}
              />
            </div>
            <div>
              <label htmlFor="new-account-capacity" className="stat-label block mb-1.5">
                Posting capacity / day
              </label>
              <input
                id="new-account-capacity"
                type="number"
                min={1}
                className="input-field w-full"
                placeholder="1"
                value={form.posting_capacity_per_day}
                onChange={(e) => setForm({ ...form, posting_capacity_per_day: Number(e.target.value) })}
              />
            </div>
            {createMutation.isError && (
              <p className="md:col-span-2 text-sm text-red-400">{errMessage(createMutation.error)}</p>
            )}
            <div className="md:col-span-2 flex flex-wrap gap-2">
              <button type="submit" className="btn-primary" disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Creating…' : 'Create account'}
              </button>
              <button type="button" className="btn-secondary" onClick={() => setShowCreate(false)}>
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {selectedBrandId && accountsLoading && (
        <div className="text-gray-500 text-center py-16">Loading accounts…</div>
      )}

      {selectedBrandId && accountsError && (
        <div className="card border-red-900/50">
          <p className="text-red-400">{errMessage(accountsErr)}</p>
        </div>
      )}

      {selectedBrandId && !accountsLoading && !accountsError && accounts?.length === 0 && (
        <div className="card text-center py-14">
          <BarChart3 size={48} className="mx-auto text-gray-600 mb-4" aria-hidden />
          <p className="text-gray-400 mb-1">No creator accounts for this brand yet.</p>
          <p className="text-sm text-gray-500">Add an account to track metrics and publishing capacity.</p>
        </div>
      )}

      {selectedBrandId && !accountsLoading && !accountsError && accounts && accounts.length > 0 && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {accounts.map((account) => (
            <div key={account.id} className="card-hover">
              <div className="flex items-start justify-between gap-3 mb-4">
                <div>
                  <h3 className="text-lg font-semibold text-white">{account.platform_username}</h3>
                  <div className="flex flex-wrap gap-2 mt-2">
                    <span className={platformBadgeClass(account.platform)}>{account.platform}</span>
                    <span className="badge-blue capitalize">{account.account_type}</span>
                    <span className={healthBadgeClass(account.account_health)}>{account.account_health}</span>
                  </div>
                </div>
                <button
                  type="button"
                  className="btn-secondary p-2 text-red-400 hover:text-red-300 border-red-900/40 shrink-0"
                  aria-label={`Delete ${account.platform_username}`}
                  onClick={() => setDeleteTarget(account)}
                >
                  <Trash2 size={18} aria-hidden />
                </button>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4 pb-4 border-b border-gray-800">
                <div>
                  <p className="stat-label">Revenue</p>
                  <p className="stat-value text-xl text-white tabular-nums">{formatMoney(account.total_revenue)}</p>
                </div>
                <div>
                  <p className="stat-label">Profit</p>
                  <p className="stat-value text-xl text-emerald-300 tabular-nums">{formatMoney(account.total_profit)}</p>
                </div>
                <div>
                  <p className="stat-label">Profit / post</p>
                  <p className="stat-value text-xl text-white tabular-nums">{formatMoney(account.profit_per_post)}</p>
                </div>
                <div>
                  <p className="stat-label">RPM</p>
                  <p className="stat-value text-xl text-white tabular-nums">{formatMoney(account.revenue_per_mille)}</p>
                </div>
                <div>
                  <p className="stat-label">CTR</p>
                  <p className="stat-value text-xl text-white tabular-nums">{formatPercent(account.ctr)}</p>
                </div>
                <div>
                  <p className="stat-label">Conversion</p>
                  <p className="stat-value text-xl text-white tabular-nums">{formatPercent(account.conversion_rate)}</p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-3 text-sm text-gray-400 mb-3">
                <span className="flex items-center gap-1.5">
                  <Users size={14} className="text-gray-500 shrink-0" aria-hidden />
                  <span className="text-gray-300 tabular-nums">{account.follower_count.toLocaleString()}</span>
                  <span>followers</span>
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-sm">
                <div>
                  <p className="stat-label normal-case tracking-normal text-gray-500 mb-0.5">Niche</p>
                  <p className="text-gray-200">{account.niche_focus?.trim() || '—'}</p>
                </div>
                <div>
                  <p className="stat-label normal-case tracking-normal text-gray-500 mb-0.5">Geography</p>
                  <p className="text-gray-200 flex items-center gap-1">
                    <Globe size={14} className="text-gray-500 shrink-0" aria-hidden />
                    {account.geography?.trim() || '—'}
                  </p>
                </div>
                <div>
                  <p className="stat-label normal-case tracking-normal text-gray-500 mb-0.5">Language</p>
                  <p className="text-gray-200">{account.language?.trim() || '—'}</p>
                </div>
              </div>
              {(account.sub_niche_focus || account.monetization_focus) && (
                <p className="text-xs text-gray-500 mt-3">
                  {account.sub_niche_focus && <span>Sub-niche: {account.sub_niche_focus}. </span>}
                  {account.monetization_focus && <span>Monetization: {account.monetization_focus}.</span>}
                </p>
              )}
              <div className="mt-4 pt-3 border-t border-gray-800 text-xs text-gray-500">
                Added {new Date(account.created_at).toLocaleDateString()}
                {!account.is_active && <span className="ml-2 text-amber-500">Inactive</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70" role="dialog" aria-modal="true">
          <div className="card max-w-md w-full border-gray-700 shadow-xl">
            <h3 className="text-lg font-semibold text-white mb-2">Delete account?</h3>
            <p className="text-gray-400 text-sm mb-6">
              Remove <span className="text-white font-medium">{deleteTarget.platform_username}</span> on{' '}
              {deleteTarget.platform}. This cannot be undone.
            </p>
            {deleteMutation.isError && <p className="text-sm text-red-400 mb-4">{errMessage(deleteMutation.error)}</p>}
            <div className="flex flex-wrap gap-2 justify-end">
              <button type="button" className="btn-secondary" onClick={() => setDeleteTarget(null)} disabled={deleteMutation.isPending}>
                Cancel
              </button>
              <button
                type="button"
                className="btn-primary bg-red-700 hover:bg-red-600"
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
