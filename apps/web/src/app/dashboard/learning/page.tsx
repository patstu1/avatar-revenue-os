'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchBrainMemory, recomputeBrainMemory } from '@/lib/brain-phase-a-api';
import { fetchPatterns, recomputePatterns } from '@/lib/pattern-memory-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Brain, RefreshCcw } from 'lucide-react';

interface MemoryEntry {
  id: string;
  entry_type: string;
  scope_type: string;
  platform: string | null;
  summary: string;
  confidence: number;
  created_at: string | null;
}

interface MemoryLink {
  id: string;
  link_type: string;
  strength: number;
}

interface WinningPattern {
  id: string;
  pattern_key: string;
  performance_band: string;
  confidence: number;
  reuse_count: number;
}

export default function LearningMemoryPage() {
  const brandId = useBrandId();
  const [entries, setEntries] = useState<MemoryEntry[]>([]);
  const [links, setLinks] = useState<MemoryLink[]>([]);
  const [patterns, setPatterns] = useState<WinningPattern[]>([]);
  const [loading, setLoading] = useState(false);
  const [recomputing, setRecomputing] = useState(false);
  const [lastConsolidation, setLastConsolidation] = useState<string | null>(null);

  useEffect(() => {
    if (!brandId) return;
    setLoading(true);
    Promise.all([
      fetchBrainMemory(brandId, '').catch(() => ({ entries: [], links: [] })),
      fetchPatterns(brandId).catch(() => []),
    ]).then(([memData, patData]) => {
      const memEntries = memData.entries ?? [];
      setEntries(memEntries);
      setLinks(memData.links ?? []);
      setPatterns(Array.isArray(patData) ? patData : []);
      if (memEntries.length > 0) {
        const sorted = [...memEntries].sort((a, b) =>
          (b.created_at ?? '').localeCompare(a.created_at ?? '')
        );
        setLastConsolidation(sorted[0]?.created_at ?? null);
      }
    }).finally(() => setLoading(false));
  }, [brandId]);

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    try {
      await Promise.all([
        recomputeBrainMemory(brandId, '').catch(() => null),
        recomputePatterns(brandId).catch(() => null),
      ]);
      const [memData, patData] = await Promise.all([
        fetchBrainMemory(brandId, '').catch(() => ({ entries: [], links: [] })),
        fetchPatterns(brandId).catch(() => []),
      ]);
      const memEntries = memData.entries ?? [];
      setEntries(memEntries);
      setLinks(memData.links ?? []);
      setPatterns(Array.isArray(patData) ? patData : []);
      if (memEntries.length > 0) {
        const sorted = [...memEntries].sort((a, b) =>
          (b.created_at ?? '').localeCompare(a.created_at ?? '')
        );
        setLastConsolidation(sorted[0]?.created_at ?? null);
      }
    } finally {
      setRecomputing(false);
    }
  };

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand to view learning data.</div>;

  const avgConfidence = entries.length > 0
    ? entries.reduce((sum, e) => sum + e.confidence, 0) / entries.length
    : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Brain size={28} className="text-brand-400" />
          <div>
            <h1 className="text-2xl font-bold">Memory / Learning</h1>
            <p className="text-sm text-gray-400">
              Consolidated learning signals, pattern memory, and performance insights
            </p>
          </div>
        </div>
        <button
          onClick={handleRecompute}
          disabled={recomputing}
          className="flex items-center gap-2 rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          <RefreshCcw size={14} className={recomputing ? 'animate-spin' : ''} />
          {recomputing ? 'Consolidating...' : 'Consolidate Now'}
        </button>
      </div>

      {loading ? <p className="text-gray-400">Loading...</p> : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-gray-800 border border-gray-700 rounded-xl p-5">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Patterns Stored</p>
              <p className="text-2xl font-bold text-white">{entries.length + patterns.length}</p>
              <p className="text-xs text-gray-500 mt-1">
                {entries.length} memory entries + {patterns.length} winning patterns
              </p>
            </div>
            <div className="bg-gray-800 border border-gray-700 rounded-xl p-5">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Last Consolidation</p>
              <p className="text-2xl font-bold text-white">
                {lastConsolidation ? new Date(lastConsolidation).toLocaleDateString() : '--'}
              </p>
              <p className="text-xs text-gray-500 mt-1">Scheduled daily at 03:00 UTC</p>
            </div>
            <div className="bg-gray-800 border border-gray-700 rounded-xl p-5">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Insight Quality</p>
              <p className="text-2xl font-bold text-white">
                {avgConfidence > 0 ? `${(avgConfidence * 100).toFixed(0)}%` : '--'}
              </p>
              <p className="text-xs text-gray-500 mt-1">Average confidence across entries</p>
            </div>
          </div>

          <Card>
            <CardHeader><CardTitle>Recent Memory Entries ({entries.length})</CardTitle></CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Type</TableHead>
                    <TableHead>Scope</TableHead>
                    <TableHead>Platform</TableHead>
                    <TableHead>Summary</TableHead>
                    <TableHead>Confidence</TableHead>
                    <TableHead>Created</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {entries.slice(0, 20).map(e => (
                    <TableRow key={e.id}>
                      <TableCell className="font-medium">{e.entry_type}</TableCell>
                      <TableCell>{e.scope_type}</TableCell>
                      <TableCell>{e.platform ?? '--'}</TableCell>
                      <TableCell className="max-w-xs truncate">{e.summary}</TableCell>
                      <TableCell>{(e.confidence * 100).toFixed(0)}%</TableCell>
                      <TableCell className="text-xs">{e.created_at ? new Date(e.created_at).toLocaleDateString() : '--'}</TableCell>
                    </TableRow>
                  ))}
                  {entries.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-muted-foreground">
                        No memory entries yet. The consolidate_memory worker runs daily.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Winning Patterns ({patterns.length})</CardTitle></CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Pattern</TableHead>
                    <TableHead>Performance Band</TableHead>
                    <TableHead>Confidence</TableHead>
                    <TableHead>Reuse Count</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {patterns.slice(0, 20).map(p => (
                    <TableRow key={p.id}>
                      <TableCell className="font-medium">{p.pattern_key}</TableCell>
                      <TableCell>{p.performance_band}</TableCell>
                      <TableCell>{(p.confidence * 100).toFixed(0)}%</TableCell>
                      <TableCell>{p.reuse_count}</TableCell>
                    </TableRow>
                  ))}
                  {patterns.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center text-muted-foreground">
                        No winning patterns detected yet.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Memory Links ({links.length})</CardTitle></CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                {links.length > 0
                  ? `${links.length} cross-references connecting memory entries for reuse and pattern correlation.`
                  : 'No memory links formed yet. Links emerge as the consolidation worker connects related memory entries.'}
              </p>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
