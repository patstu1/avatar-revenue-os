'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchAutonomousRuns, startAutonomousRuns } from '@/lib/autonomous-phase-b-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Play, Zap } from 'lucide-react';

interface Run {
  id: string;
  target_platform: string;
  execution_mode: string;
  run_status: string;
  current_step: string;
  started_at: string | null;
  explanation: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-zinc-100 text-zinc-800',
  running: 'bg-blue-100 text-blue-800',
  paused: 'bg-yellow-100 text-yellow-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-zinc-200 text-zinc-600',
};

export default function ContentRunnerPage() {
  const brandId = useBrandId();
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      setRuns(await fetchAutonomousRuns(brandId, ''));
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [brandId]);

  const handleStart = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      await startAutonomousRuns(brandId, '');
      await load();
    } catch { /* empty */ }
    setLoading(false);
  };

  if (!brandId) return <p className="p-8 text-zinc-400">Select a brand first.</p>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Zap className="h-6 w-6 text-yellow-500" />
          <h1 className="text-2xl font-bold">Continuous Content Runner</h1>
        </div>
        <Button onClick={handleStart} disabled={loading} size="sm" variant="outline">
          <Play className="mr-2 h-4 w-4" /> Start Runs
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {['running', 'pending', 'completed', 'failed'].map((st) => (
          <Card key={st}>
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold">{runs.filter((r) => r.run_status === st).length}</p>
              <p className="text-xs text-zinc-400 capitalize">{st}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader><CardTitle>Autonomous Runs ({runs.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Platform</TableHead>
                <TableHead>Mode</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Current Step</TableHead>
                <TableHead>Started</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-medium">{r.target_platform}</TableCell>
                  <TableCell>{r.execution_mode}</TableCell>
                  <TableCell>
                    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[r.run_status] || 'bg-zinc-100'}`}>
                      {r.run_status}
                    </span>
                  </TableCell>
                  <TableCell className="font-mono text-sm">{r.current_step}</TableCell>
                  <TableCell className="text-xs text-zinc-400">{r.started_at ? new Date(r.started_at).toLocaleString() : '—'}</TableCell>
                </TableRow>
              ))}
              {runs.length === 0 && (
                <TableRow><TableCell colSpan={5} className="text-center text-zinc-400">No runs — click Start Runs</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
