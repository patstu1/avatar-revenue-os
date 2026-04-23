'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchOpportunityStates, recomputeOpportunityStates } from '@/lib/brain-phase-a-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Compass } from 'lucide-react';

interface OppState {
  id: string;
  opportunity_scope: string;
  current_state: string;
  urgency: number;
  readiness: number;
  suppression_risk: number;
  expected_upside: number;
  expected_cost: number;
  confidence: number;
  explanation: string | null;
}

const STATE_COLORS: Record<string, string> = {
  monitor: 'bg-blue-100 text-blue-800',
  test: 'bg-yellow-100 text-yellow-800',
  scale: 'bg-green-100 text-green-800',
  suppress: 'bg-red-100 text-red-800',
  evergreen_backlog: 'bg-gray-100 text-gray-800',
  blocked: 'bg-orange-100 text-orange-800',
};

export default function OpportunityStatesPage() {
  const brandId = useBrandId();
  const [rows, setRows] = useState<OppState[]>([]);
  const [loading, setLoading] = useState(false);
  const [recomputing, setRecomputing] = useState(false);

  useEffect(() => {
    if (!brandId) return;
    setLoading(true);
    fetchOpportunityStates(brandId, '').then(setRows).finally(() => setLoading(false));
  }, [brandId]);

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    try {
      await recomputeOpportunityStates(brandId, '');
      setRows(await fetchOpportunityStates(brandId, ''));
    } finally {
      setRecomputing(false);
    }
  };

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand.</div>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2"><Compass className="h-6 w-6" /> Opportunity State Engine</h1>
        <button onClick={handleRecompute} disabled={recomputing} className="rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
          {recomputing ? 'Recomputing…' : 'Recompute States'}
        </button>
      </div>

      {loading ? <p>Loading…</p> : (
        <Card>
          <CardHeader><CardTitle>Opportunity States ({rows.length})</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Scope</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead>Urgency</TableHead>
                  <TableHead>Readiness</TableHead>
                  <TableHead>Suppression Risk</TableHead>
                  <TableHead>Upside</TableHead>
                  <TableHead>Cost</TableHead>
                  <TableHead>Confidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map(r => (
                  <TableRow key={r.id}>
                    <TableCell>{r.opportunity_scope}</TableCell>
                    <TableCell><span className={`rounded px-2 py-0.5 text-xs font-semibold ${STATE_COLORS[r.current_state] || 'bg-gray-100'}`}>{r.current_state}</span></TableCell>
                    <TableCell>{(r.urgency * 100).toFixed(0)}%</TableCell>
                    <TableCell>{(r.readiness * 100).toFixed(0)}%</TableCell>
                    <TableCell>{(r.suppression_risk * 100).toFixed(0)}%</TableCell>
                    <TableCell>${r.expected_upside.toFixed(0)}</TableCell>
                    <TableCell>${r.expected_cost.toFixed(0)}</TableCell>
                    <TableCell>{(r.confidence * 100).toFixed(0)}%</TableCell>
                  </TableRow>
                ))}
                {rows.length === 0 && <TableRow><TableCell colSpan={8} className="text-center text-muted-foreground">No opportunity states.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
