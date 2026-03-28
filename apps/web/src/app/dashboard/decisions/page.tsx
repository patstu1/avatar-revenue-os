'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi, decisionsApi } from '@/lib/api';
import { analyticsApi } from '@/lib/analytics-api';
import { AlertTriangle, Shield, XCircle, GitBranch } from 'lucide-react';

type Brand = { id: string; name: string };

type LeakRow = {
  type: string;
  entity: string;
  issue: string;
  severity: string;
  detail: string;
  actions: string[];
};

const DECISION_TYPES = [
  'opportunity',
  'monetization',
  'publish',
  'suppression',
  'scale',
  'allocation',
  'expansion',
];

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

function severityBadgeClass(sev: string) {
  const s = (sev || '').toLowerCase();
  if (s === 'critical') return 'badge-red';
  if (s === 'warning') return 'badge-yellow';
  return 'badge-blue';
}

function typeBadgeClass(t: string) {
  const s = (t || '').toLowerCase();
  if (s === 'suppression') return 'badge-red';
  if (s === 'bottleneck') return 'badge-yellow';
  return 'badge-blue';
}

export default function DecisionsSuppressionsPage() {
  const queryClient = useQueryClient();
  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [selectedType, setSelectedType] = useState('suppression');
  const [suppressionEval, setSuppressionEval] = useState<{ suppressions: unknown[]; count: number } | null>(null);

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

  useEffect(() => {
    setSuppressionEval(null);
  }, [selectedBrandId]);

  const {
    data: leaks,
    isLoading: leaksLoading,
    isError: leaksError,
    error: leaksErr,
  } = useQuery({
    queryKey: ['analytics-revenue-leaks', selectedBrandId],
    queryFn: () => analyticsApi.revenueLeaks(selectedBrandId).then((r) => r.data as LeakRow[]),
    enabled: Boolean(selectedBrandId),
  });

  const {
    data: decisionsData,
    isLoading: decisionsLoading,
    isError: decisionsError,
    error: decisionsErr,
  } = useQuery({
    queryKey: ['decisions', selectedType, selectedBrandId],
    queryFn: () =>
      selectedBrandId ? decisionsApi.list(selectedType, selectedBrandId).then((r) => r.data as { items?: unknown[] }) : null,
    enabled: Boolean(selectedBrandId),
  });

  const evaluateMutation = useMutation({
    mutationFn: () => analyticsApi.evaluateSuppressions(selectedBrandId).then((r) => r.data as { suppressions: unknown[]; count: number }),
    onSuccess: (data) => {
      setSuppressionEval(data);
      queryClient.invalidateQueries({ queryKey: ['analytics-revenue-leaks', selectedBrandId] });
      queryClient.invalidateQueries({ queryKey: ['decisions', 'suppression', selectedBrandId] });
    },
  });

  const selectedBrand = useMemo(
    () => brands?.find((b) => String(b.id) === selectedBrandId),
    [brands, selectedBrandId]
  );

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
        <h1 className="text-2xl font-bold text-white">Suppressions and leaks</h1>
        <div className="card border-red-900/50 text-red-300 py-8 text-center">Failed to load brands: {errMessage(brandsErr)}</div>
      </div>
    );
  }

  if (!brands?.length) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Shield className="text-brand-500" size={28} aria-hidden />
            Suppression and leaks
          </h1>
          <p className="text-gray-400 mt-1">Revenue leaks, suppression evaluation, and decision history</p>
        </div>
        <div className="card text-center py-12">
          <GitBranch className="mx-auto text-gray-600 mb-4" size={48} aria-hidden />
          <p className="text-gray-500">No brands yet. Create a brand to continue.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Shield className="text-brand-500" size={28} aria-hidden />
            Suppression and leaks
          </h1>
          <p className="text-gray-400 mt-1">Surface revenue leaks, run suppression evaluation, and browse decisions</p>
        </div>
        <button
          type="button"
          className="btn-primary inline-flex items-center justify-center gap-2 shrink-0 disabled:opacity-50"
          disabled={!selectedBrandId || evaluateMutation.isPending}
          onClick={() => evaluateMutation.mutate()}
        >
          <Shield size={18} className={evaluateMutation.isPending ? 'animate-pulse' : ''} aria-hidden />
          {evaluateMutation.isPending ? 'Evaluating…' : 'Evaluate Suppressions'}
        </button>
      </div>

      <div className="card">
        <label htmlFor="decisions-brand-select" className="stat-label block mb-2">
          Brand
        </label>
        <select
          id="decisions-brand-select"
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

      {evaluateMutation.isError && (
        <div className="card border-red-900/50 text-red-300 text-sm flex items-start gap-2">
          <XCircle size={18} className="shrink-0 mt-0.5" aria-hidden />
          {errMessage(evaluateMutation.error)}
        </div>
      )}

      {suppressionEval && (
        <div className="card border-emerald-900/40">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2 mb-2">
            <Shield size={20} className="text-emerald-400" aria-hidden />
            Suppression evaluation
          </h3>
          <p className="text-sm text-gray-400">
            Created or updated <span className="text-white font-medium">{suppressionEval.count}</span> suppression
            {suppressionEval.count === 1 ? '' : 's'}.
          </p>
          {Array.isArray(suppressionEval.suppressions) && suppressionEval.suppressions.length > 0 && (
            <ul className="mt-3 space-y-2 text-sm text-gray-300">
              {(suppressionEval.suppressions as { title?: string; reason?: string; detail?: string }[]).map((s, i) => (
                <li key={i} className="bg-gray-800/50 rounded-lg px-3 py-2">
                  <span className="font-medium text-white">{s.title}</span>
                  {s.reason && <span className="text-gray-500 ml-2">({s.reason})</span>}
                  {s.detail && <p className="text-xs text-gray-500 mt-1">{s.detail}</p>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <AlertTriangle size={22} className="text-amber-400" aria-hidden />
          Revenue leaks
        </h2>
        {leaksLoading && <p className="text-gray-500 text-sm py-8 text-center">Loading leaks…</p>}
        {leaksError && !leaksLoading && (
          <p className="text-red-300 text-sm py-4 text-center">Failed to load leaks: {errMessage(leaksErr)}</p>
        )}
        {!leaksLoading && !leaksError && (!leaks || leaks.length === 0) && (
          <p className="text-gray-500 text-sm py-8 text-center">No revenue leaks detected for this brand.</p>
        )}
        {!leaksLoading && !leaksError && leaks && leaks.length > 0 && (
          <div className="space-y-4">
            {leaks.map((leak, i) => (
              <div key={`${leak.type}-${leak.entity}-${i}`} className="card-hover space-y-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={typeBadgeClass(leak.type)}>{leak.type}</span>
                    <span className="text-white font-medium">{leak.entity}</span>
                  </div>
                  <span className={severityBadgeClass(leak.severity)}>{leak.severity}</span>
                </div>
                <p className="text-sm text-gray-400">
                  <span className="text-gray-500">Issue: </span>
                  {String(leak.issue)}
                </p>
                <p className="text-sm text-gray-500">{leak.detail}</p>
                {leak.actions?.length > 0 && (
                  <div>
                    <p className="stat-label mb-2">Recommended actions</p>
                    <ul className="list-disc list-inside text-sm text-gray-300 space-y-1">
                      {leak.actions.map((a, j) => (
                        <li key={j}>{a}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div>
        <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
          <GitBranch size={22} className="text-brand-500" aria-hidden />
          Decision log
        </h2>
        <div className="flex flex-wrap gap-2 mb-4">
          {DECISION_TYPES.map((type) => (
            <button
              key={type}
              type="button"
              onClick={() => setSelectedType(type)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                selectedType === type ? 'bg-brand-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
              }`}
            >
              {type.charAt(0).toUpperCase() + type.slice(1)}
            </button>
          ))}
        </div>

        {decisionsLoading && <div className="card text-center py-12 text-gray-500">Loading decisions…</div>}

        {decisionsError && !decisionsLoading && (
          <div className="card border-red-900/50 text-red-300 py-8 text-center">
            Failed to load decisions: {errMessage(decisionsErr)}
          </div>
        )}

        {!decisionsLoading && !decisionsError && !decisionsData?.items?.length && (
          <div className="card text-center py-12">
            <p className="text-gray-500">No {selectedType} decisions recorded for this brand yet.</p>
          </div>
        )}

        {!decisionsLoading && !decisionsError && decisionsData?.items && decisionsData.items.length > 0 && (
          <div className="space-y-3">
            {(decisionsData.items as Array<Record<string, unknown>>).map((decision) => (
              <div key={String(decision.id)} className="card">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-medium text-white">
                      {String(decision.recommended_action ?? decision.recommendedAction ?? '—')} —{' '}
                      {String(decision.confidence ?? '—')} confidence
                    </p>
                    <p className="text-sm text-gray-400 mt-1">
                      {String(decision.explanation ?? 'No explanation recorded')}
                    </p>
                  </div>
                  <span className="badge-blue shrink-0">{String(decision.decision_mode ?? decision.decisionMode ?? '')}</span>
                </div>
                <div className="mt-3 text-xs text-gray-500 flex flex-wrap items-center gap-4">
                  {decision.composite_score != null && (
                    <span>Score: {Number(decision.composite_score).toFixed(2)}</span>
                  )}
                  {decision.actor_type != null && <span>Actor: {String(decision.actor_type)}</span>}
                  {decision.decided_at != null && (
                    <span>{new Date(String(decision.decided_at)).toLocaleString()}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
