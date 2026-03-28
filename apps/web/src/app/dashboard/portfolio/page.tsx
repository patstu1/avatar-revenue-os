'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { discoveryApi } from '@/lib/discovery-api';
import { BarChart3, DollarSign, TrendingUp } from 'lucide-react';

type Brand = { id: string; name: string };

type TopicCandidate = {
  id: string;
  title: string;
};

type ProfitForecast = {
  id: string;
  estimated_impressions: number;
  estimated_ctr: number;
  estimated_conversion_rate: number;
  estimated_revenue: number;
  estimated_cost: number;
  estimated_profit: number;
  estimated_rpm: number;
  estimated_epc: number;
  confidence: string;
  explanation?: string | null;
};

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

function formatMoney(n: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(n ?? 0);
}

function confidenceBadge(c: string) {
  const s = (c || '').toLowerCase();
  if (s.includes('high') || s === 'strong') return 'badge-green';
  if (s.includes('med') || s.includes('moderate')) return 'badge-yellow';
  return 'badge-red';
}

export default function PortfolioPage() {
  const queryClient = useQueryClient();
  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [forecastingTopicId, setForecastingTopicId] = useState<string | null>(null);

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

  const {
    data: forecasts,
    isLoading: forecastsLoading,
    isError: forecastsError,
    error: forecastsErr,
  } = useQuery({
    queryKey: ['discovery-forecasts', selectedBrandId],
    queryFn: () => discoveryApi.getForecasts(selectedBrandId).then((r) => r.data as ProfitForecast[]),
    enabled: Boolean(selectedBrandId),
  });

  const forecastMutation = useMutation({
    mutationFn: (topicId: string) => discoveryApi.forecast(selectedBrandId, topicId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['discovery-forecasts', selectedBrandId] });
      queryClient.invalidateQueries({ queryKey: ['discovery-signals', selectedBrandId] });
      setForecastingTopicId(null);
    },
    onError: () => {
      setForecastingTopicId(null);
    },
  });

  const selectedBrand = useMemo(
    () => brands?.find((b) => String(b.id) === selectedBrandId),
    [brands, selectedBrandId]
  );

  const topics = signalsData?.topic_candidates ?? [];

  const runForecast = (topicId: string) => {
    setForecastingTopicId(topicId);
    forecastMutation.mutate(topicId);
  };

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
        <h1 className="text-2xl font-bold text-white">Profit Forecast Dashboard</h1>
        <div className="card border-red-900/50 text-red-300 py-8 text-center">Failed to load brands: {errMessage(brandsErr)}</div>
      </div>
    );
  }

  if (!brands?.length) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <DollarSign className="text-brand-500" size={28} aria-hidden />
            Profit Forecast Dashboard
          </h1>
          <p className="text-gray-400 mt-1">Expected profit forecasts for scored opportunities</p>
        </div>
        <div className="card text-center py-12">
          <BarChart3 className="mx-auto text-gray-600 mb-4" size={48} aria-hidden />
          <p className="text-gray-500">No brands yet. Create a brand to view forecasts.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <DollarSign className="text-brand-500" size={28} aria-hidden />
          Profit Forecast Dashboard
        </h1>
        <p className="text-gray-400 mt-1">Expected profit forecasts for scored opportunities</p>
      </div>

      <div className="card">
        <label htmlFor="portfolio-brand-select" className="stat-label block mb-2">
          Brand
        </label>
        <select
          id="portfolio-brand-select"
          className="input-field w-full max-w-md"
          value={selectedBrandId}
          onChange={(e) => setSelectedBrandId(e.target.value)}
        >
          {brands.map((b) => (
            <option key={b.id} value={String(b.id)}>
              {b.name}
            </option>
          ))}
        </select>
        {selectedBrand && <p className="text-sm text-gray-500 mt-2">Viewing: {selectedBrand.name}</p>}
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
          <TrendingUp size={20} className="text-brand-500" aria-hidden />
          Topics — run forecast
        </h2>
        {signalsLoading && <p className="text-gray-500 text-sm">Loading topics…</p>}
        {signalsError && (
          <p className="text-red-300 text-sm">Failed to load topics: {errMessage(signalsErr)}</p>
        )}
        {!signalsLoading && !signalsError && topics.length === 0 && (
          <p className="text-gray-500 text-sm">No topic candidates. Ingest signals first.</p>
        )}
        {!signalsLoading && !signalsError && topics.length > 0 && (
          <ul className="divide-y divide-gray-800 border border-gray-800 rounded-lg overflow-hidden">
            {topics.map((t) => (
              <li key={t.id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 px-4 py-3 bg-gray-900/30">
                <span className="text-white font-medium">{t.title}</span>
                <button
                  type="button"
                  className="btn-secondary text-sm shrink-0 disabled:opacity-50"
                  disabled={forecastMutation.isPending && forecastingTopicId === String(t.id)}
                  onClick={() => runForecast(String(t.id))}
                >
                  {forecastMutation.isPending && forecastingTopicId === String(t.id) ? 'Forecasting…' : 'Forecast'}
                </button>
              </li>
            ))}
          </ul>
        )}
        {forecastMutation.isError && (
          <p className="text-red-300 text-sm mt-3">{errMessage(forecastMutation.error)}</p>
        )}
      </div>

      {forecastsLoading && <div className="card text-center py-12 text-gray-500">Loading forecasts…</div>}

      {forecastsError && !forecastsLoading && (
        <div className="card border-red-900/50 text-red-300 py-8 text-center">Failed to load forecasts: {errMessage(forecastsErr)}</div>
      )}

      {!forecastsLoading && !forecastsError && forecasts?.length === 0 && (
        <div className="card text-center py-12">
          <BarChart3 className="mx-auto text-gray-600 mb-4" size={40} aria-hidden />
          <p className="text-gray-500">No profit forecasts yet. Use Forecast on a topic to generate estimates.</p>
        </div>
      )}

      {!forecastsLoading && !forecastsError && forecasts && forecasts.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {forecasts.map((f) => (
            <div key={f.id} className="card-hover space-y-4">
              <div className="flex items-start justify-between gap-2">
                <span className={confidenceBadge(f.confidence)}>{f.confidence}</span>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="stat-label">Impressions</p>
                  <p className="stat-value text-white text-xl">{f.estimated_impressions.toLocaleString()}</p>
                </div>
                <div>
                  <p className="stat-label">Revenue</p>
                  <p className="stat-value text-emerald-400 text-xl">{formatMoney(f.estimated_revenue)}</p>
                </div>
                <div>
                  <p className="stat-label">Cost</p>
                  <p className="stat-value text-amber-400 text-xl">{formatMoney(f.estimated_cost)}</p>
                </div>
                <div>
                  <p className="stat-label">Profit</p>
                  <p className="stat-value text-brand-400 text-xl">{formatMoney(f.estimated_profit)}</p>
                </div>
                <div>
                  <p className="stat-label">RPM</p>
                  <p className="stat-value text-white text-lg">{formatMoney(f.estimated_rpm)}</p>
                </div>
                <div>
                  <p className="stat-label">EPC</p>
                  <p className="stat-value text-white text-lg">{formatMoney(f.estimated_epc)}</p>
                </div>
              </div>
              <div className="text-xs text-gray-500 border-t border-gray-800 pt-3 space-y-1">
                <p>
                  CTR {(f.estimated_ctr <= 1 ? f.estimated_ctr * 100 : f.estimated_ctr).toFixed(2)}% · Conv{' '}
                  {(f.estimated_conversion_rate <= 1 ? f.estimated_conversion_rate * 100 : f.estimated_conversion_rate).toFixed(2)}%
                </p>
                {f.explanation && <p className="text-gray-400">{f.explanation}</p>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
