'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchBufferBlockers } from '@/lib/buffer-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { AlertTriangle } from 'lucide-react';

interface Blocker { id: string; blocker_type: string; severity: string; description: string; operator_action_needed: string; resolved: boolean; }

const SEV_COLORS: Record<string, string> = { critical: 'bg-red-100 text-red-800', high: 'bg-orange-100 text-orange-800', medium: 'bg-yellow-100 text-yellow-800', low: 'bg-gray-100 text-gray-800' };

export default function BufferBlockersPage() {
  const brandId = useBrandId();
  const [rows, setRows] = useState<Blocker[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => { if (brandId) { setLoading(true); fetchBufferBlockers(brandId, '').then(setRows).finally(() => setLoading(false)); } }, [brandId]);

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand.</div>;

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold flex items-center gap-2"><AlertTriangle className="h-6 w-6" /> Buffer Blockers</h1>
      <p className="text-sm text-muted-foreground">Issues preventing content from being distributed via Buffer. Resolve these to enable publishing.</p>
      {loading ? <p>Loading…</p> : (
        <Card>
          <CardHeader><CardTitle>Unresolved Blockers ({rows.length})</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader><TableRow><TableHead>Type</TableHead><TableHead>Severity</TableHead><TableHead>Description</TableHead><TableHead>Action Needed</TableHead></TableRow></TableHeader>
              <TableBody>
                {rows.map(r => (
                  <TableRow key={r.id}>
                    <TableCell className="font-semibold">{r.blocker_type}</TableCell>
                    <TableCell><span className={`rounded px-2 py-0.5 text-xs font-semibold ${SEV_COLORS[r.severity] || 'bg-gray-100'}`}>{r.severity}</span></TableCell>
                    <TableCell>{r.description}</TableCell>
                    <TableCell className="font-semibold">{r.operator_action_needed}</TableCell>
                  </TableRow>
                ))}
                {rows.length === 0 && <TableRow><TableCell colSpan={4} className="text-center text-muted-foreground">No blockers. Buffer distribution is clear.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
