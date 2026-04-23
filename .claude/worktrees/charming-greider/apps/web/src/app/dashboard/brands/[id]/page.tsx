'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import {
  ArrowLeft,
  CheckCircle2,
  Loader2,
  Megaphone,
  Save,
  Trash2,
} from 'lucide-react';
import Link from 'next/link';

type Brand = {
  id: string;
  name: string;
  slug: string;
  niche?: string;
  sub_niche?: string;
  description?: string;
  target_audience?: string;
  tone_of_voice?: string;
  brand_guidelines?: Record<string, unknown>;
  decision_mode: string;
  is_active: boolean;
  created_at: string;
};

export default function BrandEditPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const brandId = params.id as string;
  const setSelectedBrandId = useAppStore((s) => s.setSelectedBrandId);

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
  const [saved, setSaved] = useState(false);

  const { data: brand, isLoading, isError } = useQuery({
    queryKey: ['brand', brandId],
    queryFn: () => brandsApi.get(brandId).then((r) => r.data as Brand),
    enabled: Boolean(brandId),
  });

  useEffect(() => {
    if (brand) {
      setForm({
        name: brand.name || '',
        slug: brand.slug || '',
        niche: brand.niche || '',
        sub_niche: brand.sub_niche || '',
        description: brand.description || '',
        target_audience: brand.target_audience || '',
        tone_of_voice: brand.tone_of_voice || '',
        decision_mode: brand.decision_mode || 'guarded_auto',
      });
    }
  }, [brand]);

  const updateMutation = useMutation({
    mutationFn: (data: Partial<typeof form>) => brandsApi.update(brandId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['brand', brandId] });
      queryClient.invalidateQueries({ queryKey: ['brands'] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateMutation.mutate(form);
  };

  const handleSetActive = () => {
    setSelectedBrandId(brandId);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="animate-spin text-gray-600" size={32} />
      </div>
    );
  }

  if (isError || !brand) {
    return (
      <div className="space-y-4 p-6">
        <Link href="/dashboard/brands" className="text-gray-400 hover:text-white flex items-center gap-2 text-sm">
          <ArrowLeft size={16} /> Back to Brands
        </Link>
        <div className="card border-red-900/50 text-red-300 py-8 text-center">
          Brand not found or failed to load.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/dashboard/brands" className="text-gray-400 hover:text-white transition-colors">
            <ArrowLeft size={20} />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-3">
              <Megaphone className="text-brand-400" size={24} />
              {brand.name}
            </h1>
            <p className="text-gray-500 text-sm mt-1">/{brand.slug} &middot; Created {new Date(brand.created_at).toLocaleDateString()}</p>
          </div>
        </div>
        <button
          onClick={handleSetActive}
          className="px-4 py-2 rounded-lg bg-brand-600/20 text-brand-300 text-sm font-medium hover:bg-brand-600/30 transition-colors border border-brand-600/30"
        >
          Set as Active Brand
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="card space-y-5">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Identity</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Brand Name</label>
              <input
                className="input-field w-full"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Slug</label>
              <input
                className="input-field w-full"
                value={form.slug}
                onChange={(e) => setForm({ ...form, slug: e.target.value })}
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Niche</label>
              <input
                className="input-field w-full"
                value={form.niche}
                onChange={(e) => setForm({ ...form, niche: e.target.value })}
                placeholder="e.g. beauty, AI tools, celebrity culture"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Sub-Niche</label>
              <input
                className="input-field w-full"
                value={form.sub_niche}
                onChange={(e) => setForm({ ...form, sub_niche: e.target.value })}
                placeholder="e.g. aesthetics / medspa"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Description</label>
            <textarea
              className="input-field w-full"
              rows={3}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="What this brand is about"
            />
          </div>
        </div>

        <div className="card space-y-5">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Voice & Audience</h2>

          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Target Audience</label>
            <textarea
              className="input-field w-full"
              rows={2}
              value={form.target_audience}
              onChange={(e) => setForm({ ...form, target_audience: e.target.value })}
              placeholder="Who is this brand for?"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Tone of Voice</label>
            <textarea
              className="input-field w-full"
              rows={2}
              value={form.tone_of_voice}
              onChange={(e) => setForm({ ...form, tone_of_voice: e.target.value })}
              placeholder="How should this brand sound?"
            />
          </div>
        </div>

        <div className="card space-y-5">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Operations</h2>

          <div className="max-w-xs">
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Decision Mode</label>
            <select
              className="input-field w-full"
              value={form.decision_mode}
              onChange={(e) => setForm({ ...form, decision_mode: e.target.value })}
            >
              <option value="full_auto">Full Auto</option>
              <option value="guarded_auto">Guarded Auto</option>
              <option value="manual_override">Manual Override</option>
            </select>
            <p className="text-xs text-gray-600 mt-2">
              {form.decision_mode === 'full_auto' && 'System executes all decisions autonomously.'}
              {form.decision_mode === 'guarded_auto' && 'System proposes, operator approves high-impact actions.'}
              {form.decision_mode === 'manual_override' && 'Operator approves all actions before execution.'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={updateMutation.isPending}
            className="btn-primary flex items-center gap-2 disabled:opacity-50"
          >
            {updateMutation.isPending ? (
              <><Loader2 size={16} className="animate-spin" /> Saving...</>
            ) : saved ? (
              <><CheckCircle2 size={16} className="text-emerald-400" /> Saved</>
            ) : (
              <><Save size={16} /> Save Changes</>
            )}
          </button>
          {updateMutation.isError && (
            <span className="text-red-400 text-sm">Failed to save. Try again.</span>
          )}
        </div>
      </form>
    </div>
  );
}
