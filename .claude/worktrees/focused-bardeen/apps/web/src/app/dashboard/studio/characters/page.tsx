'use client';

import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { cinemaStudioApi } from '@/lib/cinema-studio-api';
import { Users, Plus, UserPlus } from 'lucide-react';
import Link from 'next/link';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

const ROLE_OPTIONS = ['lead', 'supporting', 'background', 'narrator', 'antagonist'] as const;
const GENDER_OPTIONS = ['male', 'female', 'non-binary', 'other'] as const;

const ROLE_COLORS: Record<string, string> = {
  lead: 'bg-purple-900/60 text-purple-300',
  supporting: 'bg-sky-900/60 text-sky-300',
  background: 'bg-gray-700 text-gray-300',
  narrator: 'bg-amber-900/60 text-amber-300',
  antagonist: 'bg-red-900/60 text-red-300',
};

const emptyForm = {
  name: '',
  description: '',
  gender: '',
  age: '',
  ethnicity: '',
  hair_color: '',
  hair_style: '',
  eye_color: '',
  build: '',
  personality: '',
  role: '',
  image_url: '',
  tags: '',
};

export default function CharacterBiblePage() {
  const queryClient = useQueryClient();
  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) {
      setSelectedBrandId(String(brands[0].id));
    }
  }, [brands, selectedBrandId]);

  const { data: characters, isLoading, isError, error } = useQuery({
    queryKey: ['studio-characters', selectedBrandId],
    queryFn: () => cinemaStudioApi.listCharacters(selectedBrandId).then((r) => r.data),
    enabled: Boolean(selectedBrandId),
  });

  const createMut = useMutation({
    mutationFn: (payload: any) => cinemaStudioApi.createCharacter(selectedBrandId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['studio-characters', selectedBrandId] });
      setForm(emptyForm);
      setShowForm(false);
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const payload: any = { ...form };
    payload.age = form.age ? Number(form.age) : undefined;
    payload.tags = form.tags ? form.tags.split(',').map((t) => t.trim()).filter(Boolean) : [];
    if (!payload.gender) delete payload.gender;
    if (!payload.role) delete payload.role;
    createMut.mutate(payload);
  }

  function setField(key: string, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  if (brandsLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-96 bg-gray-800 rounded animate-pulse" />
        <div className="card py-12 text-center text-gray-500">Loading…</div>
      </div>
    );
  }

  if (brandsError) {
    return <div className="card border-red-900/50 text-red-300 py-8 text-center">{errMessage(brandsErr)}</div>;
  }

  if (!brands?.length) {
    return <div className="card text-center py-12 text-gray-500">Create a brand first.</div>;
  }

  const list = (characters ?? []) as any[];

  return (
    <div className="space-y-8 pb-16">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Users className="text-brand-500" size={28} aria-hidden />
            Character Bible
          </h1>
          <p className="text-gray-400 mt-1 max-w-3xl">
            Define and manage every character in your cinema universe.
          </p>
        </div>
        <button
          type="button"
          className="btn-primary flex items-center gap-2 shrink-0"
          onClick={() => setShowForm((v) => !v)}
        >
          {showForm ? 'Cancel' : <><UserPlus size={16} /> New Character</>}
        </button>
      </div>

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          value={selectedBrandId}
          onChange={(e) => setSelectedBrandId(e.target.value)}
          aria-label="Select brand"
        >
          {brands.map((b) => (
            <option key={b.id} value={String(b.id)}>{b.name}</option>
          ))}
        </select>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="card space-y-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Plus size={18} /> Create Character
          </h2>

          {createMut.isError && (
            <div className="text-red-300 text-sm">{errMessage(createMut.error)}</div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="stat-label block mb-1">Name *</label>
              <input className="input-field w-full" required value={form.name} onChange={(e) => setField('name', e.target.value)} />
            </div>
            <div>
              <label className="stat-label block mb-1">Role</label>
              <select className="input-field w-full" value={form.role} onChange={(e) => setField('role', e.target.value)}>
                <option value="">—</option>
                {ROLE_OPTIONS.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <div>
              <label className="stat-label block mb-1">Gender</label>
              <select className="input-field w-full" value={form.gender} onChange={(e) => setField('gender', e.target.value)}>
                <option value="">—</option>
                {GENDER_OPTIONS.map((g) => <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <div>
              <label className="stat-label block mb-1">Age</label>
              <input className="input-field w-full" type="number" min={0} value={form.age} onChange={(e) => setField('age', e.target.value)} />
            </div>
            <div>
              <label className="stat-label block mb-1">Ethnicity</label>
              <input className="input-field w-full" value={form.ethnicity} onChange={(e) => setField('ethnicity', e.target.value)} />
            </div>
            <div>
              <label className="stat-label block mb-1">Hair Color</label>
              <input className="input-field w-full" value={form.hair_color} onChange={(e) => setField('hair_color', e.target.value)} />
            </div>
            <div>
              <label className="stat-label block mb-1">Hair Style</label>
              <input className="input-field w-full" value={form.hair_style} onChange={(e) => setField('hair_style', e.target.value)} />
            </div>
            <div>
              <label className="stat-label block mb-1">Eye Color</label>
              <input className="input-field w-full" value={form.eye_color} onChange={(e) => setField('eye_color', e.target.value)} />
            </div>
            <div>
              <label className="stat-label block mb-1">Build</label>
              <input className="input-field w-full" value={form.build} onChange={(e) => setField('build', e.target.value)} />
            </div>
            <div>
              <label className="stat-label block mb-1">Image URL</label>
              <input className="input-field w-full" value={form.image_url} onChange={(e) => setField('image_url', e.target.value)} />
            </div>
          </div>

          <div>
            <label className="stat-label block mb-1">Description <span className="text-red-400">*</span></label>
            <textarea className="input-field w-full" rows={3} value={form.description} onChange={(e) => setField('description', e.target.value)} required />
          </div>
          <div>
            <label className="stat-label block mb-1">Personality</label>
            <textarea className="input-field w-full" rows={3} value={form.personality} onChange={(e) => setField('personality', e.target.value)} />
          </div>
          <div>
            <label className="stat-label block mb-1">Tags (comma-separated)</label>
            <input className="input-field w-full" value={form.tags} onChange={(e) => setField('tags', e.target.value)} placeholder="hero, mentor, wise" />
          </div>

          <button type="submit" className="btn-primary flex items-center gap-2 disabled:opacity-50" disabled={createMut.isPending || !form.name || !form.description}>
            {createMut.isPending ? 'Creating…' : <><Plus size={16} /> Create Character</>}
          </button>
        </form>
      )}

      {isLoading && <div className="card py-12 text-center text-gray-500">Loading characters…</div>}
      {isError && <div className="card border-red-900/50 text-red-300 py-8 text-center">{errMessage(error)}</div>}

      {!isLoading && !isError && list.length === 0 && (
        <div className="card text-center py-12 text-gray-500">No characters yet. Create one above.</div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {list.map((c: any) => (
          <Link
            key={c.id}
            href={`/dashboard/studio/characters/${c.id}`}
            className="card hover:border-gray-600 transition-colors group"
          >
            <div className="flex items-start justify-between mb-2">
              <h3 className="text-white font-semibold text-lg group-hover:text-brand-400 transition-colors">
                {c.name}
              </h3>
              {c.role && (
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${ROLE_COLORS[c.role] ?? 'bg-gray-700 text-gray-300'}`}>
                  {c.role}
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 text-sm text-gray-400 mb-3">
              {c.gender && <span className="capitalize">{c.gender}</span>}
              {c.age != null && <span>Age {c.age}</span>}
            </div>
            {c.description && (
              <p className="text-gray-400 text-sm line-clamp-2 mb-3">{c.description}</p>
            )}
            {c.tags?.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {(c.tags as string[]).map((t) => (
                  <span key={t} className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">{t}</span>
                ))}
              </div>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
