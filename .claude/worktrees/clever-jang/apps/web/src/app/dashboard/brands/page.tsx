'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { Plus, Megaphone } from 'lucide-react';

export default function BrandsPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: '', slug: '', niche: '', description: '', decision_mode: 'guarded_auto' });

  const { data: brands, isLoading } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (data: typeof form) => brandsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['brands'] });
      setShowCreate(false);
      setForm({ name: '', slug: '', niche: '', description: '', decision_mode: 'guarded_auto' });
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Brands</h1>
          <p className="text-gray-400 mt-1">Manage brand identities and operating modes</p>
        </div>
        <button onClick={() => setShowCreate(!showCreate)} className="btn-primary flex items-center gap-2">
          <Plus size={16} /> New Brand
        </button>
      </div>

      {showCreate && (
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">Create Brand</h3>
          <form
            onSubmit={(e) => { e.preventDefault(); createMutation.mutate(form); }}
            className="grid grid-cols-1 md:grid-cols-2 gap-4"
          >
            <input placeholder="Brand Name" className="input-field" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            <input placeholder="Slug (url-safe)" className="input-field" value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} required />
            <input placeholder="Niche" className="input-field" value={form.niche} onChange={(e) => setForm({ ...form, niche: e.target.value })} />
            <select className="input-field" value={form.decision_mode} onChange={(e) => setForm({ ...form, decision_mode: e.target.value })}>
              <option value="full_auto">Full Auto</option>
              <option value="guarded_auto">Guarded Auto</option>
              <option value="manual_override">Manual Override</option>
            </select>
            <textarea placeholder="Description" className="input-field md:col-span-2" rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            <div className="md:col-span-2">
              <button type="submit" className="btn-primary" disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Creating...' : 'Create Brand'}
              </button>
            </div>
          </form>
        </div>
      )}

      {isLoading ? (
        <div className="text-gray-500 text-center py-12">Loading brands...</div>
      ) : brands?.length === 0 ? (
        <div className="card text-center py-12">
          <Megaphone size={48} className="mx-auto text-gray-600 mb-4" />
          <p className="text-gray-400">No brands yet. Create your first brand to get started.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {brands?.map((brand: any) => (
            <div key={brand.id} className="card-hover">
              <div className="flex items-start justify-between mb-3">
                <h3 className="text-lg font-semibold text-white">{brand.name}</h3>
                <span className={brand.decision_mode === 'full_auto' ? 'badge-green' : brand.decision_mode === 'guarded_auto' ? 'badge-yellow' : 'badge-blue'}>
                  {brand.decision_mode.replace('_', ' ')}
                </span>
              </div>
              {brand.niche && <p className="text-sm text-gray-400 mb-2">Niche: {brand.niche}</p>}
              {brand.description && <p className="text-sm text-gray-500 line-clamp-2">{brand.description}</p>}
              <div className="mt-4 pt-3 border-t border-gray-800 text-xs text-gray-500">
                Created {new Date(brand.created_at).toLocaleDateString()}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
