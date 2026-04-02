'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { settingsApi } from '@/lib/api';
import { Settings, Shield, Key, Save, CheckCircle2, XCircle, Cpu, Image, Video, Mic, Music, Share2, DollarSign, Mail, Database } from 'lucide-react';

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

  return (
    <div className="space-y-8 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Settings size={24} /> Settings & API Keys
        </h1>
        <p className="text-gray-400 mt-1">
          {configuredCount}/{totalCount} providers connected
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
                  <div key={`${catKey}-${p.provider}`} className="flex items-center justify-between py-3 px-4 bg-gray-800/50 rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className={`w-2.5 h-2.5 rounded-full ${p.configured ? 'bg-emerald-400' : 'bg-gray-600'}`} />
                      <div>
                        <p className="text-sm font-medium text-gray-200">{p.provider.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}</p>
                        <p className="text-xs text-gray-500">{descriptions[p.provider] || ''}</p>
                      </div>
                    </div>
                    <div>
                      {p.configured ? (
                        <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-400 bg-emerald-400/10 px-2.5 py-1 rounded-full">
                          <CheckCircle2 size={12} /> Connected
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs font-medium text-gray-400 bg-gray-700/50 px-2.5 py-1 rounded-full">
                          <XCircle size={12} /> Not Set
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })
      )}

      {/* How to Configure */}
      <div className="card border-blue-900/30 bg-blue-900/5">
        <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
          <Key size={18} /> How to Add API Keys
        </h3>
        <div className="text-sm text-gray-400 space-y-2">
          <p>API keys are set as environment variables on the server for security. To add or change a key:</p>
          <ol className="list-decimal list-inside space-y-1 text-gray-300">
            <li>SSH into your server</li>
            <li>Edit the .env file: <code className="text-xs bg-gray-800 px-1.5 py-0.5 rounded">nano /opt/nvironments/AI\ AVATAR\ CONTENT\ OS\ OPS\ NEW/.env</code></li>
            <li>Add or update the key (e.g. <code className="text-xs bg-gray-800 px-1.5 py-0.5 rounded">ANTHROPIC_API_KEY=sk-ant-...</code>)</li>
            <li>Save and restart: <code className="text-xs bg-gray-800 px-1.5 py-0.5 rounded">docker compose restart api worker scheduler</code></li>
          </ol>
          <p className="text-xs text-gray-500 mt-3">Keys are never stored in the database — only in server environment variables. The status above shows whether each key is detected.</p>
        </div>
      </div>
    </div>
  );
}
