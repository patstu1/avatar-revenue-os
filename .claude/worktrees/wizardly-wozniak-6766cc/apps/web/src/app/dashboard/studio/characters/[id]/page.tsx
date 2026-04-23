'use client';

import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import { brandsApi } from '@/lib/api';
import { cinemaStudioApi } from '@/lib/cinema-studio-api';
import { User, Pencil, Trash2, ArrowLeft } from 'lucide-react';
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

export default function CharacterDetailPage() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const params = useParams();
  const characterId = params.id as string;

  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Record<string, any>>({});

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) {
      setSelectedBrandId(String(brands[0].id));
    }
  }, [brands, selectedBrandId]);

  const { data: character, isLoading, isError, error } = useQuery({
    queryKey: ['studio-character', selectedBrandId, characterId],
    queryFn: () => cinemaStudioApi.getCharacter(selectedBrandId, characterId).then((r) => r.data),
    enabled: Boolean(selectedBrandId) && Boolean(characterId),
  });

  useEffect(() => {
    if (character && !editing) {
      setForm({
        name: character.name ?? '',
        description: character.description ?? '',
        gender: character.gender ?? '',
        age: character.age ?? '',
        ethnicity: character.ethnicity ?? '',
        hair_color: character.hair_color ?? '',
        hair_style: character.hair_style ?? '',
        eye_color: character.eye_color ?? '',
        build: character.build ?? '',
        personality: character.personality ?? '',
        role: character.role ?? '',
        image_url: character.image_url ?? '',
        tags: (character.tags ?? []).join(', '),
      });
    }
  }, [character, editing]);

  const updateMut = useMutation({
    mutationFn: (payload: any) => cinemaStudioApi.updateCharacter(selectedBrandId, characterId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['studio-character', selectedBrandId, characterId] });
      setEditing(false);
    },
  });

  const deleteMut = useMutation({
    mutationFn: () => cinemaStudioApi.deleteCharacter(selectedBrandId, characterId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['studio-characters'] });
      router.push('/dashboard/studio/characters');
    },
  });

  function handleUpdate(e: React.FormEvent) {
    e.preventDefault();
    const payload: any = { ...form };
    payload.age = form.age ? Number(form.age) : undefined;
    payload.tags = form.tags ? String(form.tags).split(',').map((t: string) => t.trim()).filter(Boolean) : [];
    if (!payload.gender) delete payload.gender;
    if (!payload.role) delete payload.role;
    updateMut.mutate(payload);
  }

  function handleDelete() {
    if (window.confirm('Delete this character permanently?')) {
      deleteMut.mutate();
    }
  }

  function setField(key: string, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  if (brandsLoading || isLoading) {
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

  if (isError) {
    return <div className="card border-red-900/50 text-red-300 py-8 text-center">{errMessage(error)}</div>;
  }

  if (!character) {
    return <div className="card text-center py-12 text-gray-500">Character not found.</div>;
  }

  const c = character as any;

  return (
    <div className="space-y-8 pb-16">
      <div className="flex items-center gap-3">
        <Link href="/dashboard/studio/characters" className="text-gray-400 hover:text-white transition-colors">
          <ArrowLeft size={20} />
        </Link>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <User className="text-brand-500" size={28} aria-hidden />
          {c.name}
        </h1>
        {c.role && (
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${ROLE_COLORS[c.role] ?? 'bg-gray-700 text-gray-300'}`}>
            {c.role}
          </span>
        )}
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

      {deleteMut.isError && (
        <div className="card border-red-900/50 text-red-300 text-sm">{errMessage(deleteMut.error)}</div>
      )}
      {updateMut.isError && (
        <div className="card border-red-900/50 text-red-300 text-sm">{errMessage(updateMut.error)}</div>
      )}

      {!editing ? (
        <div className="card space-y-6">
          <div className="flex items-start justify-between">
            <h2 className="text-lg font-semibold text-white">Character Details</h2>
            <div className="flex gap-2">
              <button
                type="button"
                className="btn-primary flex items-center gap-1.5 text-sm"
                onClick={() => setEditing(true)}
              >
                <Pencil size={14} /> Edit
              </button>
              <button
                type="button"
                className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg bg-red-900/40 text-red-300 hover:bg-red-900/60 transition-colors disabled:opacity-50"
                onClick={handleDelete}
                disabled={deleteMut.isPending}
              >
                <Trash2 size={14} /> {deleteMut.isPending ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {c.image_url ? (
              <div className="md:col-span-2">
                <img
                  src={c.image_url}
                  alt={c.name}
                  className="w-full max-w-sm rounded-lg border border-gray-800 object-cover"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                />
              </div>
            ) : (
              <div className="md:col-span-2">
                <div className="w-full max-w-sm h-48 rounded-lg bg-gray-800 border border-gray-700 flex items-center justify-center text-gray-500">
                  <User size={48} />
                </div>
              </div>
            )}

            <DetailField label="Name" value={c.name} />
            <DetailField label="Role" value={c.role} />
            <DetailField label="Gender" value={c.gender} />
            <DetailField label="Age" value={c.age} />
            <DetailField label="Ethnicity" value={c.ethnicity} />
            <DetailField label="Hair Color" value={c.hair_color} />
            <DetailField label="Hair Style" value={c.hair_style} />
            <DetailField label="Eye Color" value={c.eye_color} />
            <DetailField label="Build" value={c.build} />
          </div>

          {c.description && (
            <div>
              <span className="stat-label block mb-1">Description</span>
              <p className="text-gray-300 text-sm whitespace-pre-wrap">{c.description}</p>
            </div>
          )}

          {c.personality && (
            <div>
              <span className="stat-label block mb-1">Personality</span>
              <p className="text-gray-300 text-sm whitespace-pre-wrap">{c.personality}</p>
            </div>
          )}

          {c.tags?.length > 0 && (
            <div>
              <span className="stat-label block mb-2">Tags</span>
              <div className="flex flex-wrap gap-2">
                {(c.tags as string[]).map((t) => (
                  <span key={t} className="text-xs bg-brand-900/40 text-brand-300 px-2.5 py-1 rounded-full">{t}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <form onSubmit={handleUpdate} className="card space-y-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Pencil size={18} /> Editing {c.name}
          </h2>

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
            <label className="stat-label block mb-1">Description</label>
            <textarea className="input-field w-full" rows={3} value={form.description} onChange={(e) => setField('description', e.target.value)} />
          </div>
          <div>
            <label className="stat-label block mb-1">Personality</label>
            <textarea className="input-field w-full" rows={3} value={form.personality} onChange={(e) => setField('personality', e.target.value)} />
          </div>
          <div>
            <label className="stat-label block mb-1">Tags (comma-separated)</label>
            <input className="input-field w-full" value={form.tags} onChange={(e) => setField('tags', e.target.value)} />
          </div>

          <div className="flex gap-3">
            <button type="submit" className="btn-primary flex items-center gap-2 disabled:opacity-50" disabled={updateMut.isPending || !form.name}>
              {updateMut.isPending ? 'Saving…' : 'Save Changes'}
            </button>
            <button type="button" className="px-4 py-2 rounded-lg bg-gray-800 text-gray-300 hover:bg-gray-700 transition-colors" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

function DetailField({ label, value }: { label: string; value: any }) {
  if (value == null || value === '') return null;
  return (
    <div>
      <span className="stat-label block mb-0.5">{label}</span>
      <span className="text-gray-300 text-sm capitalize">{String(value)}</span>
    </div>
  );
}
