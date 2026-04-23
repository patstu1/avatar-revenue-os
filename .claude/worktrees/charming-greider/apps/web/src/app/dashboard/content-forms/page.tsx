'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { contentFormApi } from '@/lib/content-form-api';
import { Layers, RefreshCcw } from 'lucide-react';

interface Recommendation {
  id: string;
  platform: string;
  recommended_content_form: string;
  secondary_content_form: string | null;
  format_family: string;
  short_or_long: string;
  avatar_mode: string;
  trust_level_required: string;
  production_cost_band: string;
  expected_upside: number;
  expected_cost: number;
  confidence: number;
  urgency: number;
  explanation: string;
  truth_label: string;
  blockers: any[] | null;
}

const AVATAR_BADGE: Record<string, string> = {
  full_avatar: 'bg-violet-600/20 text-violet-300',
  voice_only: 'bg-blue-600/20 text-blue-300',
  avatar_overlay: 'bg-cyan-600/20 text-cyan-300',
  none: 'bg-gray-700/40 text-gray-400',
};

const COST_BADGE: Record<string, string> = {
  low: 'text-green-400',
  medium: 'text-yellow-400',
  high: 'text-red-400',
};

export default function ContentFormsPage() {
  const brandId = useBrandId();
  const [items, setItems] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      const { data } = await contentFormApi.recommendations(brandId);
      setItems(data);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    try {
      await contentFormApi.recomputeRecommendations(brandId);
      setTimeout(fetchData, 2000);
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => { fetchData(); }, [brandId]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Layers className="h-8 w-8 text-violet-400" />
          <h1 className="text-2xl font-bold text-white">Content Form Recommendations</h1>
        </div>
        <button
          onClick={handleRecompute}
          disabled={recomputing}
          className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
        >
          <RefreshCcw size={16} className={recomputing ? 'animate-spin' : ''} />
          {recomputing ? 'Recomputing...' : 'Recompute'}
        </button>
      </div>

      {loading ? (
        <p className="text-gray-400 text-center py-8">Loading recommendations...</p>
      ) : items.length === 0 ? (
        <p className="text-gray-500 text-center py-8">No content form recommendations yet. Click Recompute to generate.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-800">
          <table className="w-full text-sm text-left">
            <thead className="bg-gray-800/50 text-gray-400 uppercase text-xs">
              <tr>
                <th className="px-4 py-3">Content Form</th>
                <th className="px-4 py-3">Format</th>
                <th className="px-4 py-3">Length</th>
                <th className="px-4 py-3">Avatar Mode</th>
                <th className="px-4 py-3">Cost Band</th>
                <th className="px-4 py-3 text-right">Upside</th>
                <th className="px-4 py-3 text-right">Confidence</th>
                <th className="px-4 py-3">Explanation</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {items.map((r) => (
                <tr key={r.id} className="hover:bg-gray-800/30 transition-colors">
                  <td className="px-4 py-3 text-white font-medium whitespace-nowrap">
                    {r.recommended_content_form.replace(/_/g, ' ')}
                  </td>
                  <td className="px-4 py-3 text-gray-300">{r.format_family}</td>
                  <td className="px-4 py-3 text-gray-300">{r.short_or_long}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${AVATAR_BADGE[r.avatar_mode] || AVATAR_BADGE.none}`}>
                      {r.avatar_mode.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td className={`px-4 py-3 font-medium ${COST_BADGE[r.production_cost_band] || 'text-gray-300'}`}>
                    {r.production_cost_band}
                  </td>
                  <td className="px-4 py-3 text-right text-green-400 font-mono">${r.expected_upside.toFixed(0)}</td>
                  <td className="px-4 py-3 text-right font-mono text-gray-200">{(r.confidence * 100).toFixed(0)}%</td>
                  <td className="px-4 py-3 text-gray-400 max-w-xs truncate">{r.explanation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
