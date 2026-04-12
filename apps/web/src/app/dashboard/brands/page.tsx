'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import Link from 'next/link';
import {
  CheckCircle2,
  ChevronRight,
  Megaphone,
  Plus,
  Star,
} from 'lucide-react';

type Brand = {
  id: string;
  name: string;
  slug: string;
  niche?: string;
  sub_niche?: string;
  description?: string;
  target_audience?: string;
  tone_of_voice?: string;
  decision_mode: string;
  is_active: boolean;
  created_at: string;
};

const modeConfig: Record<string, { label: string; class: string }> = {
  full_auto: { label: 'Full Auto', class: 'badge-green' },
  guarded_auto: { label: 'Guarded Auto', class: 'badge-yellow' },
  manual_override: { label: 'Manual', class: 'badge-blue' },
};

export default function BrandsPage() {
  const queryClient = useQueryClient();
  const selectedBrandId = useAppStore((s) => s.selectedBrandId);
  const setSelectedBrandId = useAppStore((s) => s.setSelectedBrandId);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    name: '',
    slug: '',
    niche: '',
    sub_niche: '',
    description: '',
    target_audience: '',
    tone_of_voice: '',
    decision_mode: 'guarded_auto',
  });

  const { data: brands, isLoading } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  const createMutation = useMutation({
    mutationFn: (data: typeof form) => brandsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['brands'] });
      setShowCreate(false);
      setForm({ name: '', slug: '', niche: '', sub_niche: '', description: '', target_audience: '', tone_of_voice: '', decision_mode: 'guarded_auto' });
    },
  });

  const autoSlug = (name: string) => name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Megaphone className="text-brand-400" size={24} />
            Brands
          </h1>
          <p className="text-gray-400 mt-1">Manage brand identities, audience, voice, and operating modes</p>
        </div>
        <button onClick={() => setShowCreate(!showCreate)} className="btn-primary flex items-center gap-2">
          <Plus size={16} /> New Brand
        </button>
      </div>

      {showCreate && (
        <div className="card border-brand-600/30">
          <h3 className="text-lg font-semibold text-white mb-4">Create Brand</h3>
          <form
            onSubmit={(e) => { e.preventDefault(); createMutation.mutate(form); }}
            className="space-y-4"
          >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Brand Name *</label>
                <input className="input-field w-full" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value, slug: form.slug || autoSlug(e.target.value) })} required />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Slug *</label>
                <input className="input-field w-full" value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} required />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Niche</label>
                <input className="input-field w-full" value={form.niche} onChange={(e) => setForm({ ...form, niche: e.target.value })} placeholder="e.g. beauty, AI tools" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Decision Mode</label>
                <select className="input-field w-full" value={form.decision_mode} onChange={(e) => setForm({ ...form, decision_mode: e.target.value })}>
                  <option value="full_auto">Full Auto</option>
                  <option value="guarded_auto">Guarded Auto</option>
                  <option value="manual_override">Manual Override</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Description</label>
              <textarea className="input-field w-full" rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>
            <div className="flex gap-3">
              <button type="submit" className="btn-primary" disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Creating...' : 'Create Brand'}
              </button>
              <button type="button" onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">
                Cancel
              </button>
            </div>
            {createMutation.isError && <p className="text-red-400 text-sm">Failed to create brand. Check fields and try again.</p>}
          </form>
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => <div key={i} className="h-48 bg-gray-800/60 rounded-xl animate-pulse" />)}
        </div>
      ) : !brands?.length ? (
        <div className="card text-center py-16">
          <Megaphone size={48} className="mx-auto text-gray-700 mb-4" />
          <p className="text-gray-400 text-lg">No brands yet</p>
          <p className="text-gray-600 text-sm mt-2">Create your first brand to start building content and revenue.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {brands.map((brand) => {
            const isActive = selectedBrandId === brand.id;
            const mode = modeConfig[brand.decision_mode] || modeConfig.guarded_auto;

            return (
              <Link
                key={brand.id}
                href={`/dashboard/brands/${brand.id}`}
                className={`card-hover group relative transition-all ${
                  isActive
                    ? 'ring-2 ring-brand-500/50 border-brand-500/30'
                    : ''
                }`}
              >
                {isActive && (
                  <div className="absolute top-3 right-3 flex items-center gap-1 text-brand-300 text-[10px] font-bold uppercase tracking-wider">
                    <Star size={12} className="fill-brand-400 text-brand-400" /> Active
                  </div>
                )}
                <div className="flex items-start justify-between mb-3">
                  <h3 className="text-lg font-semibold text-white group-hover:text-brand-300 transition-colors">{brand.name}</h3>
                </div>
                <div className="flex flex-wrap gap-2 mb-3">
                  <span className={mode.class}>{mode.label}</span>
                  {brand.niche && (
                    <span className="inline-flex rounded-md border border-gray-700 bg-gray-800 px-2 py-0.5 text-xs text-gray-300">
                      {brand.niche}
                    </span>
                  )}
                  {brand.sub_niche && (
                    <span className="inline-flex rounded-md border border-gray-700/50 bg-gray-800/50 px-2 py-0.5 text-xs text-gray-400">
                      {brand.sub_niche}
                    </span>
                  )}
                </div>
                {brand.description && (
                  <p className="text-sm text-gray-500 line-clamp-2 mb-3">{brand.description}</p>
                )}
                <div className="mt-auto pt-3 border-t border-gray-800 flex items-center justify-between">
                  <span className="text-xs text-gray-600">
                    Created {new Date(brand.created_at).toLocaleDateString()}
                  </span>
                  <span className="text-xs text-gray-500 group-hover:text-brand-400 transition-colors flex items-center gap-1">
                    Edit <ChevronRight size={12} />
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
