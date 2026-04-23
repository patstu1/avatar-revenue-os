'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchBlockerDetection, recomputeBlockerDetection } from '@/lib/autonomous-phase-d-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Ban, RefreshCcw } from 'lucide-react';

interface Blocker {
  id: string;
  blocker: string;
  severity: string;
  affected_scope: string;
  operator_action_needed: string;
  deadline_or_urgency: string;
  consequence_if_ignored: string;
  status: string;
}

export default function BlockerDetectionPage() {
  const brandId = useBrandId();
  const [blockers, setBlockers] = useState<Blocker[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      const data = await fetchBlockerDetection(brandId, '');
      setBlockers(Array.isArray(data) ? data : []);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [brandId]);

  const recompute = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      await recomputeBlockerDetection(brandId, '');
      await load();
    } catch { /* empty */ }
    setLoading(false);
  };

  if (!brandId) return <p className="p-8 text-zinc-400">Select a brand first.</p>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Ban className="h-6 w-6 text-red-500" />
          <h1 className="text-2xl font-bold">Blocker Detection</h1>
        </div>
        <Button onClick={recompute} disabled={loading} size="sm" variant="outline">
          <RefreshCcw className="mr-2 h-4 w-4" /> Recompute
        </Button>
      </div>
      <Card>
        <CardHeader><CardTitle>Blockers ({blockers.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Blocker</TableHead>
                <TableHead>Severity</TableHead>
                <TableHead>Scope</TableHead>
                <TableHead>Action Needed</TableHead>
                <TableHead>Urgency</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {blockers.map((b) => (
                <TableRow key={b.id}>
                  <TableCell className="font-mono text-xs">{b.blocker}</TableCell>
                  <TableCell>{b.severity}</TableCell>
                  <TableCell className="max-w-xs truncate text-xs">{b.affected_scope}</TableCell>
                  <TableCell className="max-w-sm truncate text-xs">{b.operator_action_needed}</TableCell>
                  <TableCell>{b.deadline_or_urgency}</TableCell>
                  <TableCell>{b.status}</TableCell>
                </TableRow>
              ))}
              {blockers.length === 0 && (
                <TableRow><TableCell colSpan={6} className="text-center text-zinc-400">No blockers detected</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
