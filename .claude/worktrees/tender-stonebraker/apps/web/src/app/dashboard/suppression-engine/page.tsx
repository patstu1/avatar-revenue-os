'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchSuppressionExecutions } from '@/lib/autonomous-phase-b-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ShieldOff } from 'lucide-react';

interface Suppression {
  id: string;
  suppression_type: string;
  affected_scope: string;
  trigger_reason: string;
  duration_hours: number | null;
  lift_condition: string | null;
  confidence: number;
  suppression_status: string;
  created_at: string | null;
}

const TYPE_COLORS: Record<string, string> = {
  pause_lane: 'bg-red-100 text-red-800',
  reduce_output: 'bg-orange-100 text-orange-800',
  suppress_queue_item: 'bg-yellow-100 text-yellow-800',
  suppress_content_family: 'bg-amber-100 text-amber-800',
  suppress_account_expansion: 'bg-rose-100 text-rose-800',
  suppress_monetization_path: 'bg-pink-100 text-pink-800',
};

export default function SuppressionEnginePage() {
  const brandId = useBrandId();
  const [items, setItems] = useState<Suppression[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      setItems(await fetchSuppressionExecutions(brandId, ''));
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [brandId]);

  if (!brandId) return <p className="p-8 text-zinc-400">Select a brand first.</p>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-3">
        <ShieldOff className="h-6 w-6 text-red-500" />
        <h1 className="text-2xl font-bold">Autonomous Suppression Engine</h1>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        {['active', 'lifted', 'expired'].map((st) => (
          <Card key={st}>
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold">{items.filter((s) => s.suppression_status === st).length}</p>
              <p className="text-xs text-zinc-400 capitalize">{st}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader><CardTitle>Suppression Executions ({items.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Type</TableHead>
                <TableHead>Scope</TableHead>
                <TableHead>Reason</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>Lift Condition</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((s) => (
                <TableRow key={s.id}>
                  <TableCell>
                    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${TYPE_COLORS[s.suppression_type] || 'bg-zinc-100'}`}>
                      {s.suppression_type.replace(/_/g, ' ')}
                    </span>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{s.affected_scope}</TableCell>
                  <TableCell className="max-w-xs truncate text-xs">{s.trigger_reason}</TableCell>
                  <TableCell>{s.duration_hours ? `${s.duration_hours}h` : '—'}</TableCell>
                  <TableCell className="max-w-xs truncate text-xs text-zinc-500">{s.lift_condition || '—'}</TableCell>
                  <TableCell>{(s.confidence * 100).toFixed(0)}%</TableCell>
                  <TableCell>{s.suppression_status}</TableCell>
                </TableRow>
              ))}
              {items.length === 0 && (
                <TableRow><TableCell colSpan={7} className="text-center text-zinc-400">No suppressions active</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
