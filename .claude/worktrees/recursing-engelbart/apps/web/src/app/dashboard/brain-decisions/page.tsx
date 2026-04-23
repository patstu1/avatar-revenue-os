'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchBrainDecisions, recomputeBrainDecisions } from '@/lib/brain-phase-b-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Brain } from 'lucide-react';

interface Decision {
  id: string;
  decision_class: string;
  objective: string;
  target_scope: string;
  selected_action: string;
  confidence: number;
  policy_mode: string;
  expected_upside: number;
  expected_cost: number;
  downstream_action: string | null;
}

const MODE_COLORS: Record<string, string> = {
  autonomous: 'bg-green-100 text-green-800',
  guarded: 'bg-yellow-100 text-yellow-800',
  manual: 'bg-red-100 text-red-800',
};

export default function BrainDecisionsPage() {
  const brandId = useBrandId();
  const [rows, setRows] = useState<Decision[]>([]);
  const [loading, setLoading] = useState(false);
  const [recomputing, setRecomputing] = useState(false);

  useEffect(() => {
    if (!brandId) return;
    setLoading(true);
    fetchBrainDecisions(brandId, '').then(setRows).finally(() => setLoading(false));
  }, [brandId]);

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    try {
      await recomputeBrainDecisions(brandId, '');
      setRows(await fetchBrainDecisions(brandId, ''));
    } finally { setRecomputing(false); }
  };

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand.</div>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2"><Brain className="h-6 w-6" /> Brain Decisions</h1>
        <button onClick={handleRecompute} disabled={recomputing} className="rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
          {recomputing ? 'Recomputing…' : 'Recompute Decisions'}
        </button>
      </div>
      {loading ? <p>Loading…</p> : (
        <Card>
          <CardHeader><CardTitle>Decisions ({rows.length})</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Class</TableHead>
                  <TableHead>Scope</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Mode</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Upside</TableHead>
                  <TableHead>Cost</TableHead>
                  <TableHead>Downstream</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map(r => (
                  <TableRow key={r.id}>
                    <TableCell className="font-semibold">{r.decision_class}</TableCell>
                    <TableCell>{r.target_scope}</TableCell>
                    <TableCell>{r.selected_action}</TableCell>
                    <TableCell><span className={`rounded px-2 py-0.5 text-xs font-semibold ${MODE_COLORS[r.policy_mode] || 'bg-gray-100'}`}>{r.policy_mode}</span></TableCell>
                    <TableCell>{(r.confidence * 100).toFixed(0)}%</TableCell>
                    <TableCell>${r.expected_upside.toFixed(0)}</TableCell>
                    <TableCell>${r.expected_cost.toFixed(0)}</TableCell>
                    <TableCell className="max-w-xs truncate">{r.downstream_action ?? '—'}</TableCell>
                  </TableRow>
                ))}
                {rows.length === 0 && <TableRow><TableCell colSpan={8} className="text-center text-muted-foreground">No decisions yet.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
