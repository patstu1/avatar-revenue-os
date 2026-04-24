'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchAudienceStatesV2, recomputeAudienceStatesV2 } from '@/lib/brain-phase-a-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Users } from 'lucide-react';

interface AudienceState {
  id: string;
  segment_label: string;
  current_state: string;
  state_score: number;
  next_best_action: string | null;
  estimated_segment_size: number;
  estimated_ltv: number;
  confidence: number;
}

const STATE_COLORS: Record<string, string> = {
  unaware: 'bg-gray-100 text-gray-800',
  curious: 'bg-blue-100 text-blue-800',
  evaluating: 'bg-yellow-100 text-yellow-800',
  objection_heavy: 'bg-orange-100 text-orange-800',
  ready_to_buy: 'bg-green-100 text-green-800',
  bought_once: 'bg-emerald-100 text-emerald-800',
  repeat_buyer: 'bg-teal-100 text-teal-800',
  high_ltv: 'bg-purple-100 text-purple-800',
  churn_risk: 'bg-red-100 text-red-800',
  advocate: 'bg-indigo-100 text-indigo-800',
  sponsor_friendly: 'bg-pink-100 text-pink-800',
};

export default function AudienceStatesV2Page() {
  const brandId = useBrandId();
  const [rows, setRows] = useState<AudienceState[]>([]);
  const [loading, setLoading] = useState(false);
  const [recomputing, setRecomputing] = useState(false);

  useEffect(() => {
    if (!brandId) return;
    setLoading(true);
    fetchAudienceStatesV2(brandId, '').then(setRows).finally(() => setLoading(false));
  }, [brandId]);

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    try {
      await recomputeAudienceStatesV2(brandId, '');
      setRows(await fetchAudienceStatesV2(brandId, ''));
    } finally {
      setRecomputing(false);
    }
  };

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand.</div>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2"><Users className="h-6 w-6" /> Audience State Engine V2</h1>
        <button onClick={handleRecompute} disabled={recomputing} className="rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
          {recomputing ? 'Recomputing…' : 'Recompute States'}
        </button>
      </div>

      {loading ? <p>Loading…</p> : (
        <Card>
          <CardHeader><CardTitle>Audience Segments ({rows.length})</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Segment</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Next Best Action</TableHead>
                  <TableHead>Size</TableHead>
                  <TableHead>Est. LTV</TableHead>
                  <TableHead>Confidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map(r => (
                  <TableRow key={r.id}>
                    <TableCell className="font-medium">{r.segment_label}</TableCell>
                    <TableCell><span className={`rounded px-2 py-0.5 text-xs font-semibold ${STATE_COLORS[r.current_state] || 'bg-gray-100'}`}>{r.current_state}</span></TableCell>
                    <TableCell>{(r.state_score * 100).toFixed(0)}%</TableCell>
                    <TableCell className="max-w-xs truncate">{r.next_best_action ?? '—'}</TableCell>
                    <TableCell>{r.estimated_segment_size.toLocaleString()}</TableCell>
                    <TableCell>${r.estimated_ltv.toFixed(0)}</TableCell>
                    <TableCell>{(r.confidence * 100).toFixed(0)}%</TableCell>
                  </TableRow>
                ))}
                {rows.length === 0 && <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground">No audience states.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
