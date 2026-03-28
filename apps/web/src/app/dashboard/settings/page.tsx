'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { settingsApi } from '@/lib/api';
import { Settings, Shield, Key, Save, CheckCircle2, XCircle } from 'lucide-react';

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

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Settings & Integrations</h1>
        <p className="text-gray-400 mt-1">Organization configuration, provider API keys, and system integrations</p>
      </div>

      {/* Organization Settings */}
      <div className="card">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Settings size={18} /> Organization
        </h3>
        {orgLoading ? (
          <p className="text-gray-500 text-sm">Loading organization settings...</p>
        ) : orgError ? (
          <p className="text-red-400 text-sm">Failed to load settings. You may need admin privileges.</p>
        ) : (
          <form
            onSubmit={(e) => { e.preventDefault(); updateOrg.mutate(orgForm); }}
            className="space-y-4"
          >
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
            <div className="flex items-center gap-3">
              <button type="submit" className="btn-primary flex items-center gap-2" disabled={updateOrg.isPending}>
                <Save size={14} /> {updateOrg.isPending ? 'Saving...' : 'Save Changes'}
              </button>
              {updateOrg.isSuccess && <span className="text-emerald-400 text-sm flex items-center gap-1"><CheckCircle2 size={14} /> Saved</span>}
              {updateOrg.isError && <span className="text-red-400 text-sm">Failed to save</span>}
            </div>
            {org && (
              <div className="text-xs text-gray-500 mt-2">
                Slug: <span className="font-mono">{org.slug}</span> &middot; ID: <span className="font-mono">{org.id}</span>
              </div>
            )}
          </form>
        )}
      </div>

      {/* Provider Integrations */}
      <div className="card">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Key size={18} /> Provider API Keys
        </h3>
        <p className="text-gray-400 text-sm mb-4">
          API keys are configured via environment variables. Status shows whether each provider is connected.
        </p>
        {intLoading ? (
          <p className="text-gray-500 text-sm">Loading integrations...</p>
        ) : !integrations?.providers ? (
          <p className="text-gray-500 text-sm">Unable to load integration status.</p>
        ) : (
          <div className="space-y-3">
            {integrations.providers.map((p: any) => (
              <div key={p.provider} className="flex items-center justify-between py-3 px-4 bg-gray-800/50 rounded-lg">
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full ${p.configured ? 'bg-emerald-400' : 'bg-gray-600'}`} />
                  <div>
                    <p className="text-sm font-medium text-gray-200 capitalize">{p.provider}</p>
                    <p className="text-xs text-gray-500">
                      {p.provider === 'openai' && 'LLM, Realtime Voice/Intelligence'}
                      {p.provider === 'elevenlabs' && 'Premium Voice Synthesis (Primary)'}
                      {p.provider === 'tavus' && 'Async Avatar Video Generation (Primary)'}
                      {p.provider === 'heygen' && 'Live Avatar Streaming'}
                      {p.provider === 's3' && 'Object Storage (Assets/Media)'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {p.configured ? (
                    <>
                      <span className="font-mono text-xs text-gray-500">{p.key_preview}</span>
                      <span className="badge-green"><CheckCircle2 size={12} className="mr-1" /> Connected</span>
                    </>
                  ) : (
                    <span className="badge-yellow"><XCircle size={12} className="mr-1" /> Not Configured</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Provider Architecture */}
      <div className="card">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Shield size={18} /> Provider Identity Architecture
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-gray-800/50 rounded-lg p-4">
            <h4 className="text-sm font-semibold text-brand-300 mb-2">Avatar Providers</h4>
            <ul className="space-y-2 text-sm text-gray-400">
              <li><span className="text-white font-medium">Tavus</span> — Primary async avatar video generation</li>
              <li><span className="text-white font-medium">HeyGen LiveAvatar</span> — Live avatar streaming use cases</li>
              <li><span className="text-white font-medium">Fallback</span> — Static/template-based fallback</li>
            </ul>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-4">
            <h4 className="text-sm font-semibold text-brand-300 mb-2">Voice Providers</h4>
            <ul className="space-y-2 text-sm text-gray-400">
              <li><span className="text-white font-medium">ElevenLabs</span> — Primary premium rendered voice</li>
              <li><span className="text-white font-medium">OpenAI Realtime</span> — Live conversational voice/intelligence</li>
              <li><span className="text-white font-medium">Fallback</span> — Basic TTS fallback</li>
            </ul>
          </div>
        </div>
        <p className="text-xs text-gray-500 mt-4">
          Provider profiles are configured per-avatar in the Avatar Manager. Failover routing uses capability-based selection with health status monitoring and audit logging.
        </p>
      </div>
    </div>
  );
}
