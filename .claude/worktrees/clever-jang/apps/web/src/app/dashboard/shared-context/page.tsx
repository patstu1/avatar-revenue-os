'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchSharedContextEvents } from '@/lib/brain-phase-c-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Radio } from 'lucide-react';

interface CtxEvent {
  id: string;
  event_type: string;
  source_module: string;
  target_modules_json: string[] | null;
  priority: number;
  consumed: boolean;
  explanation: string | null;
}

const PRIO_COLORS: Record<number, string> = { 1: 'bg-red-100 text-red-800', 2: 'bg-orange-100 text-orange-800', 3: 'bg-yellow-100 text-yellow-800', 4: 'bg-blue-100 text-blue-800', 5: 'bg-gray-100 text-gray-800' };

export default function SharedContextPage() {
  const brandId = useBrandId();
  const [rows, setRows] = useState<CtxEvent[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!brandId) return;
    setLoading(true);
    fetchSharedContextEvents(brandId, '').then(setRows).finally(() => setLoading(false));
  }, [brandId]);

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand.</div>;

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold flex items-center gap-2"><Radio className="h-6 w-6" /> Shared Context Bus</h1>
      {loading ? <p>Loading…</p> : (
        <Card>
          <CardHeader><CardTitle>Events ({rows.length})</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader><TableRow><TableHead>Event</TableHead><TableHead>Source</TableHead><TableHead>Targets</TableHead><TableHead>Priority</TableHead><TableHead>Consumed</TableHead><TableHead>Explanation</TableHead></TableRow></TableHeader>
              <TableBody>
                {rows.map(r => (
                  <TableRow key={r.id}>
                    <TableCell className="font-semibold">{r.event_type}</TableCell>
                    <TableCell>{r.source_module}</TableCell>
                    <TableCell className="text-xs">{r.target_modules_json?.join(', ') ?? '—'}</TableCell>
                    <TableCell><span className={`rounded px-2 py-0.5 text-xs font-semibold ${PRIO_COLORS[r.priority] || 'bg-gray-100'}`}>P{r.priority}</span></TableCell>
                    <TableCell>{r.consumed ? 'Yes' : 'No'}</TableCell>
                    <TableCell className="max-w-xs truncate">{r.explanation ?? '—'}</TableCell>
                  </TableRow>
                ))}
                {rows.length === 0 && <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground">No events yet.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
