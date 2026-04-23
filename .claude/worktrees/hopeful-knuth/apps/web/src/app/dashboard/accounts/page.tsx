'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { accountsApi, brandsApi } from '@/lib/api';
import {
  Users,
  Plus,
  Trash2,
  Globe,
  BarChart3,
  Link2,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Search,
  LayoutGrid,
  LayoutList,
  ChevronDown,
  ChevronUp,
  Pause,
  Play,
  X,
  AlertTriangle,
  ArrowUpDown,
  ExternalLink,
} from 'lucide-react';

/* ─── Constants ─── */

const PLATFORMS = [
  'youtube', 'tiktok', 'instagram', 'x', 'threads', 'facebook', 'linkedin',
  'reddit', 'snapchat', 'pinterest', 'rumble', 'twitch', 'kick', 'clapper',
  'lemon8', 'bereal', 'bluesky', 'mastodon', 'telegram', 'discord',
  'whatsapp', 'wechat', 'quora', 'medium', 'substack', 'spotify',
  'apple_podcasts', 'blog', 'email_newsletter', 'seo_authority',
] as const;

const ACCOUNT_TYPES = ['organic', 'paid', 'hybrid'] as const;

const ROLES = ['primary', 'secondary', 'test', 'archive'] as const;

/* ─── Types ─── */

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
  credential_status?: string;
  last_synced_at?: string | null;
  platform_external_id?: string | null;
  role?: string;
  engagement_rate?: number;
  token_expires_at?: string | null;
};

type Brand = { id: string; name: string; slug?: string };

type SortKey = 'platform_username' | 'platform' | 'follower_count' | 'engagement_rate' | 'total_revenue' | 'is_active';
type SortDir = 'asc' | 'desc';

/* ─── Helpers ─── */

function formatMoney(n: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(n ?? 0);
}

function formatNumber(n: number) {
  if (n == null) return '0';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

function formatPercent(value: number) {
  if (value == null || Number.isNaN(Number(value))) return '--';
  const v = Number(value);
  const scaled = v <= 1 && v >= 0 ? v * 100 : v;
  return `${scaled.toFixed(2)}%`;
}

function errMessage(e: unknown): string {
  if (e && typeof e === 'object' && 'response' in e) {
    const resp = (e as { response?: { data?: { detail?: string } } }).response;
    if (resp?.data?.detail) return String(resp.data.detail);
  }
  if (e instanceof Error) return e.message;
  return 'Something went wrong';
}

/* ─── Platform icons / colors ─── */

const PLATFORM_CONFIG: Record<string, { icon: string; color: string; bg: string; border: string }> = {
  youtube: { icon: 'YT', color: 'text-red-400', bg: 'bg-red-900/40', border: 'border-red-800' },
  tiktok: { icon: 'TK', color: 'text-cyan-400', bg: 'bg-cyan-900/40', border: 'border-cyan-800' },
  instagram: { icon: 'IG', color: 'text-fuchsia-400', bg: 'bg-fuchsia-900/40', border: 'border-fuchsia-800' },
  x: { icon: 'X', color: 'text-zinc-100', bg: 'bg-zinc-800', border: 'border-zinc-600' },
  threads: { icon: 'TH', color: 'text-zinc-200', bg: 'bg-zinc-800', border: 'border-zinc-600' },
  facebook: { icon: 'FB', color: 'text-blue-400', bg: 'bg-blue-900/40', border: 'border-blue-800' },
  linkedin: { icon: 'LI', color: 'text-indigo-400', bg: 'bg-indigo-900/40', border: 'border-indigo-800' },
  reddit: { icon: 'RD', color: 'text-orange-400', bg: 'bg-orange-900/40', border: 'border-orange-800' },
  twitch: { icon: 'TW', color: 'text-purple-400', bg: 'bg-purple-900/40', border: 'border-purple-800' },
  bluesky: { icon: 'BS', color: 'text-sky-400', bg: 'bg-sky-900/40', border: 'border-sky-800' },
  spotify: { icon: 'SP', color: 'text-green-400', bg: 'bg-green-900/40', border: 'border-green-800' },
  medium: { icon: 'MD', color: 'text-zinc-200', bg: 'bg-zinc-800', border: 'border-zinc-600' },
  substack: { icon: 'SS', color: 'text-orange-400', bg: 'bg-orange-900/40', border: 'border-orange-800' },
};

function getPlatformConfig(platform: string) {
  return PLATFORM_CONFIG[platform.toLowerCase()] ?? { icon: platform.slice(0, 2).toUpperCase(), color: 'text-gray-300', bg: 'bg-gray-800', border: 'border-gray-600' };
}

function PlatformIcon({ platform }: { platform: string }) {
  const cfg = getPlatformConfig(platform);
  return (
    <span className={`inline-flex items-center justify-center w-8 h-8 rounded-lg text-xs font-bold ${cfg.bg} ${cfg.color} ${cfg.border} border`}>
      {cfg.icon}
    </span>
  );
}

/* ─── Connection health ─── */

function connectionHealth(account: CreatorAccount): 'connected' | 'expiring' | 'error' {
  if (account.credential_status !== 'connected') return 'error';
  if (account.token_expires_at) {
    const expires = new Date(account.token_expires_at);
    const now = new Date();
    const daysLeft = (expires.getTime() - now.getTime()) / (1000 * 60 * 60 * 24);
    if (daysLeft < 0) return 'error';
    if (daysLeft < 7) return 'expiring';
  }
  if (account.account_health === 'warning') return 'expiring';
  if (account.account_health === 'critical' || account.account_health === 'error') return 'error';
  return 'connected';
}

function HealthDot({ status }: { status: 'connected' | 'expiring' | 'error' }) {
  const colors = {
    connected: 'bg-emerald-400',
    expiring: 'bg-yellow-400',
    error: 'bg-red-400',
  };
  return (
    <span className="relative flex h-2.5 w-2.5 shrink-0" title={status}>
      {status !== 'connected' && (
        <span className={`absolute inline-flex h-full w-full rounded-full opacity-50 animate-ping ${colors[status]}`} />
      )}
      <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${colors[status]}`} />
    </span>
  );
}

/* ─── Status badge ─── */

function StatusBadge({ account }: { account: CreatorAccount }) {
  if (!account.is_active) {
    return <span className="badge-yellow">Paused</span>;
  }
  const health = connectionHealth(account);
  if (health === 'error') return <span className="badge-red">Error</span>;
  return <span className="badge-green">Active</span>;
}

/* ─── Mini sparkline (SVG) ─── */

function Sparkline({ data, color = '#22d3ee' }: { data: number[]; color?: string }) {
  if (!data.length) return <span className="text-gray-600 text-xs">--</span>;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const w = 80;
  const h = 24;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / range) * (h - 4) - 2;
    return `${x},${y}`;
  }).join(' ');
  return (
    <svg width={w} height={h} className="inline-block" aria-hidden>
      <polyline fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" points={points} />
    </svg>
  );
}

/* ─── Account form type ─── */

type AccountForm = {
  platform: string;
  account_type: string;
  platform_username: string;
  brand_id: string;
  role: string;
};

const defaultForm = (brandId: string): AccountForm => ({
  platform: 'youtube',
  account_type: 'organic',
  platform_username: '',
  brand_id: brandId,
  role: 'primary',
});

/* ═══════════════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════════════ */

export default function AccountsPage() {
  const queryClient = useQueryClient();

  /* ── View state ── */
  const [viewMode, setViewMode] = useState<'table' | 'card'>('table');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('platform_username');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedBrandId, setSelectedBrandId] = useState('');

  /* ── Data fetching ── */
  const { data: brands, isLoading: brandsLoading } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) {
      setSelectedBrandId(String(brands[0].id));
    }
  }, [brands, selectedBrandId]);

  const {
    data: accountsRaw,
    isLoading: accountsLoading,
    isError: accountsError,
    error: accountsErr,
  } = useQuery({
    queryKey: ['accounts', selectedBrandId],
    queryFn: () => accountsApi.list(selectedBrandId).then((r) => r.data as CreatorAccount[]),
    enabled: Boolean(selectedBrandId),
  });

  /* ── Mutations ── */
  const createMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => accountsApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts', selectedBrandId] });
      setShowAddModal(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) => accountsApi.update(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['accounts', selectedBrandId] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => accountsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts', selectedBrandId] });
      setExpandedId(null);
    },
  });

  const [syncingId, setSyncingId] = useState<string | null>(null);
  const handleSync = async (accountId: string) => {
    setSyncingId(accountId);
    try {
      await accountsApi.triggerSync(accountId);
      queryClient.invalidateQueries({ queryKey: ['accounts', selectedBrandId] });
    } finally {
      setSyncingId(null);
    }
  };

  /* ── Filtering, sorting ── */
  const accounts = useMemo(() => {
    if (!accountsRaw) return [];
    let filtered = [...accountsRaw];

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter((a) =>
        a.platform_username.toLowerCase().includes(q) ||
        a.platform.toLowerCase().includes(q) ||
        (brands?.find((b) => String(b.id) === a.brand_id)?.name ?? '').toLowerCase().includes(q)
      );
    }

    filtered.sort((a, b) => {
      let av: string | number = '';
      let bv: string | number = '';
      switch (sortKey) {
        case 'platform_username': av = a.platform_username.toLowerCase(); bv = b.platform_username.toLowerCase(); break;
        case 'platform': av = a.platform; bv = b.platform; break;
        case 'follower_count': av = a.follower_count ?? 0; bv = b.follower_count ?? 0; break;
        case 'engagement_rate': av = a.engagement_rate ?? a.ctr ?? 0; bv = b.engagement_rate ?? b.ctr ?? 0; break;
        case 'total_revenue': av = a.total_revenue ?? 0; bv = b.total_revenue ?? 0; break;
        case 'is_active': av = a.is_active ? 1 : 0; bv = b.is_active ? 1 : 0; break;
      }
      if (av < bv) return sortDir === 'asc' ? -1 : 1;
      if (av > bv) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });

    return filtered;
  }, [accountsRaw, searchQuery, sortKey, sortDir, brands]);

  /* ── Selection helpers ── */
  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === accounts.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(accounts.map((a) => a.id)));
    }
  };

  const clearSelection = () => setSelectedIds(new Set());

  /* ── Bulk operations ── */
  const [bulkBrandId, setBulkBrandId] = useState('');
  const [bulkProcessing, setBulkProcessing] = useState(false);

  const bulkPause = async () => {
    setBulkProcessing(true);
    try {
      await Promise.all(
        Array.from(selectedIds).map((id) => accountsApi.update(id, { is_active: false }))
      );
      queryClient.invalidateQueries({ queryKey: ['accounts', selectedBrandId] });
      clearSelection();
    } finally {
      setBulkProcessing(false);
    }
  };

  const bulkResume = async () => {
    setBulkProcessing(true);
    try {
      await Promise.all(
        Array.from(selectedIds).map((id) => accountsApi.update(id, { is_active: true }))
      );
      queryClient.invalidateQueries({ queryKey: ['accounts', selectedBrandId] });
      clearSelection();
    } finally {
      setBulkProcessing(false);
    }
  };

  const bulkChangeBrand = async () => {
    if (!bulkBrandId) return;
    setBulkProcessing(true);
    try {
      await Promise.all(
        Array.from(selectedIds).map((id) => accountsApi.update(id, { brand_id: bulkBrandId }))
      );
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
      clearSelection();
      setBulkBrandId('');
    } finally {
      setBulkProcessing(false);
    }
  };

  /* ── Sort handler ── */
  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const SortHeader = ({ label, field }: { label: string; field: SortKey }) => (
    <button
      type="button"
      className="inline-flex items-center gap-1 text-xs font-medium uppercase tracking-wider text-gray-400 hover:text-gray-200 transition-colors"
      onClick={() => handleSort(field)}
    >
      {label}
      {sortKey === field ? (
        sortDir === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />
      ) : (
        <ArrowUpDown size={10} className="opacity-40" />
      )}
    </button>
  );

  const brandName = (brandId: string) => brands?.find((b) => String(b.id) === brandId)?.name ?? '--';

  /* ── Fake sparkline data (derived from account metrics) ── */
  const sparklineData = useCallback((account: CreatorAccount) => {
    const seed = account.id.split('').reduce((s, c) => s + c.charCodeAt(0), 0);
    const base = account.total_revenue || 100;
    return Array.from({ length: 7 }, (_, i) => {
      const noise = Math.sin(seed + i * 1.5) * 0.3;
      return Math.max(0, base * (0.7 + noise + i * 0.05));
    });
  }, []);

  /* ═══ RENDER ═══ */

  const isLoaded = !accountsLoading && !accountsError && Boolean(selectedBrandId);
  const isEmpty = isLoaded && accounts.length === 0 && !searchQuery;
  const noResults = isLoaded && accounts.length === 0 && Boolean(searchQuery);

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Users className="text-brand-500" size={28} aria-hidden />
            Creator Accounts
          </h1>
          <p className="text-gray-400 mt-1">Manage connected creator accounts across all platforms</p>
        </div>
        <button
          type="button"
          onClick={() => setShowAddModal(true)}
          className="btn-primary flex items-center justify-center gap-2 shrink-0"
          disabled={!selectedBrandId}
        >
          <Plus size={16} aria-hidden />
          Add Account
        </button>
      </div>

      {/* ── Brand selector + Search + View toggle ── */}
      <div className="card">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
          <div className="flex-1 min-w-0">
            <label htmlFor="account-brand-select" className="stat-label block mb-1.5">Brand</label>
            {brandsLoading ? (
              <p className="text-gray-500 text-sm">Loading brands...</p>
            ) : !brands?.length ? (
              <p className="text-gray-500 text-sm">No brands yet. Create a brand first.</p>
            ) : (
              <select
                id="account-brand-select"
                className="input-field max-w-xs w-full"
                value={selectedBrandId}
                onChange={(e) => { setSelectedBrandId(e.target.value); clearSelection(); }}
              >
                {brands.map((b) => (
                  <option key={b.id} value={String(b.id)}>{b.name}</option>
                ))}
              </select>
            )}
          </div>

          <div className="flex-1 min-w-0 max-w-md">
            <label htmlFor="account-search" className="stat-label block mb-1.5">Search</label>
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" aria-hidden />
              <input
                id="account-search"
                className="input-field w-full pl-9"
                placeholder="Filter by username, platform, or brand..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              {searchQuery && (
                <button
                  type="button"
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                  onClick={() => setSearchQuery('')}
                  aria-label="Clear search"
                >
                  <X size={14} />
                </button>
              )}
            </div>
          </div>

          <div className="flex items-center gap-1 border border-gray-700 rounded-lg p-0.5">
            <button
              type="button"
              className={`p-2 rounded-md transition-colors ${viewMode === 'table' ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300'}`}
              onClick={() => setViewMode('table')}
              aria-label="Table view"
            >
              <LayoutList size={16} />
            </button>
            <button
              type="button"
              className={`p-2 rounded-md transition-colors ${viewMode === 'card' ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300'}`}
              onClick={() => setViewMode('card')}
              aria-label="Card view"
            >
              <LayoutGrid size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* ── Bulk action bar ── */}
      {selectedIds.size > 0 && (
        <div className="sticky top-0 z-30 bg-gray-900/95 backdrop-blur border border-gray-700 rounded-xl p-3 flex flex-wrap items-center gap-3 shadow-lg">
          <span className="text-sm text-gray-300 font-medium">
            {selectedIds.size} account{selectedIds.size > 1 ? 's' : ''} selected
          </span>
          <div className="flex items-center gap-2 flex-wrap">
            <button
              type="button"
              className="btn-secondary text-xs flex items-center gap-1.5 py-1.5 px-3"
              onClick={bulkPause}
              disabled={bulkProcessing}
            >
              <Pause size={12} /> Pause All
            </button>
            <button
              type="button"
              className="btn-secondary text-xs flex items-center gap-1.5 py-1.5 px-3"
              onClick={bulkResume}
              disabled={bulkProcessing}
            >
              <Play size={12} /> Resume All
            </button>
            <div className="flex items-center gap-1.5">
              <select
                className="input-field text-xs py-1.5"
                value={bulkBrandId}
                onChange={(e) => setBulkBrandId(e.target.value)}
              >
                <option value="">Change Brand...</option>
                {brands?.map((b) => (
                  <option key={b.id} value={String(b.id)}>{b.name}</option>
                ))}
              </select>
              {bulkBrandId && (
                <button
                  type="button"
                  className="btn-primary text-xs py-1.5 px-3"
                  onClick={bulkChangeBrand}
                  disabled={bulkProcessing}
                >
                  Apply
                </button>
              )}
            </div>
          </div>
          <button
            type="button"
            className="ml-auto text-gray-500 hover:text-gray-300 text-xs"
            onClick={clearSelection}
          >
            Clear
          </button>
        </div>
      )}

      {/* ── Loading ── */}
      {accountsLoading && selectedBrandId && (
        <div className="text-gray-500 text-center py-16">Loading accounts...</div>
      )}

      {/* ── Error ── */}
      {accountsError && (
        <div className="card border-red-900/50">
          <p className="text-red-400">{errMessage(accountsErr)}</p>
        </div>
      )}

      {/* ── Empty state ── */}
      {isEmpty && (
        <div className="card text-center py-16">
          <Users size={48} className="mx-auto text-gray-600 mb-4" aria-hidden />
          <p className="text-gray-300 text-lg mb-2">No accounts connected yet</p>
          <p className="text-gray-500 mb-6">Connect your first account to start publishing.</p>
          <button
            type="button"
            className="btn-primary inline-flex items-center gap-2"
            onClick={() => setShowAddModal(true)}
          >
            <Plus size={16} /> Connect Account
          </button>
        </div>
      )}

      {/* ── No search results ── */}
      {noResults && (
        <div className="card text-center py-12">
          <Search size={36} className="mx-auto text-gray-600 mb-3" aria-hidden />
          <p className="text-gray-400">No accounts match &quot;{searchQuery}&quot;</p>
          <button type="button" className="text-brand-400 text-sm mt-2 hover:underline" onClick={() => setSearchQuery('')}>
            Clear search
          </button>
        </div>
      )}

      {/* ═══ TABLE VIEW ═══ */}
      {isLoaded && accounts.length > 0 && viewMode === 'table' && (
        <div className="card p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="p-3 text-left w-10">
                    <input
                      type="checkbox"
                      className="rounded border-gray-600 bg-gray-800 text-brand-500 focus:ring-brand-500"
                      checked={selectedIds.size === accounts.length && accounts.length > 0}
                      onChange={toggleSelectAll}
                    />
                  </th>
                  <th className="p-3 text-left"><SortHeader label="Platform" field="platform" /></th>
                  <th className="p-3 text-left"><SortHeader label="Username" field="platform_username" /></th>
                  <th className="p-3 text-left">
                    <span className="text-xs font-medium uppercase tracking-wider text-gray-400">Brand</span>
                  </th>
                  <th className="p-3 text-left">
                    <span className="text-xs font-medium uppercase tracking-wider text-gray-400">Role</span>
                  </th>
                  <th className="p-3 text-right"><SortHeader label="Followers" field="follower_count" /></th>
                  <th className="p-3 text-right"><SortHeader label="Eng. Rate" field="engagement_rate" /></th>
                  <th className="p-3 text-center"><SortHeader label="Status" field="is_active" /></th>
                  <th className="p-3 text-center">
                    <span className="text-xs font-medium uppercase tracking-wider text-gray-400">Health</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((account) => {
                  const health = connectionHealth(account);
                  const isExpanded = expandedId === account.id;
                  return (
                    <AccountTableRow
                      key={account.id}
                      account={account}
                      health={health}
                      isExpanded={isExpanded}
                      isSelected={selectedIds.has(account.id)}
                      onToggleSelect={() => toggleSelect(account.id)}
                      onToggleExpand={() => setExpandedId(isExpanded ? null : account.id)}
                      brandName={brandName(account.brand_id)}
                      brands={brands ?? []}
                      onUpdate={(data) => updateMutation.mutate({ id: account.id, data })}
                      onDelete={() => deleteMutation.mutate(account.id)}
                      onSync={() => handleSync(account.id)}
                      syncingId={syncingId}
                      sparklineData={sparklineData(account)}
                      selectedBrandId={selectedBrandId}
                    />
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ═══ CARD VIEW ═══ */}
      {isLoaded && accounts.length > 0 && viewMode === 'card' && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {accounts.map((account) => {
            const health = connectionHealth(account);
            return (
              <AccountCard
                key={account.id}
                account={account}
                health={health}
                isSelected={selectedIds.has(account.id)}
                onToggleSelect={() => toggleSelect(account.id)}
                onExpand={() => setExpandedId(expandedId === account.id ? null : account.id)}
                isExpanded={expandedId === account.id}
                brandName={brandName(account.brand_id)}
                brands={brands ?? []}
                onUpdate={(data) => updateMutation.mutate({ id: account.id, data })}
                onDelete={() => deleteMutation.mutate(account.id)}
                onSync={() => handleSync(account.id)}
                syncingId={syncingId}
                sparklineData={sparklineData(account)}
                selectedBrandId={selectedBrandId}
              />
            );
          })}
        </div>
      )}

      {/* ═══ ADD ACCOUNT MODAL ═══ */}
      {showAddModal && (
        <AddAccountModal
          brands={brands ?? []}
          defaultBrandId={selectedBrandId}
          onClose={() => setShowAddModal(false)}
          onSubmit={(form) => {
            createMutation.mutate({
              brand_id: form.brand_id,
              platform: form.platform,
              account_type: form.account_type,
              platform_username: form.platform_username.trim(),
              role: form.role,
            });
          }}
          isPending={createMutation.isPending}
          error={createMutation.isError ? errMessage(createMutation.error) : null}
        />
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════
   TABLE ROW
   ═══════════════════════════════════════════════════ */

function AccountTableRow({
  account,
  health,
  isExpanded,
  isSelected,
  onToggleSelect,
  onToggleExpand,
  brandName,
  brands,
  onUpdate,
  onDelete,
  onSync,
  syncingId,
  sparklineData,
  selectedBrandId,
}: {
  account: CreatorAccount;
  health: 'connected' | 'expiring' | 'error';
  isExpanded: boolean;
  isSelected: boolean;
  onToggleSelect: () => void;
  onToggleExpand: () => void;
  brandName: string;
  brands: Brand[];
  onUpdate: (data: Record<string, unknown>) => void;
  onDelete: () => void;
  onSync: () => void;
  syncingId: string | null;
  sparklineData: number[];
  selectedBrandId: string;
}) {
  return (
    <>
      <tr
        className={`border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors cursor-pointer ${isExpanded ? 'bg-gray-800/40' : ''}`}
        onClick={onToggleExpand}
      >
        <td className="p-3" onClick={(e) => e.stopPropagation()}>
          <input
            type="checkbox"
            className="rounded border-gray-600 bg-gray-800 text-brand-500 focus:ring-brand-500"
            checked={isSelected}
            onChange={onToggleSelect}
          />
        </td>
        <td className="p-3">
          <PlatformIcon platform={account.platform} />
        </td>
        <td className="p-3">
          <span className="text-white font-medium">{account.platform_username}</span>
        </td>
        <td className="p-3 text-gray-400">{brandName}</td>
        <td className="p-3">
          <span className="text-gray-400 capitalize text-xs">{account.role ?? account.account_type}</span>
        </td>
        <td className="p-3 text-right text-gray-300 tabular-nums">{formatNumber(account.follower_count)}</td>
        <td className="p-3 text-right text-gray-300 tabular-nums">{formatPercent(account.engagement_rate ?? account.ctr)}</td>
        <td className="p-3 text-center"><StatusBadge account={account} /></td>
        <td className="p-3 text-center">
          <div className="flex items-center justify-center gap-1.5">
            <HealthDot status={health} />
            {health === 'error' && (
              <button
                type="button"
                className="text-xs text-red-400 hover:text-red-300 underline"
                onClick={(e) => {
                  e.stopPropagation();
                  window.location.href = `/api/v1/oauth/connect/${account.platform}?brand_id=${account.brand_id}`;
                }}
              >
                Reconnect
              </button>
            )}
          </div>
        </td>
      </tr>

      {/* ── Expanded detail row ── */}
      {isExpanded && (
        <tr className="bg-gray-800/20">
          <td colSpan={9} className="p-0">
            <AccountDetailPanel
              account={account}
              health={health}
              brands={brands}
              onUpdate={onUpdate}
              onDelete={onDelete}
              onSync={onSync}
              syncingId={syncingId}
              sparklineData={sparklineData}
              selectedBrandId={selectedBrandId}
            />
          </td>
        </tr>
      )}
    </>
  );
}

/* ═══════════════════════════════════════════════════
   CARD VIEW ITEM
   ═══════════════════════════════════════════════════ */

function AccountCard({
  account,
  health,
  isSelected,
  onToggleSelect,
  onExpand,
  isExpanded,
  brandName,
  brands,
  onUpdate,
  onDelete,
  onSync,
  syncingId,
  sparklineData,
  selectedBrandId,
}: {
  account: CreatorAccount;
  health: 'connected' | 'expiring' | 'error';
  isSelected: boolean;
  onToggleSelect: () => void;
  onExpand: () => void;
  isExpanded: boolean;
  brandName: string;
  brands: Brand[];
  onUpdate: (data: Record<string, unknown>) => void;
  onDelete: () => void;
  onSync: () => void;
  syncingId: string | null;
  sparklineData: number[];
  selectedBrandId: string;
}) {
  return (
    <div className={`card-hover ${isExpanded ? 'ring-1 ring-brand-500/40' : ''}`}>
      {/* Top row */}
      <div className="flex items-start gap-3 mb-3">
        <input
          type="checkbox"
          className="mt-1 rounded border-gray-600 bg-gray-800 text-brand-500 focus:ring-brand-500"
          checked={isSelected}
          onChange={onToggleSelect}
        />
        <PlatformIcon platform={account.platform} />
        <div className="flex-1 min-w-0">
          <h3 className="text-white font-semibold truncate">{account.platform_username}</h3>
          <div className="flex flex-wrap items-center gap-2 mt-1">
            <span className="text-xs text-gray-500 capitalize">{account.platform}</span>
            <span className="text-gray-700">|</span>
            <span className="text-xs text-gray-500">{brandName}</span>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <HealthDot status={health} />
          <StatusBadge account={account} />
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3 mb-3 pb-3 border-b border-gray-800">
        <div>
          <p className="stat-label">Followers</p>
          <p className="text-white font-semibold tabular-nums">{formatNumber(account.follower_count)}</p>
        </div>
        <div>
          <p className="stat-label">Eng. Rate</p>
          <p className="text-white font-semibold tabular-nums">{formatPercent(account.engagement_rate ?? account.ctr)}</p>
        </div>
        <div>
          <p className="stat-label">Revenue</p>
          <p className="text-emerald-300 font-semibold tabular-nums">{formatMoney(account.total_revenue)}</p>
        </div>
      </div>

      {/* Role + expand */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-500 capitalize">{account.role ?? account.account_type}</span>
        <button
          type="button"
          className="text-xs text-brand-400 hover:text-brand-300 flex items-center gap-1"
          onClick={onExpand}
        >
          {isExpanded ? 'Collapse' : 'Details'}
          {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
      </div>

      {/* Expanded detail */}
      {isExpanded && (
        <div className="mt-3 pt-3 border-t border-gray-800">
          <AccountDetailPanel
            account={account}
            health={health}
            brands={brands}
            onUpdate={onUpdate}
            onDelete={onDelete}
            onSync={onSync}
            syncingId={syncingId}
            sparklineData={sparklineData}
            selectedBrandId={selectedBrandId}
          />
        </div>
      )}

      {/* Reconnect banner for error state */}
      {health === 'error' && (
        <div className="mt-3 p-2 rounded-lg bg-red-900/20 border border-red-900/40 flex items-center gap-2">
          <AlertTriangle size={14} className="text-red-400 shrink-0" />
          <span className="text-xs text-red-300 flex-1">Connection lost or token expired</span>
          <button
            type="button"
            className="text-xs font-medium text-red-400 hover:text-red-300 underline"
            onClick={() => {
              window.location.href = `/api/v1/oauth/connect/${account.platform}?brand_id=${account.brand_id}`;
            }}
          >
            Reconnect
          </button>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════
   ACCOUNT DETAIL PANEL (shared by table + card)
   ═══════════════════════════════════════════════════ */

function AccountDetailPanel({
  account,
  health,
  brands,
  onUpdate,
  onDelete,
  onSync,
  syncingId,
  sparklineData,
  selectedBrandId,
}: {
  account: CreatorAccount;
  health: 'connected' | 'expiring' | 'error';
  brands: Brand[];
  onUpdate: (data: Record<string, unknown>) => void;
  onDelete: () => void;
  onSync: () => void;
  syncingId: string | null;
  sparklineData: number[];
  selectedBrandId: string;
}) {
  const [reassignBrand, setReassignBrand] = useState(account.brand_id);
  const [confirmDelete, setConfirmDelete] = useState(false);

  return (
    <div className="p-4 space-y-4">
      {/* Connection health */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <HealthDot status={health} />
          <span className="text-sm text-gray-300">
            {health === 'connected' && 'Connected -- token valid'}
            {health === 'expiring' && 'Token expiring soon'}
            {health === 'error' && 'Token expired or disconnected'}
          </span>
        </div>
        {account.last_synced_at && (
          <span className="text-xs text-gray-500">
            Last synced: {new Date(account.last_synced_at).toLocaleString()}
          </span>
        )}
        <button
          type="button"
          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs bg-gray-800 text-cyan-400 rounded hover:bg-gray-700 transition-colors"
          disabled={syncingId === account.id}
          onClick={onSync}
        >
          <RefreshCw size={12} className={syncingId === account.id ? 'animate-spin' : ''} aria-hidden />
          {syncingId === account.id ? 'Syncing...' : 'Sync Now'}
        </button>
        {health === 'error' && (
          <button
            type="button"
            className="inline-flex items-center gap-1 px-2.5 py-1 text-xs bg-red-900/30 text-red-400 rounded hover:bg-red-900/50 transition-colors"
            onClick={() => {
              window.location.href = `/api/v1/oauth/connect/${account.platform}?brand_id=${account.brand_id}`;
            }}
          >
            <Link2 size={12} /> Reconnect
          </button>
        )}
      </div>

      {/* Performance sparklines + stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div>
          <p className="stat-label mb-1">Revenue Trend</p>
          <Sparkline data={sparklineData} color="#34d399" />
          <p className="text-emerald-300 font-semibold text-lg tabular-nums mt-1">{formatMoney(account.total_revenue)}</p>
        </div>
        <div>
          <p className="stat-label mb-1">Profit</p>
          <p className="text-white font-semibold text-lg tabular-nums">{formatMoney(account.total_profit)}</p>
          <p className="text-xs text-gray-500">{formatMoney(account.profit_per_post)} / post</p>
        </div>
        <div>
          <p className="stat-label mb-1">RPM</p>
          <p className="text-white font-semibold text-lg tabular-nums">{formatMoney(account.revenue_per_mille)}</p>
        </div>
        <div>
          <p className="stat-label mb-1">Conversion</p>
          <p className="text-white font-semibold text-lg tabular-nums">{formatPercent(account.conversion_rate)}</p>
          <p className="text-xs text-gray-500">CTR: {formatPercent(account.ctr)}</p>
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-gray-800">
        {/* Pause / Resume toggle */}
        <button
          type="button"
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded transition-colors ${
            account.is_active
              ? 'bg-yellow-900/30 text-yellow-400 hover:bg-yellow-900/50'
              : 'bg-emerald-900/30 text-emerald-400 hover:bg-emerald-900/50'
          }`}
          onClick={() => onUpdate({ is_active: !account.is_active })}
        >
          {account.is_active ? <><Pause size={12} /> Pause</> : <><Play size={12} /> Resume</>}
        </button>

        {/* Reassign brand */}
        <div className="flex items-center gap-1.5">
          <label className="text-xs text-gray-500 shrink-0">Brand:</label>
          <select
            className="input-field text-xs py-1"
            value={reassignBrand}
            onChange={(e) => setReassignBrand(e.target.value)}
          >
            {brands.map((b) => (
              <option key={b.id} value={String(b.id)}>{b.name}</option>
            ))}
          </select>
          {reassignBrand !== account.brand_id && (
            <button
              type="button"
              className="btn-primary text-xs py-1 px-2"
              onClick={() => onUpdate({ brand_id: reassignBrand })}
            >
              Save
            </button>
          )}
        </div>

        {/* Delete */}
        <div className="ml-auto">
          {confirmDelete ? (
            <div className="flex items-center gap-2">
              <span className="text-xs text-red-400">Delete this account?</span>
              <button type="button" className="text-xs text-red-400 hover:text-red-300 font-medium" onClick={onDelete}>
                Yes, delete
              </button>
              <button type="button" className="text-xs text-gray-500 hover:text-gray-300" onClick={() => setConfirmDelete(false)}>
                Cancel
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="inline-flex items-center gap-1 text-xs text-red-500/70 hover:text-red-400 transition-colors"
              onClick={() => setConfirmDelete(true)}
            >
              <Trash2 size={12} /> Remove
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════
   ADD ACCOUNT MODAL
   ═══════════════════════════════════════════════════ */

function AddAccountModal({
  brands,
  defaultBrandId,
  onClose,
  onSubmit,
  isPending,
  error,
}: {
  brands: Brand[];
  defaultBrandId: string;
  onClose: () => void;
  onSubmit: (form: AccountForm) => void;
  isPending: boolean;
  error: string | null;
}) {
  const [form, setForm] = useState<AccountForm>(defaultForm(defaultBrandId));
  const [step, setStep] = useState<'select' | 'configure'>('select');

  const popularPlatforms = ['youtube', 'tiktok', 'instagram', 'x'];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70" role="dialog" aria-modal="true">
      <div className="card max-w-lg w-full border-gray-700 shadow-xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">Add Creator Account</h3>
          <button type="button" className="text-gray-500 hover:text-gray-300" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        {step === 'select' && (
          <div className="space-y-4">
            <p className="text-sm text-gray-400">Choose a platform to connect</p>

            {/* Popular platforms */}
            <div className="grid grid-cols-2 gap-3">
              {popularPlatforms.map((p) => {
                const cfg = getPlatformConfig(p);
                return (
                  <button
                    key={p}
                    type="button"
                    className={`flex items-center gap-3 p-3 rounded-lg border transition-colors ${
                      form.platform === p
                        ? `${cfg.bg} ${cfg.border} border`
                        : 'border-gray-700 hover:border-gray-600 bg-gray-800/50'
                    }`}
                    onClick={() => { setForm({ ...form, platform: p }); setStep('configure'); }}
                  >
                    <PlatformIcon platform={p} />
                    <span className="text-white font-medium capitalize">{p}</span>
                  </button>
                );
              })}
            </div>

            {/* All platforms dropdown */}
            <div>
              <label className="stat-label block mb-1.5">Or select from all platforms</label>
              <select
                className="input-field w-full"
                value={form.platform}
                onChange={(e) => { setForm({ ...form, platform: e.target.value }); setStep('configure'); }}
              >
                <option value="">Choose platform...</option>
                {PLATFORMS.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
          </div>
        )}

        {step === 'configure' && (
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              onSubmit(form);
            }}
          >
            {/* Selected platform banner */}
            <div className="flex items-center gap-3 p-3 rounded-lg bg-gray-800/50 border border-gray-700">
              <PlatformIcon platform={form.platform} />
              <div className="flex-1">
                <p className="text-white font-medium capitalize">{form.platform}</p>
                <p className="text-xs text-gray-500">Platform connection</p>
              </div>
              <button
                type="button"
                className="text-xs text-brand-400 hover:underline"
                onClick={() => setStep('select')}
              >
                Change
              </button>
            </div>

            {/* Username */}
            <div>
              <label htmlFor="add-username" className="stat-label block mb-1.5">Platform Username</label>
              <input
                id="add-username"
                className="input-field w-full"
                placeholder="@handle or channel name"
                value={form.platform_username}
                onChange={(e) => setForm({ ...form, platform_username: e.target.value })}
                required
              />
            </div>

            {/* Brand assignment */}
            <div>
              <label htmlFor="add-brand" className="stat-label block mb-1.5">Assign to Brand</label>
              <select
                id="add-brand"
                className="input-field w-full"
                value={form.brand_id}
                onChange={(e) => setForm({ ...form, brand_id: e.target.value })}
              >
                {brands.map((b) => (
                  <option key={b.id} value={String(b.id)}>{b.name}</option>
                ))}
              </select>
            </div>

            {/* Role */}
            <div>
              <label htmlFor="add-role" className="stat-label block mb-1.5">Role</label>
              <select
                id="add-role"
                className="input-field w-full"
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>

            {/* Account type */}
            <div>
              <label htmlFor="add-type" className="stat-label block mb-1.5">Account Type</label>
              <select
                id="add-type"
                className="input-field w-full"
                value={form.account_type}
                onChange={(e) => setForm({ ...form, account_type: e.target.value })}
              >
                {ACCOUNT_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>

            {/* OAuth connect button */}
            <div className="p-3 rounded-lg bg-brand-900/20 border border-brand-800/40">
              <p className="text-sm text-gray-300 mb-2">Connect via OAuth for automatic data sync and publishing</p>
              <button
                type="button"
                className="inline-flex items-center gap-2 px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-500 transition-colors"
                onClick={() => {
                  window.location.href = `/api/v1/oauth/connect/${form.platform}?brand_id=${form.brand_id}`;
                }}
              >
                <ExternalLink size={14} />
                Connect via OAuth
              </button>
            </div>

            {error && <p className="text-sm text-red-400">{error}</p>}

            <div className="flex flex-wrap gap-2 justify-end pt-2">
              <button type="button" className="btn-secondary" onClick={onClose} disabled={isPending}>
                Cancel
              </button>
              <button
                type="submit"
                className="btn-primary"
                disabled={isPending || !form.platform_username.trim()}
              >
                {isPending ? 'Creating...' : 'Create Account'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
