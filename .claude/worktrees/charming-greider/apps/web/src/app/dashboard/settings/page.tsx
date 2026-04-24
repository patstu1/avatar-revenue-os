'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { settingsApi } from '@/lib/api';
import { Settings, Shield, Key, Save, CheckCircle2, XCircle, Cpu, Image, Video, Mic, Music, Share2, DollarSign, Mail, Database, Eye, EyeOff, Trash2, Loader2 } from 'lucide-react';

const PROVIDER_CATEGORIES: Record<string, { label: string; icon: any; providers: string[] }> = {
  brain: {
    label: 'Brain / Text AI',
    icon: Cpu,
    providers: ['anthropic', 'google_ai', 'deepseek', 'openai'],
  },
  image: {
    label: 'Image Generation',
    icon: Image,
    providers: ['openai', 'google_ai', 'fal'],
  },
  video: {
    label: 'Video Generation',
    icon: Video,
    providers: ['higgsfield', 'runway', 'fal'],
  },
  avatar: {
    label: 'AI Avatar',
    icon: Video,
    providers: ['heygen', 'did', 'synthesia'],
  },
  voice: {
    label: 'Voice / TTS',
    icon: Mic,
    providers: ['elevenlabs', 'fish_audio', 'mistral'],
  },
  music: {
    label: 'Music / Audio',
    icon: Music,
    providers: ['suno', 'mubert', 'stability'],
  },
  publishing: {
    label: 'Social Publishing',
    icon: Share2,
    providers: ['buffer', 'publer', 'ayrshare'],
  },
  affiliate: {
    label: 'Affiliate Networks',
    icon: DollarSign,
    providers: ['clickbank', 'amazon', 'semrush', 'impact', 'shareasale', 'tiktok_shop', 'etsy'],
  },
  payments: {
    label: 'Payments & Revenue',
    icon: DollarSign,
    providers: ['stripe'],
  },
  infrastructure: {
    label: 'Infrastructure',
    icon: Database,
    providers: ['s3', 'smtp', 'twilio', 'sentry'],
  },
};

function ProviderRow({ provider, description, onSaved }: { provider: any; description: string; onSaved: () => void }) {
  const [editing, setEditing] = useState(false);
  const [keyValue, setKeyValue] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [error, setError] = useState('');

  const saveMutation = useMutation({
    mutationFn: () => settingsApi.saveApiKey(provider.provider, keyValue),
    onSuccess: () => {
      setEditing(false);
      setKeyValue('');
      setError('');
      onSaved();
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Failed to save key');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => settingsApi.deleteApiKey(provider.provider),
    onSuccess: () => {
      setEditing(false);
      setKeyValue('');
      onSaved();
    },
    onError: () => {},
  });

  return (
    <div className="py-3 px-4 bg-gray-800/50 rounded-lg space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-2.5 h-2.5 rounded-full ${provider.configured ? 'bg-emerald-400' : 'bg-gray-600'}`} />
          <div>
            <p className="text-sm font-medium text-gray-200">
              {provider.provider.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}
            </p>
            <p className="text-xs text-gray-500">{description}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {provider.configured ? (
            <>
              <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-400 bg-emerald-400/10 px-2.5 py-1 rounded-full">
                <CheckCircle2 size={12} /> {provider.source === 'dashboard' ? 'Dashboard' : 'Server'}
              </span>
              {!editing && (
                <button
                  onClick={() => setEditing(true)}
                  className="text-xs text-gray-400 hover:text-white px-2 py-1 rounded hover:bg-gray-700 transition"
                >
                  Update
                </button>
              )}
              {provider.source === 'dashboard' && !editing && (
                <button
                  onClick={() => { if (confirm('Remove this API key?')) deleteMutation.mutate(); }}
                  className="text-xs text-red-400 hover:text-red-300 px-1.5 py-1 rounded hover:bg-red-900/20 transition"
                  title="Remove key"
                >
                  <Trash2 size={12} />
                </button>
              )}
            </>
          ) : (
            <>
              <span className="inline-flex items-center gap-1 text-xs font-medium text-gray-400 bg-gray-700/50 px-2.5 py-1 rounded-full">
                <XCircle size={12} /> Not Set
              </span>
              {!editing && (
                <button
                  onClick={() => setEditing(true)}
                  className="text-xs text-blue-400 hover:text-blue-300 px-2 py-1 rounded hover:bg-blue-900/20 transition font-medium"
                >
                  + Add Key
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {editing && (
        <div className="flex items-center gap-2 pt-1">
          <div className="relative flex-1">
            <input
              type={showKey ? 'text' : 'password'}
              value={keyValue}
              onChange={(e) => { setKeyValue(e.target.value); setError(''); }}
              placeholder={provider.configured ? 'Enter new key to replace...' : 'Paste your API key here...'}
              className="input-field w-full pr-8 text-sm"
              autoFocus
            />
            <button
              type="button"
              onClick={() => setShowKey(!showKey)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
            >
              {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          </div>
          <button
            onClick={() => saveMutation.mutate()}
            disabled={!keyValue.trim() || saveMutation.isPending}
            className="btn-primary text-xs px-3 py-2 flex items-center gap-1 disabled:opacity-40"
          >
            {saveMutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
            Save
          </button>
          <button
            onClick={() => { setEditing(false); setKeyValue(''); setError(''); }}
            className="text-xs text-gray-400 hover:text-white px-2 py-2 rounded hover:bg-gray-700 transition"
          >
            Cancel
          </button>
        </div>
      )}
      {error && <p className="text-xs text-red-400 pl-5">{error}</p>}
      {provider.configured && provider.key_preview && !editing && (
        <p className="text-xs text-gray-600 pl-5 font-mono">{provider.key_preview}</p>
      )}
    </div>
  );
}

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [orgForm, setOrgForm] = useState({ name: '', plan: '' });
  const [initialized, setInitialized] = useState(false);

  const { data: org, isLoading: orgLoading, error: orgError } = useQuery({
    queryKey: ['settings-org'],
    queryFn: () => settingsApi.getOrganization().then((r) => r.data),
  });

  const { data: integrations, isLoading: intLoading } = useQuery({
    queryKey: ['settings-integrations'],
    queryFn: () => settingsApi.getIntegrations().then((r) => r.data),
  });

  if (org && !initialized) {
    setOrgForm({ name: org.name, plan: org.plan });
    setInitialized(true);
  }

  const updateOrg = useMutation({
    mutationFn: (data: any) => settingsApi.updateOrganization(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['settings-org'] }),
  });

  const providerMap = new Map<string, any>();
  const descriptions = (integrations as any)?.descriptions || {};
  if (integrations?.providers) {
    for (const p of integrations.providers) {
      providerMap.set(p.provider, p);
    }
  }

  const configuredCount = integrations?.providers?.filter((p: any) => p.configured).length || 0;
  const totalCount = integrations?.providers?.length || 0;

  const refreshIntegrations = () => queryClient.invalidateQueries({ queryKey: ['settings-integrations'] });

  return (
    <div className="space-y-8 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Settings size={24} /> Settings & API Keys
        </h1>
        <p className="text-gray-400 mt-1">
          {configuredCount}/{totalCount} providers connected — add keys directly below
        </p>
      </div>

      {/* Organization Settings */}
      <div className="card">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Shield size={18} /> Organization
        </h3>
        {orgLoading ? (
          <p className="text-gray-500 text-sm">Loading...</p>
        ) : orgError ? (
          <p className="text-red-400 text-sm">Failed to load settings.</p>
        ) : (
          <form onSubmit={(e) => { e.preventDefault(); updateOrg.mutate(orgForm); }} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="stat-label block mb-1">Organization Name</label>
                <input className="input-field w-full" value={orgForm.name} onChange={(e) => setOrgForm({ ...orgForm, name: e.target.value })} />
              </div>
              <div>
                <label className="stat-label block mb-1">Plan</label>
                <select className="input-field w-full" value={orgForm.plan} onChange={(e) => setOrgForm({ ...orgForm, plan: e.target.value })}>
                  <option value="free">Free</option>
                  <option value="pro">Pro</option>
                  <option value="enterprise">Enterprise</option>
                </select>
              </div>
            </div>
            <button type="submit" className="btn-primary flex items-center gap-2" disabled={updateOrg.isPending}>
              <Save size={14} /> {updateOrg.isPending ? 'Saving...' : 'Save Changes'}
            </button>
            {org && <p className="text-xs text-gray-500 mt-2">Slug: <span className="font-mono">{org.slug}</span> &middot; ID: <span className="font-mono">{org.id}</span></p>}
          </form>
        )}
      </div>

      {/* Provider Status by Category */}
      {intLoading ? (
        <div className="card py-8 text-center text-gray-500">Loading provider status...</div>
      ) : (
        Object.entries(PROVIDER_CATEGORIES).map(([catKey, cat]) => {
          const catProviders = cat.providers
            .map((name) => providerMap.get(name))
            .filter(Boolean)
            .filter((p, i, arr) => arr.findIndex((x: any) => x.provider === p.provider) === i);

          if (catProviders.length === 0) return null;
          const connectedInCat = catProviders.filter((p: any) => p.configured).length;
          const IconComponent = cat.icon;

          return (
            <div key={catKey} className="card">
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <IconComponent size={18} />
                {cat.label}
                <span className="text-xs text-gray-500 font-normal ml-2">
                  {connectedInCat}/{catProviders.length} connected
                </span>
              </h3>
              <div className="space-y-2">
                {catProviders.map((p: any) => (
                  <ProviderRow
                    key={`${catKey}-${p.provider}`}
                    provider={p}
                    description={descriptions[p.provider] || ''}
                    onSaved={refreshIntegrations}
                  />
                ))}
              </div>
            </div>
          );
        })
      )}

      {/* Info Card */}
      <div className="card border-blue-900/30 bg-blue-900/5">
        <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
          <Key size={18} /> How API Keys Work
        </h3>
        <div className="text-sm text-gray-400 space-y-2">
          <p>You can add API keys in two ways:</p>
          <ul className="list-disc list-inside space-y-1 text-gray-300">
            <li><strong className="text-emerald-400">Dashboard</strong> — Click &quot;+ Add Key&quot; next to any provider above. Keys are encrypted and stored securely in the database.</li>
            <li><strong className="text-blue-400">Server .env</strong> — Set keys as environment variables. Dashboard keys take priority over .env keys.</li>
          </ul>
          <p className="text-xs text-gray-500 mt-3">All keys are encrypted at rest using AES-256. Dashboard-stored keys override server environment variables. You can remove dashboard keys at any time to fall back to the server .env value.</p>
        </div>
      </div>
    </div>
  );
}
