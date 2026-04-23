'use client';

import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { phase7Api } from '@/lib/phase7-api';
import { Share2, Circle, ArrowRight } from 'lucide-react';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

const nodeTypeColors: Record<string, string> = {
  brand: 'bg-brand-600/25 text-brand-300',
  avatar: 'bg-purple-600/25 text-purple-300',
  offer: 'bg-emerald-600/25 text-emerald-300',
  account: 'bg-blue-600/25 text-blue-300',
  content: 'bg-amber-600/25 text-amber-300',
  topic: 'bg-rose-600/25 text-rose-300',
  sponsor: 'bg-cyan-600/25 text-cyan-300',
};

export default function KnowledgeGraphPage() {
  const [selectedBrandId, setSelectedBrandId] = useState('');

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) {
      setSelectedBrandId(String(brands[0].id));
    }
  }, [brands, selectedBrandId]);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['knowledge-graph', selectedBrandId],
    queryFn: () => phase7Api.knowledgeGraph(selectedBrandId).then((r) => r.data),
    enabled: Boolean(selectedBrandId),
  });

  const selectedBrand = useMemo(
    () => brands?.find((b) => String(b.id) === selectedBrandId),
    [brands, selectedBrandId]
  );

  const nodes = (data?.nodes || []) as any[];
  const edges = (data?.edges || []) as any[];

  const grouped = useMemo(() => {
    const map: Record<string, any[]> = {};
    nodes.forEach((n: any) => {
      const t = n.type || n.node_type || 'unknown';
      if (!map[t]) map[t] = [];
      map[t].push(n);
    });
    return map;
  }, [nodes]);

  if (brandsLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-96 bg-gray-800 rounded animate-pulse" />
        <div className="card py-12 text-center text-gray-500">Loading…</div>
      </div>
    );
  }

  if (brandsError) {
    return <div className="card border-red-900/50 text-red-300 py-8 text-center">{errMessage(brandsErr)}</div>;
  }

  if (!brands?.length) {
    return <div className="card text-center py-12 text-gray-500">Create a brand to explore the knowledge graph.</div>;
  }

  return (
    <div className="space-y-8 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Share2 className="text-brand-500" size={28} aria-hidden />
          Knowledge Graph Explorer
        </h1>
        <p className="text-gray-400 mt-1 max-w-3xl">
          Phase 7 entity graph — nodes and relationships across your brand ecosystem.
        </p>
      </div>

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          value={selectedBrandId}
          onChange={(e) => setSelectedBrandId(e.target.value)}
          aria-label="Select brand for knowledge graph"
        >
          {brands.map((b) => (
            <option key={b.id} value={String(b.id)}>
              {b.name}
            </option>
          ))}
        </select>
        {selectedBrand && <p className="text-sm text-gray-500 mt-2">Viewing: {selectedBrand.name}</p>}
      </div>

      {isLoading && <div className="card py-12 text-center text-gray-500">Building knowledge graph…</div>}
      {isError && <div className="card border-red-900/50 text-red-300 py-6">{errMessage(error)}</div>}

      {data && !isLoading && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="rounded-lg bg-gray-800/40 p-4 border border-gray-800">
              <p className="text-gray-500 text-xs uppercase">Total Nodes</p>
              <p className="text-2xl text-white mt-1">{nodes.length}</p>
            </div>
            <div className="rounded-lg bg-gray-800/40 p-4 border border-gray-800">
              <p className="text-gray-500 text-xs uppercase">Total Edges</p>
              <p className="text-2xl text-white mt-1">{edges.length}</p>
            </div>
            <div className="rounded-lg bg-gray-800/40 p-4 border border-gray-800">
              <p className="text-gray-500 text-xs uppercase">Node Types</p>
              <p className="text-2xl text-white mt-1">{Object.keys(grouped).length}</p>
            </div>
          </div>

          <div className="space-y-6">
            {Object.entries(grouped).map(([type, items]) => (
              <div key={type} className="card">
                <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                  <Circle size={10} className="text-brand-400" aria-hidden />
                  {type}
                  <span className="text-sm text-gray-500 font-normal">({items.length})</span>
                </h2>
                <ul className="space-y-2">
                  {items.map((n: any, i: number) => (
                    <li key={n.id || i} className="flex items-center gap-3 py-1.5 border-b border-gray-800 last:border-0 text-sm">
                      <span className={`inline-block px-2 py-0.5 rounded text-xs ${nodeTypeColors[type] || 'bg-gray-700 text-gray-300'}`}>
                        {type}
                      </span>
                      <span className="text-white">{n.label || n.name || n.id}</span>
                      {n.properties && (
                        <span className="text-xs text-gray-500 font-mono truncate max-w-xs">
                          {JSON.stringify(n.properties)}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          {edges.length > 0 && (
            <div className="card">
              <h2 className="text-lg font-semibold text-white mb-4">Relationships</h2>
              <ul className="space-y-2 max-h-[480px] overflow-y-auto">
                {edges.map((e: any, i: number) => (
                  <li key={e.id || i} className="flex items-center gap-2 text-sm py-1.5 border-b border-gray-800 last:border-0">
                    <span className="text-white">{e.source_label || e.source || e.from || '?'}</span>
                    <ArrowRight size={14} className="text-gray-600 shrink-0" aria-hidden />
                    <span className="text-brand-300 text-xs uppercase tracking-wide">{e.relationship || e.type || e.label || '—'}</span>
                    <ArrowRight size={14} className="text-gray-600 shrink-0" aria-hidden />
                    <span className="text-white">{e.target_label || e.target || e.to || '?'}</span>
                    {e.weight != null && <span className="text-xs text-gray-500 ml-auto">w:{e.weight}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {!nodes.length && !edges.length && (
            <div className="card text-center py-12 text-gray-500">
              No graph data yet. Run Phase 7 recompute to populate the knowledge graph.
            </div>
          )}
        </>
      )}
    </div>
  );
}
