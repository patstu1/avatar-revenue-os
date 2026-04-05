'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchBrainEscalations } from '@/lib/brain-phase-d-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { AlertTriangle } from 'lucide-react';

interface Escalation { id: string; escalation_type: string; command: string; urgency: string; expected_upside_unlocked: number; expected_cost_of_delay: number; value_basis?: string; affected_scope: string; confidence: number; resolved: boolean; explanation: string | null; }

const URG_COLORS: Record<string, string> = { critical: 'bg-red-100 text-red-800', high: 'bg-orange-100 text-orange-800', medium: 'bg-yellow-100 text-yellow-800', low: 'bg-gray-100 text-gray-800' };

export default function BrainEscalationsPage() {
  const brandId = useBrandId();
  const [rows, setRows] = useState<Escalation[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => { if (brandId) { setLoading(true); fetchBrainEscalations(brandId, '').then(setRows).finally(() => setLoading(false)); } }, [brandId]);

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand.</div>;

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold flex items-center gap-2"><AlertTriangle className="h-6 w-6" /> Brain Escalations</h1>
      {loading ? <p>Loading…</p> : (
        <Card>
          <CardHeader><CardTitle>Escalations ({rows.length})</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader><TableRow><TableHead>Type</TableHead><TableHead>Command</TableHead><TableHead>Urgency</TableHead><TableHead>Upside</TableHead><TableHead>Delay Cost</TableHead><TableHead>Scope</TableHead><TableHead>Resolved</TableHead></TableRow></TableHeader>
              <TableBody>
                {rows.map(r => (
                  <TableRow key={r.id}>
                    <TableCell className="font-semibold">{r.escalation_type}</TableCell>
                    <TableCell className="max-w-xs">{r.command}</TableCell>
                    <TableCell><span className={`rounded px-2 py-0.5 text-xs font-semibold ${URG_COLORS[r.urgency] || 'bg-gray-100'}`}>{r.urgency}</span></TableCell>
                    <TableCell className={r.value_basis === 'illustrative_estimate' ? 'text-green-700/60 italic' : 'text-green-700'}>{r.value_basis === 'illustrative_estimate' ? '~' : ''}${r.expected_upside_unlocked.toFixed(0)}{r.value_basis === 'illustrative_estimate' ? ' est.' : ''}</TableCell>
                    <TableCell className={r.value_basis === 'illustrative_estimate' ? 'text-red-700/60 italic' : 'text-red-700'}>{r.value_basis === 'illustrative_estimate' ? '~' : ''}${r.expected_cost_of_delay.toFixed(0)}/day{r.value_basis === 'illustrative_estimate' ? ' est.' : ''}</TableCell>
                    <TableCell>{r.affected_scope}</TableCell>
                    <TableCell>{r.resolved ? 'Yes' : 'No'}</TableCell>
                  </TableRow>
                ))}
                {rows.length === 0 && <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground">No escalations. System is operating within bounds.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
