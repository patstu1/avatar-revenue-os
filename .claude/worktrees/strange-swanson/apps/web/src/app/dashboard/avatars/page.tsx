'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Palette,
  Plus,
  Trash2,
  Mic,
  Video,
  Shield,
  ChevronDown,
} from 'lucide-react';
import { avatarsApi, brandsApi, providersApi } from '@/lib/api';
import { useAppStore } from '@/lib/store';

type Brand = { id: string; name: string };
type AvatarRow = {
  id: string;
  brand_id: string;
  name: string;
  persona_description?: string | null;
  voice_style?: string | null;
  visual_style?: string | null;
  default_language: string;
  is_active: boolean;
  created_at?: string;
};

type AvatarProviderRow = {
  id: string;
  avatar_id: string;
  provider: string;
  provider_avatar_id?: string | null;
  is_primary: boolean;
  is_fallback: boolean;
  health_status: string;
  cost_per_minute?: number | null;
};

type VoiceProviderRow = {
  id: string;
  avatar_id: string;
  provider: string;
  provider_voice_id?: string | null;
  is_primary: boolean;
  is_fallback: boolean;
  health_status: string;
  cost_per_minute?: number | null;
};

function errMessage(e: unknown): string {
  const ax = e as { response?: { data?: { detail?: unknown } } };
  const d = ax.response?.data?.detail;
  if (typeof d === 'string') return d;
  if (Array.isArray(d))
    return d.map((x: { msg?: string }) => x.msg ?? JSON.stringify(x)).join(', ');
  return 'Something went wrong';
}

function healthBadgeClass(status: string): string {
  if (status === 'healthy') return 'badge-green';
  if (status === 'warning') return 'badge-yellow';
  return 'badge-red';
}

function AvatarProviderSection({ avatar }: { avatar: AvatarRow }) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [form, setForm] = useState({
    provider: '',
    provider_avatar_id: '',
    is_primary: false,
    is_fallback: false,
    cost_per_minute: '',
  });

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['avatar-providers', avatar.id],
    queryFn: () =>
      providersApi.listAvatarProviders(avatar.id).then((r) => r.data as AvatarProviderRow[]),
  });

  const createMutation = useMutation({
    mutationFn: (body: {
      avatar_id: string;
      provider: string;
      provider_avatar_id?: string;
      is_primary: boolean;
      is_fallback: boolean;
      cost_per_minute?: number;
    }) => providersApi.createAvatarProvider(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['avatar-providers', avatar.id] });
      setExpanded(false);
      setForm({
        provider: '',
        provider_avatar_id: '',
        is_primary: false,
        is_fallback: false,
        cost_per_minute: '',
      });
    },
  });

  return (
    <div className="mt-4 pt-4 border-t border-gray-800">
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 text-sm font-medium text-gray-300">
          <Video size={16} className="text-cyan-400" />
          Avatar providers
        </div>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="btn-secondary text-xs py-1.5 px-2 flex items-center gap-1"
        >
          <Plus size={14} /> Add profile
        </button>
      </div>
      {isLoading ? (
        <p className="text-sm text-gray-500">Loading...</p>
      ) : isError ? (
        <p className="text-sm text-red-400">{errMessage(error)}</p>
      ) : !data?.length ? (
        <p className="text-sm text-gray-500">
          No avatar provider profiles yet. Add one to connect a video avatar engine.
        </p>
      ) : (
        <ul className="space-y-2">
          {data.map((p) => (
            <li
              key={p.id}
              className="rounded-lg bg-gray-900/60 border border-gray-800 px-3 py-2 text-sm"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-white font-medium capitalize">{p.provider}</span>
                {p.is_primary && <span className="badge-blue">primary</span>}
                {p.is_fallback && <span className="badge-yellow">fallback</span>}
                <span className={healthBadgeClass(p.health_status)}>{p.health_status}</span>
                {p.cost_per_minute != null && (
                  <span className="text-gray-400">
                    <span className="stat-label">cost/min</span>{' '}
                    {Number(p.cost_per_minute).toFixed(4)}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {createMutation.isError && (
        <p className="text-sm text-red-400 mt-2">{errMessage(createMutation.error)}</p>
      )}
      {expanded && (
        <form
          className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            const cost = form.cost_per_minute.trim();
            createMutation.mutate({
              avatar_id: avatar.id,
              provider: form.provider.trim(),
              provider_avatar_id: form.provider_avatar_id.trim() || undefined,
              is_primary: form.is_primary,
              is_fallback: form.is_fallback,
              ...(cost !== '' ? { cost_per_minute: Number(cost) } : {}),
            });
          }}
        >
          <input
            className="input-field sm:col-span-2"
            placeholder="Provider (e.g. heygen, tavus)"
            value={form.provider}
            onChange={(e) => setForm({ ...form, provider: e.target.value })}
            required
          />
          <input
            className="input-field sm:col-span-2"
            placeholder="Provider avatar ID (optional)"
            value={form.provider_avatar_id}
            onChange={(e) => setForm({ ...form, provider_avatar_id: e.target.value })}
          />
          <label className="flex items-center gap-2 text-sm text-gray-400">
            <input
              type="checkbox"
              checked={form.is_primary}
              onChange={(e) => setForm({ ...form, is_primary: e.target.checked })}
            />
            Primary
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-400">
            <input
              type="checkbox"
              checked={form.is_fallback}
              onChange={(e) => setForm({ ...form, is_fallback: e.target.checked })}
            />
            Fallback
          </label>
          <input
            className="input-field sm:col-span-2"
            placeholder="Cost per minute (optional)"
            type="number"
            step="any"
            value={form.cost_per_minute}
            onChange={(e) => setForm({ ...form, cost_per_minute: e.target.value })}
          />
          <div className="sm:col-span-2 flex gap-2">
            <button type="submit" className="btn-primary" disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Saving...' : 'Save avatar provider'}
            </button>
            <button type="button" className="btn-secondary" onClick={() => setExpanded(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

function VoiceProviderSection({ avatar }: { avatar: AvatarRow }) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [form, setForm] = useState({
    provider: '',
    provider_voice_id: '',
    is_primary: false,
    is_fallback: false,
    cost_per_minute: '',
  });

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['voice-providers', avatar.id],
    queryFn: () =>
      providersApi.listVoiceProviders(avatar.id).then((r) => r.data as VoiceProviderRow[]),
  });

  const createMutation = useMutation({
    mutationFn: (body: {
      avatar_id: string;
      provider: string;
      provider_voice_id?: string;
      is_primary: boolean;
      is_fallback: boolean;
      cost_per_minute?: number;
    }) => providersApi.createVoiceProvider(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['voice-providers', avatar.id] });
      setExpanded(false);
      setForm({
        provider: '',
        provider_voice_id: '',
        is_primary: false,
        is_fallback: false,
        cost_per_minute: '',
      });
    },
  });

  return (
    <div className="mt-4 pt-4 border-t border-gray-800">
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 text-sm font-medium text-gray-300">
          <Mic size={16} className="text-violet-400" />
          Voice providers
        </div>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="btn-secondary text-xs py-1.5 px-2 flex items-center gap-1"
        >
          <Plus size={14} /> Add profile
        </button>
      </div>
      {isLoading ? (
        <p className="text-sm text-gray-500">Loading...</p>
      ) : isError ? (
        <p className="text-sm text-red-400">{errMessage(error)}</p>
      ) : !data?.length ? (
        <p className="text-sm text-gray-500">
          No voice provider profiles yet. Add TTS or realtime voice backends here.
        </p>
      ) : (
        <ul className="space-y-2">
          {data.map((p) => (
            <li
              key={p.id}
              className="rounded-lg bg-gray-900/60 border border-gray-800 px-3 py-2 text-sm"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-white font-medium capitalize">{p.provider}</span>
                {p.is_primary && <span className="badge-blue">primary</span>}
                {p.is_fallback && <span className="badge-yellow">fallback</span>}
                <span className={healthBadgeClass(p.health_status)}>{p.health_status}</span>
                {p.cost_per_minute != null && (
                  <span className="text-gray-400">
                    <span className="stat-label">cost/min</span>{' '}
                    {Number(p.cost_per_minute).toFixed(4)}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {createMutation.isError && (
        <p className="text-sm text-red-400 mt-2">{errMessage(createMutation.error)}</p>
      )}
      {expanded && (
        <form
          className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            const cost = form.cost_per_minute.trim();
            createMutation.mutate({
              avatar_id: avatar.id,
              provider: form.provider.trim(),
              provider_voice_id: form.provider_voice_id.trim() || undefined,
              is_primary: form.is_primary,
              is_fallback: form.is_fallback,
              ...(cost !== '' ? { cost_per_minute: Number(cost) } : {}),
            });
          }}
        >
          <input
            className="input-field sm:col-span-2"
            placeholder="Provider (e.g. elevenlabs, openai_realtime)"
            value={form.provider}
            onChange={(e) => setForm({ ...form, provider: e.target.value })}
            required
          />
          <input
            className="input-field sm:col-span-2"
            placeholder="Provider voice ID (optional)"
            value={form.provider_voice_id}
            onChange={(e) => setForm({ ...form, provider_voice_id: e.target.value })}
          />
          <label className="flex items-center gap-2 text-sm text-gray-400">
            <input
              type="checkbox"
              checked={form.is_primary}
              onChange={(e) => setForm({ ...form, is_primary: e.target.checked })}
            />
            Primary
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-400">
            <input
              type="checkbox"
              checked={form.is_fallback}
              onChange={(e) => setForm({ ...form, is_fallback: e.target.checked })}
            />
            Fallback
          </label>
          <input
            className="input-field sm:col-span-2"
            placeholder="Cost per minute (optional)"
            type="number"
            step="any"
            value={form.cost_per_minute}
            onChange={(e) => setForm({ ...form, cost_per_minute: e.target.value })}
          />
          <div className="sm:col-span-2 flex gap-2">
            <button type="submit" className="btn-primary" disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Saving...' : 'Save voice provider'}
            </button>
            <button type="button" className="btn-secondary" onClick={() => setExpanded(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

export default function AvatarsPage() {
  const queryClient = useQueryClient();
  const selectedBrandId = useAppStore((s) => s.selectedBrandId);
  const setSelectedBrandId = useAppStore((s) => s.setSelectedBrandId);

  const [showCreate, setShowCreate] = useState(false);
  const [traitsJson, setTraitsJson] = useState('{}');
  const [traitsError, setTraitsError] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState({
    name: '',
    persona_description: '',
    voice_style: '',
    visual_style: '',
    default_language: 'en',
  });

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
    if (brands && brands.length > 0 && !selectedBrandId) {
      setSelectedBrandId(brands[0].id);
    }
  }, [brands, selectedBrandId, setSelectedBrandId]);

  const {
    data: avatars,
    isLoading: avatarsLoading,
    isError: avatarsError,
    error: avatarsErr,
  } = useQuery({
    queryKey: ['avatars', selectedBrandId],
    queryFn: () =>
      avatarsApi.list(selectedBrandId!).then((r) => r.data as AvatarRow[]),
    enabled: Boolean(selectedBrandId),
  });

  const createMutation = useMutation({
    mutationFn: (payload: {
      brand_id: string;
      name: string;
      persona_description?: string;
      voice_style?: string;
      visual_style?: string;
      default_language: string;
      personality_traits?: Record<string, unknown>;
    }) => avatarsApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['avatars', selectedBrandId] });
      setShowCreate(false);
      setTraitsJson('{}');
      setTraitsError(null);
      setCreateForm({
        name: '',
        persona_description: '',
        voice_style: '',
        visual_style: '',
        default_language: 'en',
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => avatarsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['avatars', selectedBrandId] });
    },
  });

  const selectedBrandName = useMemo(() => {
    if (!selectedBrandId || !brands) return null;
    return brands.find((b) => b.id === selectedBrandId)?.name ?? null;
  }, [brands, selectedBrandId]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="rounded-lg bg-gray-800/80 p-2 border border-gray-700">
            <Palette className="text-amber-400" size={24} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Avatar Manager</h1>
            <p className="text-gray-400 mt-1">
              Personas, voice and visual styles, and provider routing per brand
            </p>
          </div>
        </div>
        {selectedBrandId && (
          <button
            type="button"
            onClick={() => setShowCreate((v) => !v)}
            className="btn-primary flex items-center gap-2 shrink-0"
          >
            <Plus size={16} /> New avatar
          </button>
        )}
      </div>

      <div className="card">
        <label htmlFor="avatars-brand-select" className="stat-label block mb-2">
          Brand
        </label>
        <div className="relative max-w-md">
          <select
            id="avatars-brand-select"
            aria-label="Brand for avatar management"
            className="input-field w-full appearance-none pr-10"
            value={selectedBrandId ?? ''}
            onChange={(e) => setSelectedBrandId(e.target.value || null)}
            disabled={brandsLoading}
          >
            <option value="">Select a brand…</option>
            {brands?.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
          <ChevronDown
            size={18}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none"
          />
        </div>
        {brandsLoading && <p className="text-gray-500 mt-3">Loading...</p>}
        {brandsError && (
          <p className="text-red-400 mt-3">{errMessage(brandsErr)}</p>
        )}
        {!brandsLoading && !brandsError && brands?.length === 0 && (
          <p className="text-gray-500 mt-3">
            No brands found. Create a brand first, then pick it here to manage avatars.
          </p>
        )}
      </div>

      {showCreate && selectedBrandId && (
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Shield size={18} className="text-gray-400" />
            <h2 className="text-lg font-semibold text-white">Create avatar</h2>
          </div>
          <form
            className="grid grid-cols-1 md:grid-cols-2 gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              setTraitsError(null);
              let personality_traits: Record<string, unknown> | undefined;
              try {
                const parsed = JSON.parse(traitsJson || '{}') as unknown;
                if (parsed !== null && typeof parsed === 'object' && !Array.isArray(parsed)) {
                  personality_traits = parsed as Record<string, unknown>;
                } else {
                  setTraitsError('Personality traits must be a JSON object.');
                  return;
                }
              } catch {
                setTraitsError('Invalid JSON for personality traits.');
                return;
              }
              createMutation.mutate({
                brand_id: selectedBrandId,
                name: createForm.name.trim(),
                persona_description: createForm.persona_description.trim() || undefined,
                voice_style: createForm.voice_style.trim() || undefined,
                visual_style: createForm.visual_style.trim() || undefined,
                default_language: createForm.default_language.trim() || 'en',
                personality_traits,
              });
            }}
          >
            <input
              className="input-field md:col-span-2"
              placeholder="Name"
              value={createForm.name}
              onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
              required
            />
            <textarea
              className="input-field md:col-span-2"
              rows={3}
              placeholder="Persona description"
              value={createForm.persona_description}
              onChange={(e) =>
                setCreateForm({ ...createForm, persona_description: e.target.value })
              }
            />
            <input
              className="input-field"
              placeholder="Voice style"
              value={createForm.voice_style}
              onChange={(e) => setCreateForm({ ...createForm, voice_style: e.target.value })}
            />
            <input
              className="input-field"
              placeholder="Visual style"
              value={createForm.visual_style}
              onChange={(e) => setCreateForm({ ...createForm, visual_style: e.target.value })}
            />
            <input
              className="input-field md:col-span-2"
              placeholder="Default language (e.g. en)"
              value={createForm.default_language}
              onChange={(e) =>
                setCreateForm({ ...createForm, default_language: e.target.value })
              }
            />
            <div className="md:col-span-2">
              <label htmlFor="avatar-personality-traits-json" className="stat-label block mb-1">
                Personality traits (JSON object)
              </label>
              <textarea
                id="avatar-personality-traits-json"
                className="input-field font-mono text-sm"
                rows={5}
                placeholder='{"warmth": 0.8}'
                value={traitsJson}
                onChange={(e) => setTraitsJson(e.target.value)}
                spellCheck={false}
              />
              {traitsError && <p className="text-sm text-red-400 mt-1">{traitsError}</p>}
            </div>
            {createMutation.isError && (
              <p className="text-red-400 md:col-span-2 text-sm">
                {errMessage(createMutation.error)}
              </p>
            )}
            <div className="md:col-span-2 flex gap-2">
              <button type="submit" className="btn-primary" disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Creating...' : 'Create avatar'}
              </button>
              <button type="button" className="btn-secondary" onClick={() => setShowCreate(false)}>
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {!selectedBrandId && !brandsLoading && brands && brands.length > 0 && (
        <div className="card text-center py-10">
          <p className="text-gray-400">Select a brand above to load avatars.</p>
        </div>
      )}

      {selectedBrandId && (
        <>
          {avatarsLoading && (
            <div className="text-gray-500 text-center py-12">Loading...</div>
          )}
          {avatarsError && (
            <p className="text-red-400 text-center py-6">{errMessage(avatarsErr)}</p>
          )}
          {!avatarsLoading && !avatarsError && avatars?.length === 0 && (
            <div className="card text-center py-12">
              <Video size={44} className="mx-auto text-gray-600 mb-3" />
              <p className="text-gray-400 mb-1">No avatars for {selectedBrandName ?? 'this brand'}.</p>
              <p className="text-sm text-gray-500">
                Create an avatar to define persona, language, and hook up providers.
              </p>
            </div>
          )}
          {!avatarsLoading && !avatarsError && avatars && avatars.length > 0 && (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              {avatars.map((avatar) => (
                <div key={avatar.id} className="card-hover">
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="min-w-0">
                      <h3 className="text-lg font-semibold text-white">{avatar.name}</h3>
                      <p className="text-sm text-gray-400 mt-1 line-clamp-3">
                        <span className="stat-label">Persona</span>{' '}
                        {avatar.persona_description?.trim() ? avatar.persona_description : '—'}
                      </p>
                    </div>
                    <div className="flex flex-col items-end gap-2 shrink-0">
                      <span className={avatar.is_active ? 'badge-green' : 'badge-red'}>
                        {avatar.is_active ? 'active' : 'inactive'}
                      </span>
                      <button
                        type="button"
                        className="btn-secondary text-xs py-1 px-2 flex items-center gap-1 text-red-300 border-red-900/50 hover:bg-red-950/30"
                        disabled={deleteMutation.isPending}
                        onClick={() => {
                          if (
                            !confirm(
                              `Delete avatar "${avatar.name}"? This cannot be undone.`
                            )
                          )
                            return;
                          deleteMutation.mutate(avatar.id);
                        }}
                      >
                        <Trash2 size={14} /> Delete
                      </button>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                    <div>
                      <p className="stat-label">Voice style</p>
                      <p className="text-gray-300">{avatar.voice_style ?? '—'}</p>
                    </div>
                    <div>
                      <p className="stat-label">Visual style</p>
                      <p className="text-gray-300">{avatar.visual_style ?? '—'}</p>
                    </div>
                    <div>
                      <p className="stat-label">Language</p>
                      <p className="text-gray-300">{avatar.default_language}</p>
                    </div>
                  </div>
                  <AvatarProviderSection avatar={avatar} />
                  <VoiceProviderSection avatar={avatar} />
                </div>
              ))}
            </div>
          )}
          {deleteMutation.isError && (
            <p className="text-red-400 text-sm text-center">
              {errMessage(deleteMutation.error)}
            </p>
          )}
        </>
      )}
    </div>
  );
}
