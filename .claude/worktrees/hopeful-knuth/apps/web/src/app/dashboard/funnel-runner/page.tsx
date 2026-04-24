'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchFunnelExecution, recomputeFunnelExecution } from '@/lib/autonomous-phase-c-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { GitBranch, RefreshCcw } from 'lucide-react';

interface FunnelRun {
  id: string;
  funnel_action: string;
  target_funnel_path: string;
  capture_mode: string;
  execution_mode: string;
  expected_upside: number;
  confidence: number;
  run_status: string;
}

export default function FunnelRunnerPage() {
  const brandId = useBrandId();
  const [rows, setRows] = useState<FunnelRun[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      setRows(await fetchFunnelExecution(brandId, ''));
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [brandId]);

  const recompute = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      await recomputeFunnelExecution(brandId, '');
      await load();
    } catch { /* empty */ }
    setLoading(false);
  };

  if (!brandId) return <p className="p-8 text-zinc-400">Select a brand first.</p>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <GitBranch className="h-6 w-6 text-emerald-600" />
          <h1 className="text-2xl font-bold">Autonomous Funnel Runner</h1>
        </div>
        <Button onClick={recompute} disabled={loading} size="sm" variant="outline">
          <RefreshCcw className="mr-2 h-4 w-4" /> Recompute
        </Button>
      </div>
      <Card>
        <CardHeader><CardTitle>Funnel execution runs ({rows.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Action</TableHead>
                <TableHead>Path</TableHead>
                <TableHead>Capture</TableHead>
                <TableHead>Mode</TableHead>
                <TableHead>Upside</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-mono text-xs">{r.funnel_action}</TableCell>
                  <TableCell className="max-w-xs truncate text-xs">{r.target_funnel_path}</TableCell>
                  <TableCell>{r.capture_mode}</TableCell>
                  <TableCell>{r.execution_mode}</TableCell>
                  <TableCell>${r.expected_upside.toLocaleString()}</TableCell>
                  <TableCell>{(r.confidence * 100).toFixed(0)}%</TableCell>
                  <TableCell>{r.run_status}</TableCell>
                </TableRow>
              ))}
              {rows.length === 0 && (
                <TableRow><TableCell colSpan={7} className="text-center text-zinc-400">No runs — Recompute</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
