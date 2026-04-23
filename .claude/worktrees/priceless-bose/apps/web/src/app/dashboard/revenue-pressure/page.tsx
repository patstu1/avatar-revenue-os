'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchRevenuePressure, recomputeRevenuePressure } from '@/lib/autonomous-phase-d-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Flame, RefreshCcw } from 'lucide-react';

interface Pressure {
  id: string;
  pressure_score: number;
  biggest_blocker: string | null;
  biggest_missed_opportunity: string | null;
  biggest_weak_lane_to_kill: string | null;
  underused_monetization_class: string | null;
  underbuilt_platform: string | null;
  next_commands_json: { action: string; priority: string; explanation: string }[] | null;
  next_launches_json: { launch: string; platform: string }[] | null;
  explanation: string | null;
}

export default function RevenuePressurePage() {
  const brandId = useBrandId();
  const [reports, setReports] = useState<Pressure[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      const data = await fetchRevenuePressure(brandId, '');
      setReports(Array.isArray(data) ? data : []);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [brandId]);

  const recompute = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      await recomputeRevenuePressure(brandId, '');
      await load();
    } catch { /* empty */ }
    setLoading(false);
  };

  if (!brandId) return <p className="p-8 text-zinc-400">Select a brand first.</p>;
  const latest = reports[0];

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Flame className="h-6 w-6 text-orange-500" />
          <h1 className="text-2xl font-bold">Revenue Pressure</h1>
        </div>
        <Button onClick={recompute} disabled={loading} size="sm" variant="outline">
          <RefreshCcw className="mr-2 h-4 w-4" /> Recompute
        </Button>
      </div>
      {latest ? (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <Card><CardHeader><CardTitle className="text-sm">Pressure Score</CardTitle></CardHeader>
              <CardContent><p className="text-3xl font-bold">{(latest.pressure_score * 100).toFixed(0)}%</p></CardContent>
            </Card>
            <Card><CardHeader><CardTitle className="text-sm">Biggest Blocker</CardTitle></CardHeader>
              <CardContent><p className="font-mono text-sm">{latest.biggest_blocker ?? 'none'}</p></CardContent>
            </Card>
            <Card><CardHeader><CardTitle className="text-sm">Biggest Missed Opportunity</CardTitle></CardHeader>
              <CardContent><p className="font-mono text-sm">{latest.biggest_missed_opportunity ?? 'none'}</p></CardContent>
            </Card>
          </div>
          <Card>
            <CardHeader><CardTitle>Next Commands</CardTitle></CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Action</TableHead>
                    <TableHead>Priority</TableHead>
                    <TableHead>Explanation</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(latest.next_commands_json || []).map((c, i) => (
                    <TableRow key={i}>
                      <TableCell className="font-mono text-xs">{c.action}</TableCell>
                      <TableCell>{c.priority}</TableCell>
                      <TableCell className="max-w-sm truncate text-xs">{c.explanation}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Next Launches</CardTitle></CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Launch</TableHead>
                    <TableHead>Platform</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(latest.next_launches_json || []).map((l, i) => (
                    <TableRow key={i}>
                      <TableCell className="font-mono text-xs">{l.launch}</TableCell>
                      <TableCell>{l.platform}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      ) : (
        <Card><CardContent className="py-12 text-center text-zinc-400">No pressure reports yet. Click Recompute.</CardContent></Card>
      )}
    </div>
  );
}
