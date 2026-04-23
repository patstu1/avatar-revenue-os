'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchAccountStates, recomputeAccountStates } from '@/lib/brain-phase-a-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Users } from 'lucide-react';

interface AccountState {
  id: string;
  account_id: string;
  current_state: string;
  state_score: number;
  previous_state: string | null;
  next_expected_state: string | null;
  days_in_state: number;
  platform: string | null;
  confidence: number;
  explanation: string | null;
}

const STATE_COLORS: Record<string, string> = {
  newborn: 'bg-blue-100 text-blue-800',
  warming: 'bg-yellow-100 text-yellow-800',
  stable: 'bg-green-100 text-green-800',
  scaling: 'bg-emerald-100 text-emerald-800',
  max_output: 'bg-purple-100 text-purple-800',
  saturated: 'bg-orange-100 text-orange-800',
  cooling: 'bg-gray-100 text-gray-800',
  at_risk: 'bg-red-100 text-red-800',
};

export default function AccountStatesPage() {
  const brandId = useBrandId();
  const [rows, setRows] = useState<AccountState[]>([]);
  const [loading, setLoading] = useState(false);
  const [recomputing, setRecomputing] = useState(false);

  useEffect(() => {
    if (!brandId) return;
    setLoading(true);
    fetchAccountStates(brandId, '').then(setRows).finally(() => setLoading(false));
  }, [brandId]);

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    try {
      await recomputeAccountStates(brandId, '');
      setRows(await fetchAccountStates(brandId, ''));
    } finally {
      setRecomputing(false);
    }
  };

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand.</div>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2"><Users className="h-6 w-6" /> Account State Engine</h1>
        <button onClick={handleRecompute} disabled={recomputing} className="rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
          {recomputing ? 'Recomputing…' : 'Recompute States'}
        </button>
      </div>

      {loading ? <p>Loading…</p> : (
        <Card>
          <CardHeader><CardTitle>Account States ({rows.length})</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Account</TableHead>
                  <TableHead>Platform</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Prev</TableHead>
                  <TableHead>Next</TableHead>
                  <TableHead>Days</TableHead>
                  <TableHead>Confidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map(r => (
                  <TableRow key={r.id}>
                    <TableCell className="font-mono text-xs">{r.account_id.slice(0, 8)}</TableCell>
                    <TableCell>{r.platform ?? '—'}</TableCell>
                    <TableCell><span className={`rounded px-2 py-0.5 text-xs font-semibold ${STATE_COLORS[r.current_state] || 'bg-gray-100'}`}>{r.current_state}</span></TableCell>
                    <TableCell>{(r.state_score * 100).toFixed(0)}%</TableCell>
                    <TableCell>{r.previous_state ?? '—'}</TableCell>
                    <TableCell>{r.next_expected_state ?? '—'}</TableCell>
                    <TableCell>{r.days_in_state}</TableCell>
                    <TableCell>{(r.confidence * 100).toFixed(0)}%</TableCell>
                  </TableRow>
                ))}
                {rows.length === 0 && <TableRow><TableCell colSpan={8} className="text-center text-muted-foreground">No account states.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
