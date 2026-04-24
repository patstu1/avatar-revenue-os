'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchExecutionStates, recomputeExecutionStates } from '@/lib/brain-phase-a-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Zap } from 'lucide-react';

interface ExecState {
  id: string;
  execution_scope: string;
  current_state: string;
  transition_reason: string | null;
  rollback_eligible: boolean;
  escalation_required: boolean;
  failure_count: number;
  confidence: number;
}

const STATE_COLORS: Record<string, string> = {
  queued: 'bg-gray-100 text-gray-800',
  autonomous: 'bg-green-100 text-green-800',
  guarded: 'bg-yellow-100 text-yellow-800',
  manual: 'bg-blue-100 text-blue-800',
  blocked: 'bg-orange-100 text-orange-800',
  failed: 'bg-red-100 text-red-800',
  recovering: 'bg-amber-100 text-amber-800',
  completed: 'bg-emerald-100 text-emerald-800',
};

export default function ExecutionStatesPage() {
  const brandId = useBrandId();
  const [rows, setRows] = useState<ExecState[]>([]);
  const [loading, setLoading] = useState(false);
  const [recomputing, setRecomputing] = useState(false);

  useEffect(() => {
    if (!brandId) return;
    setLoading(true);
    fetchExecutionStates(brandId, '').then(setRows).finally(() => setLoading(false));
  }, [brandId]);

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    try {
      await recomputeExecutionStates(brandId, '');
      setRows(await fetchExecutionStates(brandId, ''));
    } finally {
      setRecomputing(false);
    }
  };

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand.</div>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2"><Zap className="h-6 w-6" /> Execution State Engine</h1>
        <button onClick={handleRecompute} disabled={recomputing} className="rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
          {recomputing ? 'Recomputing…' : 'Recompute States'}
        </button>
      </div>

      {loading ? <p>Loading…</p> : (
        <Card>
          <CardHeader><CardTitle>Execution States ({rows.length})</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Scope</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead>Rollback</TableHead>
                  <TableHead>Escalation</TableHead>
                  <TableHead>Failures</TableHead>
                  <TableHead>Confidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map(r => (
                  <TableRow key={r.id}>
                    <TableCell>{r.execution_scope}</TableCell>
                    <TableCell><span className={`rounded px-2 py-0.5 text-xs font-semibold ${STATE_COLORS[r.current_state] || 'bg-gray-100'}`}>{r.current_state}</span></TableCell>
                    <TableCell className="max-w-xs truncate">{r.transition_reason ?? '—'}</TableCell>
                    <TableCell>{r.rollback_eligible ? 'Yes' : 'No'}</TableCell>
                    <TableCell>{r.escalation_required ? 'Yes' : 'No'}</TableCell>
                    <TableCell>{r.failure_count}</TableCell>
                    <TableCell>{(r.confidence * 100).toFixed(0)}%</TableCell>
                  </TableRow>
                ))}
                {rows.length === 0 && <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground">No execution states.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
