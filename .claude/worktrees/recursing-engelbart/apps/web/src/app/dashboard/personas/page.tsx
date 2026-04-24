'use client';

import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi, accountsApi, apiFetch } from '@/lib/api';
import {
  Loader2, Plus, Trash2, ToggleLeft, ToggleRight, User, X, Mic, Sparkles,
} from 'lucide-react';

/* ─── Types ─── */

type Brand = { id: string; name: string };
type Account = { id: string; platform_username: string; platform: string };

interface Persona {
  id: string;
  brand_id: string;
  account_id: string;
  character_name: string;
  character_tagline: string | null;
  character_backstory: string | null;
  character_archetype: string;
  communication_style: string;
  humor_level: string;
  energy_level: string;
  formality_level: string;
  personality_traits: string[];
  catchphrases: string[];
  voice_provider: string | null;
  voice_id: string | null;
  voice_description: string | null;
  visual_style: string | null;
  favorite_topics: string[];
  expertise_areas: string[];
  content_philosophy: string | null;
  is_active: boolean;
  created_at: string;
}

const ARCHETYPES = ['expert', 'entertainer', 'educator', 'motivator', 'storyteller', 'analyst', 'provocateur'] as const;
const STYLES = ['direct', 'conversational', 'authoritative', 'friendly', 'sarcastic', 'empathetic'] as const;
const LEVELS = ['low', 'moderate', 'high'] as const;
const FORMALITY = ['very_casual', 'casual', 'balanced', 'formal', 'very_formal'] as const;

/* ─── API ─── */

const personaApi = {
  list: (brandId: string) => apiFetch(`/api/v1/personas/?brand_id=${brandId}`),
  create: (data: Record<string, unknown>) =>
    apiFetch('/api/v1/personas/', { method: 'POST', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } }),
  patch: (id: string, data: Record<string, unknown>) =>
    apiFetch(`/api/v1/personas/${id}`, { method: 'PATCH', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } }),
  del: (id: string) =>
    apiFetch(`/api/v1/personas/${id}`, { method: 'DELETE' }),
};

/* ─── Page ─── */

export default function PersonasPage() {
  const queryClient = useQueryClient();
  const [brandId, setBrandId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    account_id: '',
    character_name: '',
    character_tagline: '',
    character_archetype: 'expert',
    communication_style: 'direct',
    humor_level: 'moderate',
    energy_level: 'high',
    formality_level: 'casual',
    voice_description: '',
    content_philosophy: '',
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

  const { data: personas, isLoading } = useQuery({
    queryKey: ['personas', brandId],
    queryFn: () => personaApi.list(brandId!) as Promise<Persona[]>,
    enabled: !!brandId,
  });

  const { data: accounts } = useQuery({
    queryKey: ['accounts-for-persona', brandId],
    queryFn: () => accountsApi.list({ brand_id: brandId }).then((r) => {
      const d = r.data;
      return (Array.isArray(d) ? d : d?.items ?? []) as Account[];
    }),
    enabled: !!brandId,
  });

  const createMut = useMutation({
    mutationFn: (data: Record<string, unknown>) => personaApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['personas', brandId] });
      setShowForm(false);
    },
  });

  const toggleMut = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) => personaApi.patch(id, { is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['personas', brandId] }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => personaApi.del(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['personas', brandId] }),
  });

  const handleCreate = () => {
    if (!brandId || !form.account_id || !form.character_name) return;
    createMut.mutate({
      brand_id: brandId,
      account_id: form.account_id,
      character_name: form.character_name,
      character_tagline: form.character_tagline || null,
      character_archetype: form.character_archetype,
      communication_style: form.communication_style,
      humor_level: form.humor_level,
      energy_level: form.energy_level,
      formality_level: form.formality_level,
      voice_description: form.voice_description || null,
      content_philosophy: form.content_philosophy || null,
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-start gap-3">
          <Sparkles className="text-brand-400 shrink-0 mt-1" size={28} />
          <div>
            <h1 className="text-2xl font-bold text-white">AI Personas</h1>
            <p className="text-gray-400 mt-1">Character identities for content channels</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <select className="input-field min-w-[180px]" value={brandId ?? ''} onChange={(e) => setBrandId(e.target.value || null)}>
            {!brands?.length && <option value="">No brands</option>}
            {(brands as Brand[] | undefined)?.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
          <button className="btn-primary flex items-center gap-2" onClick={() => setShowForm(!showForm)}>
            {showForm ? <X size={16} /> : <Plus size={16} />}
            {showForm ? 'Cancel' : 'New Persona'}
          </button>
        </div>
      </div>

      {/* Create Form */}
      {showForm && (
        <div className="card border-brand-600/30 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <label className="metric-label mb-1 block">Account</label>
              <select className="input-field w-full" value={form.account_id} onChange={(e) => setForm((f) => ({ ...f, account_id: e.target.value }))}>
                <option value="">Select account...</option>
                {accounts?.map((a) => <option key={a.id} value={a.id}>{a.platform_username} ({a.platform})</option>)}
              </select>
            </div>
            <div>
              <label className="metric-label mb-1 block">Character Name</label>
              <input className="input-field w-full" placeholder="e.g. Alex Finance" value={form.character_name} onChange={(e) => setForm((f) => ({ ...f, character_name: e.target.value }))} />
            </div>
            <div>
              <label className="metric-label mb-1 block">Tagline</label>
              <input className="input-field w-full" placeholder="Short intro line" value={form.character_tagline} onChange={(e) => setForm((f) => ({ ...f, character_tagline: e.target.value }))} />
            </div>
            <div>
              <label className="metric-label mb-1 block">Archetype</label>
              <select className="input-field w-full" value={form.character_archetype} onChange={(e) => setForm((f) => ({ ...f, character_archetype: e.target.value }))}>
                {ARCHETYPES.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
            <div>
              <label className="metric-label mb-1 block">Style</label>
              <select className="input-field w-full" value={form.communication_style} onChange={(e) => setForm((f) => ({ ...f, communication_style: e.target.value }))}>
                {STYLES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="metric-label mb-1 block">Energy</label>
              <select className="input-field w-full" value={form.energy_level} onChange={(e) => setForm((f) => ({ ...f, energy_level: e.target.value }))}>
                {LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="metric-label mb-1 block">Voice Description</label>
            <input className="input-field w-full" placeholder="e.g. Deep authoritative male, fast-paced" value={form.voice_description} onChange={(e) => setForm((f) => ({ ...f, voice_description: e.target.value }))} />
          </div>
          <div>
            <label className="metric-label mb-1 block">Content Philosophy</label>
            <textarea className="input-field w-full h-20 resize-none" placeholder="What drives this character's content?" value={form.content_philosophy} onChange={(e) => setForm((f) => ({ ...f, content_philosophy: e.target.value }))} />
          </div>
          <button className="btn-primary flex items-center gap-2" onClick={handleCreate} disabled={createMut.isPending || !form.account_id || !form.character_name}>
            {createMut.isPending ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />} Create Persona
          </button>
        </div>
      )}

      {/* Persona Cards */}
      {isLoading ? (
        <div className="card flex items-center justify-center py-12"><Loader2 className="animate-spin text-gray-500" size={24} /></div>
      ) : !personas?.length ? (
        <div className="card text-center py-12">
          <User className="mx-auto text-gray-600 mb-3" size={32} />
          <p className="text-gray-400">No personas configured</p>
          <p className="text-gray-600 text-sm mt-1">Create character identities for your content channels</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {personas.map((p) => (
            <div key={p.id} className={`card space-y-3 ${!p.is_active ? 'opacity-50' : ''}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded bg-brand-600/20 flex items-center justify-center text-brand-400 font-mono font-bold text-sm">
                    {p.character_name.slice(0, 2).toUpperCase()}
                  </div>
                  <div>
                    <p className="text-white font-medium">{p.character_name}</p>
                    {p.character_tagline && <p className="text-gray-500 text-xs">{p.character_tagline}</p>}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button className="text-gray-400 hover:text-white" onClick={() => toggleMut.mutate({ id: p.id, is_active: !p.is_active })}>
                    {p.is_active ? <ToggleRight size={20} className="text-emerald-400" /> : <ToggleLeft size={20} />}
                  </button>
                  <button className="text-gray-500 hover:text-red-400" onClick={() => deleteMut.mutate(p.id)}>
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
              <div className="flex flex-wrap gap-1.5">
                <span className="chip-cyan">{p.character_archetype}</span>
                <span className="chip">{p.communication_style}</span>
                <span className="chip">{p.energy_level} energy</span>
              </div>
              {p.voice_description && (
                <div className="flex items-center gap-2 text-xs text-gray-400">
                  <Mic size={12} /> {p.voice_description}
                </div>
              )}
              {p.content_philosophy && (
                <p className="text-xs text-gray-500 line-clamp-2">{p.content_philosophy}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
