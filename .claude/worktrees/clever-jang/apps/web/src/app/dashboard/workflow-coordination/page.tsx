'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchWorkflowCoordination } from '@/lib/brain-phase-c-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { GitBranch } from 'lucide-react';

interface Workflow {
  id: string;
  workflow_type: string;
  status: string;
  sequence_json: string[] | null;
  handoff_events_json: Array<{ from_agent: string; to_agent: string; confidence: number }> | null;
  failure_points_json: Array<{ step: number; agent: string; error: string }> | null;
  explanation: string | null;
}

const STATUS_COLORS: Record<string, string> = { completed: 'bg-green-100 text-green-800', running: 'bg-blue-100 text-blue-800', failed: 'bg-red-100 text-red-800' };

export default function WorkflowCoordinationPage() {
  const brandId = useBrandId();
  const [rows, setRows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!brandId) return;
    setLoading(true);
    fetchWorkflowCoordination(brandId, '').then(setRows).finally(() => setLoading(false));
  }, [brandId]);

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand.</div>;

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold flex items-center gap-2"><GitBranch className="h-6 w-6" /> Workflow Coordination</h1>
      {loading ? <p>Loading…</p> : (
        <Card>
          <CardHeader><CardTitle>Workflows ({rows.length})</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader><TableRow><TableHead>Type</TableHead><TableHead>Status</TableHead><TableHead>Sequence</TableHead><TableHead>Handoffs</TableHead><TableHead>Failures</TableHead><TableHead>Explanation</TableHead></TableRow></TableHeader>
              <TableBody>
                {rows.map(r => (
                  <TableRow key={r.id}>
                    <TableCell className="font-semibold">{r.workflow_type}</TableCell>
                    <TableCell><span className={`rounded px-2 py-0.5 text-xs font-semibold ${STATUS_COLORS[r.status] || 'bg-gray-100'}`}>{r.status}</span></TableCell>
                    <TableCell className="text-xs">{r.sequence_json?.join(' → ') ?? '—'}</TableCell>
                    <TableCell>{r.handoff_events_json?.length ?? 0}</TableCell>
                    <TableCell>{r.failure_points_json?.length ?? 0}</TableCell>
                    <TableCell className="max-w-xs truncate">{r.explanation ?? '—'}</TableCell>
                  </TableRow>
                ))}
                {rows.length === 0 && <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground">No workflows yet.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
