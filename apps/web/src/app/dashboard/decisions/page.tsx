'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { decisionsApi } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import { GitBranch } from 'lucide-react';

const DECISION_TYPES = [
  'opportunity', 'monetization', 'publish', 'suppression', 'scale', 'allocation', 'expansion',
];

export default function DecisionsPage() {
  const [selectedType, setSelectedType] = useState('opportunity');
  const brandId = useAppStore((s) => s.selectedBrandId);

  const { data, isLoading } = useQuery({
    queryKey: ['decisions', selectedType, brandId],
    queryFn: () => brandId ? decisionsApi.list(selectedType, brandId).then((r) => r.data) : null,
    enabled: !!brandId,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Decision Log</h1>
        <p className="text-gray-400 mt-1">Persisted records of every automated and manual decision</p>
      </div>

      <div className="flex flex-wrap gap-2">
        {DECISION_TYPES.map((type) => (
          <button
            key={type}
            onClick={() => setSelectedType(type)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              selectedType === type ? 'bg-brand-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
            }`}
          >
            {type.charAt(0).toUpperCase() + type.slice(1)}
          </button>
        ))}
      </div>

      {!brandId ? (
        <div className="card text-center py-12">
          <GitBranch size={48} className="mx-auto text-gray-600 mb-4" />
          <p className="text-gray-400">Select a brand from the Brands page to view decisions.</p>
        </div>
      ) : isLoading ? (
        <div className="text-gray-500 text-center py-12">Loading decisions...</div>
      ) : !data?.items?.length ? (
        <div className="card text-center py-12">
          <p className="text-gray-400">No {selectedType} decisions recorded yet.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {data.items.map((decision: any) => (
            <div key={decision.id} className="card">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-white">
                    {decision.recommended_action} — {decision.confidence} confidence
                  </p>
                  <p className="text-sm text-gray-400 mt-1">{decision.explanation || 'No explanation recorded'}</p>
                </div>
                <span className="badge-blue">{decision.decision_mode}</span>
              </div>
              <div className="mt-3 text-xs text-gray-500 flex items-center gap-4">
                <span>Score: {decision.composite_score?.toFixed(2)}</span>
                <span>Actor: {decision.actor_type}</span>
                <span>{new Date(decision.decided_at).toLocaleString()}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
