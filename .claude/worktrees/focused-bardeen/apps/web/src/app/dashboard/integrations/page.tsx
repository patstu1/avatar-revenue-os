'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiFetch } from '@/lib/api';
import {
  Search,
  Cpu,
  Image,
  Video,
  Mic,
  Share2,
  BarChart3,
  TrendingUp,
  Mail,
  Inbox,
  DollarSign,
  Database,
  Eye,
  EyeOff,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  X,
  Loader2,
  ChevronUp,
  ChevronDown,
  Plug,
  ExternalLink,
  Zap,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ProviderStatus = 'connected' | 'unconfigured' | 'error';

interface Provider {
  id: string;
  name: string;
  slug: string;
  category: string;
  status: ProviderStatus;
  enabled: boolean;
  is_oauth: boolean;
  priority: number;
  config?: Record<string, string>;
  error_message?: string | null;
}

interface CategoryDef {
  key: string;
  label: string;
  icon: React.ElementType;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CATEGORIES: CategoryDef[] = [
  { key: 'llm', label: 'LLM', icon: Cpu },
  { key: 'image', label: 'Image', icon: Image },
  { key: 'video', label: 'Video', icon: Video },
  { key: 'avatar', label: 'Avatar', icon: Video },
  { key: 'voice', label: 'Voice', icon: Mic },
  { key: 'publishing', label: 'Publishing', icon: Share2 },
  { key: 'analytics', label: 'Analytics', icon: BarChart3 },
  { key: 'trends', label: 'Trends', icon: TrendingUp },
  { key: 'email', label: 'Email', icon: Mail },
  { key: 'inbox', label: 'Inbox', icon: Inbox },
  { key: 'payment', label: 'Payment', icon: DollarSign },
  { key: 'storage', label: 'Storage', icon: Database },
];

const OAUTH_PLATFORMS = ['youtube', 'tiktok', 'instagram', 'x'];

const CATEGORY_MAP = new Map(CATEGORIES.map((c) => [c.key, c]));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function statusBadge(status: ProviderStatus) {
  switch (status) {
    case 'connected':
      return (
        <span className="badge-green">
          <CheckCircle2 size={12} className="mr-1" /> Connected
        </span>
      );
    case 'error':
      return (
        <span className="badge-red">
          <AlertTriangle size={12} className="mr-1" /> Error
        </span>
      );
    default:
      return (
        <span className="badge inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-800 text-gray-400 border border-gray-700">
          <XCircle size={12} className="mr-1" /> Unconfigured
        </span>
      );
  }
}

function prettifyName(slug: string) {
  return slug
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusOverview({
  providers,
  categories,
}: {
  providers: Provider[];
  categories: CategoryDef[];
}) {
  const connected = providers.filter((p) => p.status === 'connected').length;
  const total = providers.length;
  const errorCount = providers.filter((p) => p.status === 'error').length;

  const categoriesWithIssues = useMemo(() => {
    const map = new Map<string, number>();
    for (const p of providers) {
      if (p.status === 'error') {
        map.set(p.category, (map.get(p.category) || 0) + 1);
      }
    }
    return map;
  }, [providers]);

  return (
    <div className="card">
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-brand-600/20 flex items-center justify-center">
            <Plug size={24} className="text-brand-400" />
          </div>
          <div>
            <p className="text-2xl font-bold text-white tabular-nums">
              {connected}
              <span className="text-gray-500 text-lg font-normal">/{total}</span>
            </p>
            <p className="text-sm text-gray-400">providers connected</p>
          </div>
        </div>

        {errorCount > 0 && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-950/50 border border-red-900/50">
            <AlertTriangle size={16} className="text-red-400 shrink-0" />
            <span className="text-sm text-red-300">
              {errorCount} provider{errorCount > 1 ? 's' : ''} with errors
            </span>
          </div>
        )}

        {categoriesWithIssues.size > 0 && (
          <div className="flex flex-wrap gap-1.5 ml-auto">
            {Array.from(categoriesWithIssues.entries()).map(([cat, count]) => {
              const def = CATEGORY_MAP.get(cat);
              return (
                <span
                  key={cat}
                  className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded bg-red-950/40 text-red-300 border border-red-900/30"
                >
                  {def?.label ?? cat}: {count}
                </span>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Provider Card
// ---------------------------------------------------------------------------

function ProviderCard({
  provider,
  onConfigure,
  onToggle,
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
}: {
  provider: Provider;
  onConfigure: (p: Provider) => void;
  onToggle: (p: Provider) => void;
  onMoveUp: (p: Provider) => void;
  onMoveDown: (p: Provider) => void;
  isFirst: boolean;
  isLast: boolean;
}) {
  const isOAuth = OAUTH_PLATFORMS.includes(provider.slug);

  return (
    <div
      className={`bg-gray-800/50 border rounded-lg p-4 transition-all duration-200 hover:border-gray-600 ${
        provider.status === 'error'
          ? 'border-red-900/50'
          : provider.status === 'connected'
            ? 'border-emerald-900/30'
            : 'border-gray-700/50'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        {/* Left: icon + name + status */}
        <div className="flex items-center gap-3 min-w-0">
          <div
            className={`w-10 h-10 rounded-lg flex items-center justify-center text-sm font-bold shrink-0 ${
              provider.status === 'connected'
                ? 'bg-emerald-900/30 text-emerald-300'
                : provider.status === 'error'
                  ? 'bg-red-900/30 text-red-300'
                  : 'bg-gray-700/50 text-gray-400'
            }`}
          >
            {provider.name.slice(0, 2).toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-gray-100 truncate">{provider.name}</p>
            <div className="mt-1">{statusBadge(provider.status)}</div>
            {provider.status === 'error' && provider.error_message && (
              <p className="text-xs text-red-400/80 mt-1 truncate" title={provider.error_message}>
                {provider.error_message}
              </p>
            )}
          </div>
        </div>

        {/* Right: toggle + reorder */}
        <div className="flex items-center gap-2 shrink-0">
          {/* Priority reorder arrows */}
          <div className="flex flex-col">
            <button
              onClick={() => onMoveUp(provider)}
              disabled={isFirst}
              className="p-0.5 text-gray-500 hover:text-white disabled:opacity-20 disabled:cursor-not-allowed transition-colors"
              title="Move up"
            >
              <ChevronUp size={14} />
            </button>
            <button
              onClick={() => onMoveDown(provider)}
              disabled={isLast}
              className="p-0.5 text-gray-500 hover:text-white disabled:opacity-20 disabled:cursor-not-allowed transition-colors"
              title="Move down"
            >
              <ChevronDown size={14} />
            </button>
          </div>

          {/* Enable / Disable toggle */}
          <button
            onClick={() => onToggle(provider)}
            className={`relative w-10 h-5 rounded-full transition-colors duration-200 ${
              provider.enabled ? 'bg-emerald-600' : 'bg-gray-600'
            }`}
            title={provider.enabled ? 'Disable provider' : 'Enable provider'}
          >
            <span
              className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200 ${
                provider.enabled ? 'translate-x-5' : 'translate-x-0'
              }`}
            />
          </button>
        </div>
      </div>

      {/* Configure / Connect button */}
      <div className="mt-3 pt-3 border-t border-gray-700/50">
        {isOAuth ? (
          <a
            href={`/api/v1/accounts/connect/${provider.slug}`}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-brand-400 hover:text-brand-300 transition-colors"
          >
            <ExternalLink size={12} />
            Connect Account
          </a>
        ) : (
          <button
            onClick={() => onConfigure(provider)}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-brand-400 hover:text-brand-300 transition-colors"
          >
            <Zap size={12} />
            Configure
          </button>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Config Modal
// ---------------------------------------------------------------------------

function ConfigModal({
  provider,
  onClose,
  onSaved,
}: {
  provider: Provider;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [error, setError] = useState('');

  const handleTest = async () => {
    if (!apiKey.trim()) return;
    setTesting(true);
    setTestResult(null);
    setError('');
    try {
      const result = await apiFetch<{ ok: boolean; message: string }>(
        '/api/v1/integrations/test',
        {
          method: 'POST',
          body: JSON.stringify({ provider_id: provider.id, api_key: apiKey.trim() }),
        }
      );
      setTestResult(result);
    } catch (e: any) {
      const msg = e?.message || 'Test connection failed';
      setTestResult({ ok: false, message: msg });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    if (!apiKey.trim()) return;
    setSaving(true);
    setError('');
    try {
      await apiFetch('/api/v1/integrations/configure', {
        method: 'POST',
        body: JSON.stringify({ provider_id: provider.id, api_key: apiKey.trim() }),
      });
      onSaved();
      onClose();
    } catch (e: any) {
      setError(e?.message || 'Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70"
      role="dialog"
      aria-modal="true"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="card max-w-lg w-full border-gray-700 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">
            Configure {provider.name}
          </h3>
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-white rounded-lg hover:bg-gray-800 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        <div className="space-y-4">
          {/* API Key Input */}
          <div>
            <label className="stat-label block mb-1.5">API Key</label>
            <div className="relative">
              <input
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => {
                  setApiKey(e.target.value);
                  setError('');
                  setTestResult(null);
                }}
                placeholder="Paste your API key here..."
                className="input-field w-full pr-10 text-sm font-mono"
                autoFocus
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors"
              >
                {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* Test result */}
          {testResult && (
            <div
              className={`flex items-start gap-2 p-3 rounded-lg text-sm ${
                testResult.ok
                  ? 'bg-emerald-950/50 border border-emerald-900/50 text-emerald-300'
                  : 'bg-red-950/50 border border-red-900/50 text-red-300'
              }`}
            >
              {testResult.ok ? (
                <CheckCircle2 size={16} className="shrink-0 mt-0.5" />
              ) : (
                <AlertTriangle size={16} className="shrink-0 mt-0.5" />
              )}
              <span>{testResult.message}</span>
            </div>
          )}

          {/* Error */}
          {error && (
            <p className="text-sm text-red-400">{error}</p>
          )}

          {/* Buttons */}
          <div className="flex items-center gap-2 pt-2">
            <button
              onClick={handleTest}
              disabled={!apiKey.trim() || testing}
              className="btn-secondary text-sm flex items-center gap-1.5 disabled:opacity-40"
            >
              {testing ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Zap size={14} />
              )}
              Test Connection
            </button>
            <button
              onClick={handleSave}
              disabled={!apiKey.trim() || saving}
              className="btn-primary text-sm flex items-center gap-1.5 disabled:opacity-40"
            >
              {saving ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <CheckCircle2 size={14} />
              )}
              Save
            </button>
            <button
              onClick={onClose}
              className="btn-secondary text-sm ml-auto"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function IntegrationsPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [configTarget, setConfigTarget] = useState<Provider | null>(null);

  // Fetch providers
  const fetchProviders = useCallback(async () => {
    try {
      const data = await apiFetch<Provider[]>('/api/v1/integrations/providers');
      setProviders(Array.isArray(data) ? data : []);
      setError('');
    } catch (e: any) {
      setError(e?.message || 'Failed to load providers');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProviders();
  }, [fetchProviders]);

  // Filter by search
  const filteredProviders = useMemo(() => {
    if (!search.trim()) return providers;
    const q = search.toLowerCase();
    return providers.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.slug.toLowerCase().includes(q) ||
        p.category.toLowerCase().includes(q)
    );
  }, [providers, search]);

  // Group by category, sorted by priority within each group
  const grouped = useMemo(() => {
    const map = new Map<string, Provider[]>();
    for (const cat of CATEGORIES) {
      const items = filteredProviders
        .filter((p) => p.category === cat.key)
        .sort((a, b) => a.priority - b.priority);
      if (items.length > 0) {
        map.set(cat.key, items);
      }
    }
    // Also include any providers in categories not in our CATEGORIES list
    for (const p of filteredProviders) {
      if (!CATEGORY_MAP.has(p.category)) {
        const existing = map.get(p.category) || [];
        existing.push(p);
        map.set(p.category, existing);
      }
    }
    return map;
  }, [filteredProviders]);

  // Toggle enable/disable
  const handleToggle = async (provider: Provider) => {
    const updated = providers.map((p) =>
      p.id === provider.id ? { ...p, enabled: !p.enabled } : p
    );
    setProviders(updated);
    try {
      await apiFetch('/api/v1/integrations/configure', {
        method: 'POST',
        body: JSON.stringify({ provider_id: provider.id, enabled: !provider.enabled }),
      });
    } catch {
      // Revert on failure
      setProviders(providers);
    }
  };

  // Reorder helpers
  const handleMove = async (provider: Provider, direction: 'up' | 'down') => {
    const catProviders = providers
      .filter((p) => p.category === provider.category)
      .sort((a, b) => a.priority - b.priority);

    const idx = catProviders.findIndex((p) => p.id === provider.id);
    if (idx < 0) return;
    const swapIdx = direction === 'up' ? idx - 1 : idx + 1;
    if (swapIdx < 0 || swapIdx >= catProviders.length) return;

    const swapTarget = catProviders[swapIdx];
    const newProviders = providers.map((p) => {
      if (p.id === provider.id) return { ...p, priority: swapTarget.priority };
      if (p.id === swapTarget.id) return { ...p, priority: provider.priority };
      return p;
    });
    setProviders(newProviders);

    try {
      await apiFetch('/api/v1/integrations/configure', {
        method: 'POST',
        body: JSON.stringify({
          provider_id: provider.id,
          priority: swapTarget.priority,
        }),
      });
      await apiFetch('/api/v1/integrations/configure', {
        method: 'POST',
        body: JSON.stringify({
          provider_id: swapTarget.id,
          priority: provider.priority,
        }),
      });
    } catch {
      setProviders(providers);
    }
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-6 pb-16">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Plug className="text-brand-500" size={28} />
            Integrations
          </h1>
          <p className="text-gray-400 mt-1">
            Manage provider connections, API keys, and priorities
          </p>
        </div>
      </div>

      {/* Status overview */}
      {!loading && providers.length > 0 && (
        <StatusOverview providers={providers} categories={CATEGORIES} />
      )}

      {/* Search / Filter */}
      <div className="relative max-w-md">
        <Search
          size={16}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500"
        />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search providers by name or category..."
          className="input-field w-full pl-9 text-sm"
        />
        {search && (
          <button
            onClick={() => setSearch('')}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
          >
            <X size={14} />
          </button>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="card py-16 text-center">
          <Loader2 size={24} className="animate-spin text-brand-400 mx-auto mb-3" />
          <p className="text-gray-500 text-sm">Loading providers...</p>
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="card border-red-900/50 bg-red-950/20">
          <div className="flex items-center gap-2 text-red-400">
            <AlertTriangle size={16} />
            <p className="text-sm">{error}</p>
          </div>
          <button
            onClick={() => {
              setLoading(true);
              fetchProviders();
            }}
            className="btn-secondary text-sm mt-3"
          >
            Retry
          </button>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && providers.length === 0 && (
        <div className="card text-center py-14">
          <Plug size={48} className="mx-auto text-gray-600 mb-4" />
          <p className="text-gray-400 mb-1">No providers available.</p>
          <p className="text-sm text-gray-500">
            Provider configurations will appear here once the system is set up.
          </p>
        </div>
      )}

      {/* No search results */}
      {!loading && !error && providers.length > 0 && filteredProviders.length === 0 && (
        <div className="card text-center py-10">
          <Search size={32} className="mx-auto text-gray-600 mb-3" />
          <p className="text-gray-400">
            No providers match &ldquo;{search}&rdquo;
          </p>
        </div>
      )}

      {/* Category groups */}
      {!loading &&
        !error &&
        Array.from(grouped.entries()).map(([catKey, catProviders]) => {
          const def = CATEGORY_MAP.get(catKey);
          const IconComponent = def?.icon ?? Database;
          const label = def?.label ?? prettifyName(catKey);
          const connectedInCat = catProviders.filter(
            (p) => p.status === 'connected'
          ).length;

          return (
            <div key={catKey}>
              <div className="flex items-center gap-2 mb-3">
                <IconComponent size={18} className="text-gray-400" />
                <h2 className="text-lg font-semibold text-white">{label}</h2>
                <span className="text-xs text-gray-500 font-normal">
                  {connectedInCat}/{catProviders.length} connected
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                {catProviders.map((provider, idx) => (
                  <ProviderCard
                    key={provider.id}
                    provider={provider}
                    onConfigure={setConfigTarget}
                    onToggle={handleToggle}
                    onMoveUp={(p) => handleMove(p, 'up')}
                    onMoveDown={(p) => handleMove(p, 'down')}
                    isFirst={idx === 0}
                    isLast={idx === catProviders.length - 1}
                  />
                ))}
              </div>
            </div>
          );
        })}

      {/* Config Modal */}
      {configTarget && (
        <ConfigModal
          provider={configTarget}
          onClose={() => setConfigTarget(null)}
          onSaved={fetchProviders}
        />
      )}
    </div>
  );
}
