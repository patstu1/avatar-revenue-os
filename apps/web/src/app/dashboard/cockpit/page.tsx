'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { discoveryApi } from '@/lib/discovery-api';
import { Target, TrendingUp, Zap, AlertTriangle, BarChart3, RefreshCw, ArrowRight } from 'lucide-react';

export default function OpportunityQueuePage() {
  const queryClient = useQueryClient();
  const [brandId, setBrandId] = useState('');

  const { data: brands } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then(r => r.data),
  });

  if (brands?.length && !brandId) setBrandId(brands[0].id);

  const { data: queue, isLoading } = useQuery({
    queryKey: ['opp-queue', brandId],
    queryFn: () => discoveryApi.getQueue(brandId).then(r => r.data),
    enabled: !!brandId,
  });

  const { data: recs } = useQuery({
    queryKey: ['recommendations', brandId],
    queryFn: () => discoveryApi.getRecommendations(brandId).then(r => r.data),
    enabled: !!brandId,
  });

  const recompute = useMutation({
    mutationFn: () => discoveryApi.recomputeOpportunities(brandId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['opp-queue', brandId] });
      queryClient.invalidateQueries({ queryKey: ['recommendations', brandId] });
    },
  });

  const triggerBrief = useMutation({
    mutationFn: (topicId: string) => discoveryApi.triggerBrief(brandId, topicId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['opp-queue', brandId] }),
  });

  const actionColor: Record<string, string> = {
    scale: 'badge-green', maintain: 'badge-blue', monitor: 'badge-yellow',
    reduce: 'badge-yellow', suppress: 'badge-red', experiment: 'badge-blue',
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Opportunity Queue</h1>
          <p className="text-gray-400 mt-1">Ranked recommendations with scoring, monetization path, and brief trigger</p>
        </div>
        <div className="flex items-center gap-3">
          <select className="input-field" value={brandId} onChange={e => setBrandId(e.target.value)}>
            {brands?.map((b: any) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
          <button onClick={() => recompute.mutate()} className="btn-primary flex items-center gap-2" disabled={recompute.isPending}>
            <RefreshCw size={14} className={recompute.isPending ? 'animate-spin' : ''} />
            {recompute.isPending ? 'Scoring...' : 'Recompute'}
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="text-gray-500 text-center py-12">Loading opportunity queue...</div>
      ) : !queue?.length ? (
        <div className="card text-center py-12">
          <Target size={48} className="mx-auto text-gray-600 mb-4" />
          <p className="text-gray-400">No opportunities scored yet. Ingest signals and run scoring.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {queue.map((item: any) => (
            <div key={item.id} className="card-hover">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-brand-600/20 flex items-center justify-center text-brand-300 text-sm font-bold">
                    {item.rank}
                  </div>
                  <div>
                    <p className="text-white font-medium">Score: {item.composite_score.toFixed(3)}</p>
                    <p className="text-sm text-gray-400 mt-0.5 max-w-xl">{item.explanation || 'No explanation'}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={actionColor[item.recommended_action] || 'badge-blue'}>
                    {item.recommended_action}
                  </span>
                  <span className="badge-blue">{item.classification}</span>
                  {item.topic_candidate_id && (
                    <button
                      onClick={() => triggerBrief.mutate(item.topic_candidate_id)}
                      className="btn-secondary text-xs flex items-center gap-1"
                      disabled={item.is_actioned}
                    >
                      <ArrowRight size={12} /> {item.is_actioned ? 'Triggered' : 'Trigger Brief'}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
