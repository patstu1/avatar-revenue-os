'use client';

import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { cinemaStudioApi } from '@/lib/cinema-studio-api';
import { Palette, Star, Plus } from 'lucide-react';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

const CATEGORIES = ['cinematic', 'anime', 'noir', 'documentary', 'retro', 'abstract', 'fantasy', 'minimalist'] as const;

const CATEGORY_COLORS: Record<string, string> = {
  cinematic: 'bg-amber-900/60 text-amber-300',
  anime: 'bg-pink-900/60 text-pink-300',
  noir: 'bg-gray-700 text-gray-200',
  documentary: 'bg-emerald-900/60 text-emerald-300',
  retro: 'bg-orange-900/60 text-orange-300',
  abstract: 'bg-violet-900/60 text-violet-300',
  fantasy: 'bg-indigo-900/60 text-indigo-300',
  minimalist: 'bg-sky-900/60 text-sky-300',
};

const emptyForm = {
  name: '',
  description: '',
  category: '',
  preview_url: '',
  tags: '',
  is_popular: false,
};

export default function StylePresetsPage() {
  const queryClient = useQueryClient();
  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
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

  const { data: styles, isLoading, isError, error } = useQuery({
    queryKey: ['studio-styles', selectedBrandId, categoryFilter],
    queryFn: () =>
      cinemaStudioApi
        .listStyles(selectedBrandId, categoryFilter || undefined)
        .then((r) => r.data),
    enabled: Boolean(selectedBrandId),
  });

  const createMut = useMutation({
    mutationFn: (payload: any) => cinemaStudioApi.createStyle(selectedBrandId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['studio-styles', selectedBrandId] });
      setForm(emptyForm);
      setShowForm(false);
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const payload: any = {
      name: form.name,
      description: form.description,
      category: form.category || "cinematic",
      preview_url: form.preview_url || undefined,
      is_popular: form.is_popular,
      tags: form.tags ? form.tags.split(',').map((t) => t.trim()).filter(Boolean) : [],
    };
    createMut.mutate(payload);
  }

  function setField(key: string, value: any) {
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

  const list = (styles ?? []) as any[];

  return (
    <div className="space-y-8 pb-16">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Palette className="text-brand-500" size={28} aria-hidden />
            Style Presets
          </h1>
          <p className="text-gray-400 mt-1 max-w-3xl">
            Browse and create visual style presets for your cinema productions.
          </p>
        </div>
        <button
          type="button"
          className="btn-primary flex items-center gap-2 shrink-0"
          onClick={() => setShowForm((v) => !v)}
        >
          {showForm ? 'Cancel' : <><Plus size={16} /> New Style</>}
        </button>
      </div>

      <div className="flex flex-col sm:flex-row gap-4">
        <div className="card max-w-xs flex-1">
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

        <div className="card max-w-xs flex-1">
          <label className="stat-label block mb-2">Category Filter</label>
          <select
            className="input-field w-full"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            aria-label="Filter by category"
          >
            <option value="">All Categories</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="card space-y-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Plus size={18} /> Create Style Preset
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
              <label className="stat-label block mb-1">Category</label>
              <select className="input-field w-full" value={form.category} onChange={(e) => setField('category', e.target.value)}>
                <option value="">—</option>
                {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="stat-label block mb-1">Preview URL</label>
              <input className="input-field w-full" value={form.preview_url} onChange={(e) => setField('preview_url', e.target.value)} placeholder="https://…" />
            </div>
            <div className="flex items-end">
              <label className="flex items-center gap-2 cursor-pointer text-gray-300 text-sm">
                <input
                  type="checkbox"
                  className="rounded border-gray-600 bg-gray-800 text-brand-500 focus:ring-brand-500"
                  checked={form.is_popular}
                  onChange={(e) => setField('is_popular', e.target.checked)}
                />
                Mark as Popular
              </label>
            </div>
          </div>

          <div>
            <label className="stat-label block mb-1">Description <span className="text-red-400">*</span></label>
            <textarea className="input-field w-full" rows={3} value={form.description} onChange={(e) => setField('description', e.target.value)} required />
          </div>
          <div>
            <label className="stat-label block mb-1">Tags (comma-separated)</label>
            <input className="input-field w-full" value={form.tags} onChange={(e) => setField('tags', e.target.value)} placeholder="moody, warm tones, …" />
          </div>

          <button type="submit" className="btn-primary flex items-center gap-2 disabled:opacity-50" disabled={createMut.isPending || !form.name || !form.description}>
            {createMut.isPending ? 'Creating…' : <><Plus size={16} /> Create Style</>}
          </button>
        </form>
      )}

      {isLoading && <div className="card py-12 text-center text-gray-500">Loading styles…</div>}
      {isError && <div className="card border-red-900/50 text-red-300 py-8 text-center">{errMessage(error)}</div>}

      {!isLoading && !isError && list.length === 0 && (
        <div className="card text-center py-12 text-gray-500">No style presets yet.</div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {list.map((s: any) => (
          <div key={s.id} className="card overflow-hidden">
            {s.preview_url ? (
              <img
                src={s.preview_url}
                alt={s.name}
                className="w-full h-40 object-cover rounded-t-lg -mt-4 -mx-4 mb-4"
                style={{ width: 'calc(100% + 2rem)' }}
                onError={(e) => {
                  const el = e.target as HTMLImageElement;
                  el.style.display = 'none';
                  el.nextElementSibling?.classList.remove('hidden');
                }}
              />
            ) : null}
            {!s.preview_url && (
              <div className="w-full h-40 rounded-t-lg -mt-4 -mx-4 mb-4 bg-gradient-to-br from-gray-700 to-gray-800 flex items-center justify-center" style={{ width: 'calc(100% + 2rem)' }}>
                <Palette size={36} className="text-gray-600" />
              </div>
            )}

            <div className="flex items-start justify-between mb-2">
              <h3 className="text-white font-semibold">{s.name}</h3>
              <div className="flex items-center gap-1.5">
                {s.is_popular && <Star size={14} className="text-yellow-400 fill-yellow-400" />}
                {s.category && (
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${CATEGORY_COLORS[s.category] ?? 'bg-gray-700 text-gray-300'}`}>
                    {s.category}
                  </span>
                )}
              </div>
            </div>

            {s.description && (
              <p className="text-gray-400 text-sm line-clamp-2 mb-3">{s.description}</p>
            )}

            {s.tags?.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {(s.tags as string[]).map((t) => (
                  <span key={t} className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">{t}</span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
