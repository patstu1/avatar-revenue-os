'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchSponsorAutonomy, recomputeSponsorAutonomy } from '@/lib/autonomous-phase-c-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Handshake, RefreshCcw } from 'lucide-react';

interface Row {
  id: string;
  sponsor_action: string;
  target_category: string;
  pipeline_stage: string;
  expected_deal_value: number;
  confidence: number;
}

export default function SponsorAutonomyPage() {
  const brandId = useBrandId();
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      setRows(await fetchSponsorAutonomy(brandId, ''));
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [brandId]);

  const recompute = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      await recomputeSponsorAutonomy(brandId, '');
      await load();
    } catch { /* empty */ }
    setLoading(false);
  };

  if (!brandId) return <p className="p-8 text-zinc-400">Select a brand first.</p>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Handshake className="h-6 w-6 text-violet-600" />
          <h1 className="text-2xl font-bold">Autonomous Sponsor Revenue</h1>
        </div>
        <Button onClick={recompute} disabled={loading} size="sm" variant="outline">
          <RefreshCcw className="mr-2 h-4 w-4" /> Recompute
        </Button>
      </div>
      <Card>
        <CardHeader><CardTitle>Sponsor autonomous actions ({rows.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Action</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Pipeline</TableHead>
                <TableHead>Deal value est.</TableHead>
                <TableHead>Confidence</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-mono text-xs">{r.sponsor_action}</TableCell>
                  <TableCell>{r.target_category}</TableCell>
                  <TableCell>{r.pipeline_stage}</TableCell>
                  <TableCell>${r.expected_deal_value.toLocaleString()}</TableCell>
                  <TableCell>{(r.confidence * 100).toFixed(0)}%</TableCell>
                </TableRow>
              ))}
              {rows.length === 0 && (
                <TableRow><TableCell colSpan={5} className="text-center text-zinc-400">No actions</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
