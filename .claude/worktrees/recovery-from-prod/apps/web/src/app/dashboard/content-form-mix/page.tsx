'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { contentFormApi } from '@/lib/content-form-api';
import { PieChart, RefreshCcw } from 'lucide-react';

interface MixReport {
  id: string;
  dimension: string;
  dimension_value: string;
  mix_allocation: Record<string, number>;
  total_expected_upside: number;
  avg_confidence: number;
  explanation: string | null;
}

const DIMENSION_BADGE: Record<string, string> = {
  platform: 'bg-blue-600/20 text-blue-300',
  funnel_stage: 'bg-amber-600/20 text-amber-300',
  monetization: 'bg-green-600/20 text-green-300',
};

const BAR_COLORS = [
  'bg-violet-500', 'bg-blue-500', 'bg-cyan-500', 'bg-emerald-500',
  'bg-amber-500', 'bg-rose-500', 'bg-indigo-500', 'bg-teal-500',
];

export default function ContentFormMixPage() {
  const brandId = useBrandId();
  const [items, setItems] = useState<MixReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      const { data } = await contentFormApi.mix(brandId);
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
      await contentFormApi.recomputeMix(brandId);
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
          <PieChart className="h-8 w-8 text-blue-400" />
          <h1 className="text-2xl font-bold text-white">Content Form Mix</h1>
        </div>
        <button
          onClick={handleRecompute}
          disabled={recomputing}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
        >
          <RefreshCcw size={16} className={recomputing ? 'animate-spin' : ''} />
          {recomputing ? 'Recomputing...' : 'Recompute Mix'}
        </button>
      </div>

      {loading ? (
        <p className="text-gray-400 text-center py-8">Loading mix reports...</p>
      ) : items.length === 0 ? (
        <p className="text-gray-500 text-center py-8">No mix reports yet. Recompute recommendations first, then recompute mix.</p>
      ) : (
        <div className="grid gap-5">
          {items.map((r) => {
            const entries = Object.entries(r.mix_allocation);
            return (
              <div key={r.id} className="rounded-lg border border-gray-800 bg-gray-900/50 p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className={`px-2.5 py-1 rounded text-xs font-semibold uppercase ${DIMENSION_BADGE[r.dimension] || 'bg-gray-700 text-gray-300'}`}>
                      {r.dimension.replace(/_/g, ' ')}
                    </span>
                    <span className="text-white font-semibold">{r.dimension_value}</span>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-gray-400">
                    <span>Upside: <span className="text-green-400 font-mono">${r.total_expected_upside.toFixed(0)}</span></span>
                    <span>Confidence: <span className="text-gray-200 font-mono">{(r.avg_confidence * 100).toFixed(0)}%</span></span>
                  </div>
                </div>

                <div className="space-y-2">
                  {entries.map(([form, pct], i) => (
                    <div key={form} className="flex items-center gap-3">
                      <span className="text-gray-400 text-xs w-36 truncate">{form.replace(/_/g, ' ')}</span>
                      <div className="flex-1 h-5 bg-gray-800 rounded overflow-hidden">
                        <div
                          className={`h-full ${BAR_COLORS[i % BAR_COLORS.length]} rounded transition-all`}
                          style={{ width: `${Math.max(2, pct * 100)}%` }}
                        />
                      </div>
                      <span className="text-gray-300 text-xs font-mono w-12 text-right">{(pct * 100).toFixed(1)}%</span>
                    </div>
                  ))}
                </div>

                {r.explanation && (
                  <p className="text-gray-500 text-xs">{r.explanation}</p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
