'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { contentFormApi } from '@/lib/content-form-api';
import { AlertTriangle } from 'lucide-react';

interface Blocker {
  id: string;
  content_form: string;
  blocker_type: string;
  severity: string;
  description: string;
  operator_action: string;
  resolved: boolean;
}

const SEVERITY_BADGE: Record<string, string> = {
  critical: 'bg-red-600/20 text-red-300 border-red-600/30',
  high: 'bg-orange-600/20 text-orange-300 border-orange-600/30',
  medium: 'bg-yellow-600/20 text-yellow-300 border-yellow-600/30',
  low: 'bg-gray-600/20 text-gray-300 border-gray-600/30',
};

export default function ContentFormBlockersPage() {
  const brandId = useBrandId();
  const [items, setItems] = useState<Blocker[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      const { data } = await contentFormApi.blockers(brandId);
      setItems(data);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [brandId]);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <AlertTriangle className="h-8 w-8 text-amber-400" />
        <h1 className="text-2xl font-bold text-white">Content Form Blockers</h1>
      </div>

      {loading ? (
        <p className="text-gray-400 text-center py-8">Loading blockers...</p>
      ) : items.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-green-400 font-medium">No active blockers</p>
          <p className="text-gray-500 text-sm mt-1">All content form capabilities are available.</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((b) => (
            <div
              key={b.id}
              className={`rounded-lg border p-5 space-y-3 ${
                b.severity === 'high' || b.severity === 'critical'
                  ? 'border-red-800/60 bg-red-950/20'
                  : 'border-gray-800 bg-gray-900/50'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-white font-semibold text-sm">
                  {b.content_form.replace(/_/g, ' ')}
                </span>
                <span className={`px-2 py-0.5 rounded text-xs font-medium border ${SEVERITY_BADGE[b.severity] || SEVERITY_BADGE.medium}`}>
                  {b.severity}
                </span>
              </div>
              <p className="text-xs text-gray-400 font-mono">{b.blocker_type.replace(/_/g, ' ')}</p>
              <p className="text-sm text-gray-300">{b.description}</p>
              <div className="pt-2 border-t border-gray-800">
                <p className="text-xs text-violet-400 font-medium">Action Required</p>
                <p className="text-xs text-gray-400 mt-0.5">{b.operator_action}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
