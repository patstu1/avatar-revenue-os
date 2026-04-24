'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchPaidOperator, recomputePaidOperator } from '@/lib/autonomous-phase-c-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { HandCoins, RefreshCcw } from 'lucide-react';

interface PaidRun {
  id: string;
  paid_action: string;
  budget_band: string;
  expected_cac: number;
  expected_roi: number;
  execution_mode: string;
  confidence: number;
  winner_score: number;
  run_status: string;
}

interface Decision {
  id: string;
  decision_type: string;
  budget_band: string;
  expected_cac: number;
  expected_roi: number;
  execution_mode: string;
  confidence: number;
}

export default function PaidOperatorPage() {
  const brandId = useBrandId();
  const [runs, setRuns] = useState<PaidRun[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      const data = await fetchPaidOperator(brandId, '');
      setRuns(data.runs || []);
      setDecisions(data.decisions || []);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [brandId]);

  const recompute = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      await recomputePaidOperator(brandId, '');
      await load();
    } catch { /* empty */ }
    setLoading(false);
  };

  if (!brandId) return <p className="p-8 text-zinc-400">Select a brand first.</p>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <HandCoins className="h-6 w-6 text-amber-600" />
          <h1 className="text-2xl font-bold">Autonomous Paid Operator</h1>
        </div>
        <Button onClick={recompute} disabled={loading} size="sm" variant="outline">
          <RefreshCcw className="mr-2 h-4 w-4" /> Recompute
        </Button>
      </div>
      <Card>
        <CardHeader><CardTitle>Paid operator runs ({runs.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Action</TableHead>
                <TableHead>Budget band</TableHead>
                <TableHead>CAC est.</TableHead>
                <TableHead>ROI est.</TableHead>
                <TableHead>Mode</TableHead>
                <TableHead>Winner score</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-mono text-xs">{r.paid_action}</TableCell>
                  <TableCell>{r.budget_band}</TableCell>
                  <TableCell>${r.expected_cac.toFixed(2)}</TableCell>
                  <TableCell>{r.expected_roi.toFixed(2)}x</TableCell>
                  <TableCell>{r.execution_mode}</TableCell>
                  <TableCell>{(r.winner_score * 100).toFixed(0)}%</TableCell>
                </TableRow>
              ))}
              {runs.length === 0 && (
                <TableRow><TableCell colSpan={6} className="text-center text-zinc-400">No runs</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Decisions ({decisions.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Type</TableHead>
                <TableHead>Budget band</TableHead>
                <TableHead>CAC</TableHead>
                <TableHead>ROI</TableHead>
                <TableHead>Mode</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {decisions.map((d) => (
                <TableRow key={d.id}>
                  <TableCell>{d.decision_type}</TableCell>
                  <TableCell>{d.budget_band}</TableCell>
                  <TableCell>${d.expected_cac.toFixed(2)}</TableCell>
                  <TableCell>{d.expected_roi.toFixed(2)}x</TableCell>
                  <TableCell>{d.execution_mode}</TableCell>
                </TableRow>
              ))}
              {decisions.length === 0 && (
                <TableRow><TableCell colSpan={5} className="text-center text-zinc-400">No decisions</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
