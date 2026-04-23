'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchBrainMemory, recomputeBrainMemory } from '@/lib/brain-phase-a-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Brain } from 'lucide-react';

interface MemoryEntry {
  id: string;
  entry_type: string;
  scope_type: string;
  platform: string | null;
  summary: string;
  confidence: number;
  reuse_recommendation: string | null;
  suppression_caution: string | null;
  created_at: string | null;
}

interface MemoryLink {
  id: string;
  link_type: string;
  strength: number;
  source_entry_id: string;
  target_entry_id: string;
}

export default function BrainMemoryPage() {
  const brandId = useBrandId();
  const [entries, setEntries] = useState<MemoryEntry[]>([]);
  const [links, setLinks] = useState<MemoryLink[]>([]);
  const [loading, setLoading] = useState(false);
  const [recomputing, setRecomputing] = useState(false);

  useEffect(() => {
    if (!brandId) return;
    setLoading(true);
    fetchBrainMemory(brandId, '').then(data => {
      setEntries(data.entries ?? []);
      setLinks(data.links ?? []);
    }).finally(() => setLoading(false));
  }, [brandId]);

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    try {
      await recomputeBrainMemory(brandId, '');
      const data = await fetchBrainMemory(brandId, '');
      setEntries(data.entries ?? []);
      setLinks(data.links ?? []);
    } finally {
      setRecomputing(false);
    }
  };

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand to view brain memory.</div>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2"><Brain className="h-6 w-6" /> Brain Memory</h1>
        <button onClick={handleRecompute} disabled={recomputing} className="rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
          {recomputing ? 'Consolidating…' : 'Consolidate Memory'}
        </button>
      </div>

      {loading ? <p>Loading…</p> : (
        <>
          <Card>
            <CardHeader><CardTitle>Memory Entries ({entries.length})</CardTitle></CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Type</TableHead>
                    <TableHead>Scope</TableHead>
                    <TableHead>Platform</TableHead>
                    <TableHead>Summary</TableHead>
                    <TableHead>Confidence</TableHead>
                    <TableHead>Reuse</TableHead>
                    <TableHead>Caution</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {entries.map(e => (
                    <TableRow key={e.id}>
                      <TableCell className="font-medium">{e.entry_type}</TableCell>
                      <TableCell>{e.scope_type}</TableCell>
                      <TableCell>{e.platform ?? '—'}</TableCell>
                      <TableCell className="max-w-xs truncate">{e.summary}</TableCell>
                      <TableCell>{(e.confidence * 100).toFixed(0)}%</TableCell>
                      <TableCell className="max-w-xs truncate">{e.reuse_recommendation ?? '—'}</TableCell>
                      <TableCell className="max-w-xs truncate">{e.suppression_caution ?? '—'}</TableCell>
                    </TableRow>
                  ))}
                  {entries.length === 0 && <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground">No memory entries yet.</TableCell></TableRow>}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Memory Links ({links.length})</CardTitle></CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Link Type</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead>Target</TableHead>
                    <TableHead>Strength</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {links.map(lk => (
                    <TableRow key={lk.id}>
                      <TableCell>{lk.link_type}</TableCell>
                      <TableCell className="font-mono text-xs">{lk.source_entry_id.slice(0, 8)}</TableCell>
                      <TableCell className="font-mono text-xs">{lk.target_entry_id.slice(0, 8)}</TableCell>
                      <TableCell>{(lk.strength * 100).toFixed(0)}%</TableCell>
                    </TableRow>
                  ))}
                  {links.length === 0 && <TableRow><TableCell colSpan={4} className="text-center text-muted-foreground">No links yet.</TableCell></TableRow>}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
