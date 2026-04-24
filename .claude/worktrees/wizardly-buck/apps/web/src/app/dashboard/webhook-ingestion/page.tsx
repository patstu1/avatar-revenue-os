'use client';

import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { lec2Api } from '@/lib/live-execution-phase2-api';
import { RefreshCw, Webhook } from 'lucide-react';

type Brand = { id: string; name: string };

type WebhookEventRow = {
  id: string;
  source: string;
  event_type: string;
  processed: boolean;
  processing_result?: string | null;
};

type IngestionRow = {
  id: string;
  source: string;
  source_category: string;
  events_received: number;
  events_processed: number;
  status: string;
};

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

function asList<T>(data: unknown): T[] {
  return Array.isArray(data) ? (data as T[]) : [];
}

export default function WebhookIngestionPage() {
  const qc = useQueryClient();
  const [brandId, setBrandId] = useState('');

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(String(brands[0].id));
  }, [brands, brandId]);

  const { data: eventsRaw, isLoading: evLoading } = useQuery({
    queryKey: ['lec2-webhook-events', brandId],
    queryFn: () => lec2Api.webhookEvents(brandId).then((r) => r.data),
    enabled: Boolean(brandId),
  });

  const { data: ingestionsRaw, isLoading: ingLoading } = useQuery({
    queryKey: ['lec2-event-ingestions', brandId],
    queryFn: () => lec2Api.eventIngestions(brandId).then((r) => r.data),
    enabled: Boolean(brandId),
  });

  const recomputeMut = useMutation({
    mutationFn: () => lec2Api.recomputeIngestions(brandId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['lec2-event-ingestions', brandId] });
      qc.invalidateQueries({ queryKey: ['lec2-webhook-events', brandId] });
    },
  });

  const events = asList<WebhookEventRow>(eventsRaw);
  const ingestions = asList<IngestionRow>(ingestionsRaw);

  if (brandsLoading) {
    return <div className="card py-12 text-center text-gray-500">Loading…</div>;
  }
  if (brandsError) {
    return <div className="card border-red-900/50 text-red-300 py-8 text-center">{errMessage(brandsErr)}</div>;
  }
  if (!brands?.length) {
    return <div className="card text-center py-12 text-gray-500">Create a brand to use webhook and event ingestion.</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Webhook className="text-brand-500" size={28} aria-hidden />
            Webhook &amp; Event Ingestion
          </h1>
          <p className="text-gray-400 mt-1 max-w-3xl">
            Raw webhook events and external ingestion summaries for Live Execution Phase 2.
          </p>
        </div>
        <button
          type="button"
          className="btn-primary flex items-center gap-2 disabled:opacity-50 shrink-0"
          disabled={!brandId || recomputeMut.isPending}
          onClick={() => recomputeMut.mutate()}
        >
          <RefreshCw size={16} className={recomputeMut.isPending ? 'animate-spin' : ''} />
          Recompute ingestions
        </button>
      </div>

      {recomputeMut.isError && (
        <div className="card border-amber-900/50 text-amber-200 text-sm">{errMessage(recomputeMut.error)}</div>
      )}
      {recomputeMut.isSuccess && (
        <div className="card border-emerald-900/50 text-emerald-300 text-sm">Recompute finished.</div>
      )}

      <div className="card max-w-xl">
        <label className="stat-label block mb-2 text-gray-400 text-xs font-medium uppercase tracking-wider">Brand</label>
        <select
          className="input-field w-full"
          value={brandId}
          onChange={(e) => setBrandId(e.target.value)}
          aria-label="Select brand"
        >
          {brands.map((b) => (
            <option key={b.id} value={String(b.id)}>
              {b.name}
            </option>
          ))}
        </select>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-3">Webhook events</h2>
        {evLoading ? (
          <p className="text-gray-500">Loading events…</p>
        ) : events.length === 0 ? (
          <p className="text-gray-500">No webhook events for this brand yet.</p>
        ) : (
          <div className="overflow-x-auto border border-gray-800 rounded-lg">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-left text-gray-400">
                  <th className="p-3 font-medium">Source</th>
                  <th className="p-3 font-medium">Event type</th>
                  <th className="p-3 font-medium">Processed</th>
                  <th className="p-3 font-medium">Result</th>
                </tr>
              </thead>
              <tbody>
                {events.map((row) => (
                  <tr key={row.id} className="border-b border-gray-800/80 text-gray-300">
                    <td className="p-3 text-white">{row.source}</td>
                    <td className="p-3">{row.event_type}</td>
                    <td className="p-3">{row.processed ? 'Yes' : 'No'}</td>
                    <td className="p-3 text-gray-400">{row.processing_result ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-3">Event ingestion summaries</h2>
        {ingLoading ? (
          <p className="text-gray-500">Loading ingestions…</p>
        ) : ingestions.length === 0 ? (
          <p className="text-gray-500">No ingestion batches yet. Run recompute to generate summaries.</p>
        ) : (
          <div className="overflow-x-auto border border-gray-800 rounded-lg">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-left text-gray-400">
                  <th className="p-3 font-medium">Source</th>
                  <th className="p-3 font-medium">Category</th>
                  <th className="p-3 font-medium">Received</th>
                  <th className="p-3 font-medium">Processed</th>
                  <th className="p-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {ingestions.map((row) => (
                  <tr key={row.id} className="border-b border-gray-800/80 text-gray-300">
                    <td className="p-3 text-white">{row.source}</td>
                    <td className="p-3">{row.source_category}</td>
                    <td className="p-3">{row.events_received}</td>
                    <td className="p-3">{row.events_processed}</td>
                    <td className="p-3 text-gray-400">{row.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
