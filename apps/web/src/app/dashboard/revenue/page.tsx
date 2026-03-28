'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { discoveryApi } from '@/lib/discovery-api';
import { ShoppingBag, Target, Zap } from 'lucide-react';

type Brand = { id: string; name: string };

type TopicCandidate = {
  id: string;
  title: string;
  keywords?: string[] | null;
  relevance_score: number;
  trend_velocity: number;
};

type OfferFitRow = {
  offer_id: string;
  offer_name: string;
  fit_score: number;
  confidence: string;
  explanation: string;
};

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

function barTone(v: number) {
  if (v > 0.6) return 'bg-emerald-500';
  if (v > 0.3) return 'bg-amber-500';
  return 'bg-red-500';
}

function confidenceBadge(c: string) {
  const s = (c || '').toLowerCase();
  if (s.includes('high') || s === 'strong') return 'badge-green';
  if (s.includes('med') || s.includes('moderate')) return 'badge-yellow';
  return 'badge-red';
}

export default function RevenuePage() {
  const queryClient = useQueryClient();
  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);
  const [fitByTopic, setFitByTopic] = useState<Record<string, OfferFitRow[]>>({});

  const {
    data: brands,
    isLoading: brandsLoading,
    isError: brandsError,
    error: brandsErr,
  } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) {
      setSelectedBrandId(String(brands[0].id));
    }
  }, [brands, selectedBrandId]);

  const {
    data: signalsData,
    isLoading: signalsLoading,
    isError: signalsError,
    error: signalsErr,
  } = useQuery({
    queryKey: ['discovery-signals', selectedBrandId],
    queryFn: () => discoveryApi.getSignals(selectedBrandId).then((r) => r.data as { topic_candidates: TopicCandidate[] }),
    enabled: Boolean(selectedBrandId),
  });

  const topics = signalsData?.topic_candidates ?? [];

  useEffect(() => {
    if (topics.length && !selectedTopicId) {
      setSelectedTopicId(String(topics[0].id));
    }
    if (topics.length && selectedTopicId && !topics.some((t) => String(t.id) === selectedTopicId)) {
      setSelectedTopicId(String(topics[0].id));
    }
  }, [topics, selectedTopicId]);

  const offerFitMutation = useMutation({
    mutationFn: (topicId: string) => discoveryApi.offerFit(selectedBrandId, topicId).then((r) => r.data as OfferFitRow[]),
    onSuccess: (data, topicId) => {
      setFitByTopic((prev) => ({ ...prev, [topicId]: data }));
      queryClient.invalidateQueries({ queryKey: ['discovery-signals', selectedBrandId] });
    },
  });

  const selectedBrand = useMemo(
    () => brands?.find((b) => String(b.id) === selectedBrandId),
    [brands, selectedBrandId]
  );

  const selectedTopic = topics.find((t) => String(t.id) === selectedTopicId);
  const fitResults = selectedTopicId ? fitByTopic[selectedTopicId] : undefined;
  const computingSelected =
    Boolean(selectedTopicId) &&
    offerFitMutation.isPending &&
    offerFitMutation.variables === selectedTopicId;

  if (brandsLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-64 bg-gray-800 rounded animate-pulse" />
        <div className="card py-12 text-center text-gray-500">Loading brands…</div>
      </div>
    );
  }

  if (brandsError) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Offer Fit Explorer</h1>
        <div className="card border-red-900/50 text-red-300 py-8 text-center">Failed to load brands: {errMessage(brandsErr)}</div>
      </div>
    );
  }

  if (!brands?.length) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <ShoppingBag className="text-brand-500" size={28} aria-hidden />
            Offer Fit Explorer
          </h1>
          <p className="text-gray-400 mt-1">Evaluate how each offer matches topic candidates</p>
        </div>
        <div className="card text-center py-12">
          <Target className="mx-auto text-gray-600 mb-4" size={48} aria-hidden />
          <p className="text-gray-500">No brands yet. Create a brand to explore offer fit.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <ShoppingBag className="text-brand-500" size={28} aria-hidden />
          Offer Fit Explorer
        </h1>
        <p className="text-gray-400 mt-1">Evaluate how each offer matches topic candidates</p>
      </div>

      <div className="card">
        <label htmlFor="revenue-brand-select" className="stat-label block mb-2">
          Brand
        </label>
        <select
          id="revenue-brand-select"
          className="input-field w-full max-w-md"
          value={selectedBrandId}
          onChange={(e) => {
            setSelectedBrandId(e.target.value);
            setSelectedTopicId(null);
            setFitByTopic({});
          }}
        >
          {brands.map((b) => (
            <option key={b.id} value={String(b.id)}>
              {b.name}
            </option>
          ))}
        </select>
        {selectedBrand && <p className="text-sm text-gray-500 mt-2">Viewing: {selectedBrand.name}</p>}
      </div>

      {signalsLoading && <div className="card text-center py-12 text-gray-500">Loading topics…</div>}

      {signalsError && !signalsLoading && (
        <div className="card border-red-900/50 text-red-300 py-8 text-center">Failed to load signals: {errMessage(signalsErr)}</div>
      )}

      {!signalsLoading && !signalsError && topics.length === 0 && (
        <div className="card text-center py-12">
          <Zap className="mx-auto text-gray-600 mb-4" size={40} aria-hidden />
          <p className="text-gray-500">No topic candidates yet. Ingest signals for this brand first.</p>
        </div>
      )}

      {!signalsLoading && !signalsError && topics.length > 0 && (
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
          <div className="xl:col-span-4 space-y-3">
            <h2 className="stat-label">Topics</h2>
            <ul className="space-y-2">
              {topics.map((t) => {
                const active = String(t.id) === selectedTopicId;
                const tid = String(t.id);
                const computing = offerFitMutation.isPending && offerFitMutation.variables === tid;
                return (
                  <li key={t.id}>
                    <div
                      className={`rounded-lg border px-4 py-3 transition-colors ${
                        active
                          ? 'border-brand-600 bg-brand-900/20 text-white'
                          : 'border-gray-800 bg-gray-900/50 text-gray-300'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => setSelectedTopicId(tid)}
                        className="w-full text-left"
                      >
                        <span className="font-medium block">{t.title}</span>
                        <span className="text-xs text-gray-500 mt-1 block">
                          Relevance {(Number(t.relevance_score) * 100).toFixed(0)}% · Velocity{' '}
                          {(Number(t.trend_velocity) * 100).toFixed(0)}%
                        </span>
                      </button>
                      <button
                        type="button"
                        className="btn-secondary text-xs mt-3 w-full sm:w-auto disabled:opacity-50"
                        disabled={offerFitMutation.isPending}
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedTopicId(tid);
                          offerFitMutation.mutate(tid);
                        }}
                      >
                        <span className="inline-flex items-center justify-center gap-1.5">
                          <Zap size={14} className={computing ? 'animate-pulse' : ''} aria-hidden />
                          {computing ? 'Computing…' : 'Compute Fit'}
                        </span>
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>

          <div className="xl:col-span-8 space-y-4">
            {selectedTopic && (
              <div className="card">
                <h3 className="text-lg font-semibold text-white">{selectedTopic.title}</h3>
                <p className="text-sm text-gray-500 mt-1">Use Compute Fit on a topic in the list to load offer match results here.</p>
                {selectedTopic.keywords && selectedTopic.keywords.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-3">
                    {selectedTopic.keywords.map((k, i) => (
                      <span key={`${selectedTopic.id}-kw-${i}`} className="badge-blue">
                        {typeof k === 'string' ? k : String(k)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {offerFitMutation.isError && (
              <div className="card border-red-900/50 text-red-300 text-sm">{errMessage(offerFitMutation.error)}</div>
            )}

            {computingSelected && (
              <div className="card text-gray-500 text-sm">Computing offer fit for this topic…</div>
            )}

            {fitResults && fitResults.length === 0 && (
              <div className="card text-gray-500 text-sm">No offer fit rows returned. Add offers for this brand.</div>
            )}

            {fitResults && fitResults.length > 0 && (
              <div className="grid gap-4">
                {fitResults.map((row) => {
                  const score = Math.min(1, Math.max(0, Number(row.fit_score)));
                  const pct = score * 100;
                  return (
                    <div key={row.offer_id} className="card-hover space-y-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <h4 className="text-white font-semibold">{row.offer_name}</h4>
                        <span className={confidenceBadge(row.confidence)}>{row.confidence}</span>
                      </div>
                      <div className="space-y-1">
                        <div className="flex justify-between text-xs text-gray-400">
                          <span>Fit score</span>
                          <span>{pct.toFixed(0)}%</span>
                        </div>
                        <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
                          <div
                            className={`h-full rounded-full ${barTone(score)}`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                      <p className="text-sm text-gray-400">{row.explanation}</p>
                    </div>
                  );
                })}
              </div>
            )}

            {selectedTopicId && fitResults === undefined && !computingSelected && (
              <div className="card text-gray-500 text-sm flex items-center gap-2">
                <Target size={18} className="text-gray-600 shrink-0" aria-hidden />
                Select a topic and click Compute Fit to see offer match scores.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
