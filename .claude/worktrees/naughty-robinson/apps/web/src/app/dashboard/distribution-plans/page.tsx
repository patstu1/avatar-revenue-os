'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchDistributionPlans, recomputeDistributionPlans } from '@/lib/autonomous-phase-b-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Share2, RefreshCcw } from 'lucide-react';

interface Plan {
  id: string;
  source_concept: string;
  target_platforms_json: { platform: string; priority: number }[] | null;
  derivative_types_json: string[] | null;
  plan_status: string;
  confidence: number;
  explanation: string | null;
  created_at: string | null;
}

export default function DistributionPlansPage() {
  const brandId = useBrandId();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      setPlans(await fetchDistributionPlans(brandId, ''));
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [brandId]);

  const handleRecompute = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      await recomputeDistributionPlans(brandId, '');
      await load();
    } catch { /* empty */ }
    setLoading(false);
  };

  if (!brandId) return <p className="p-8 text-zinc-400">Select a brand first.</p>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Share2 className="h-6 w-6 text-purple-500" />
          <h1 className="text-2xl font-bold">Cross-Platform Distribution</h1>
        </div>
        <Button onClick={handleRecompute} disabled={loading} size="sm" variant="outline">
          <RefreshCcw className="mr-2 h-4 w-4" /> Recompute
        </Button>
      </div>

      <Card>
        <CardHeader><CardTitle>Distribution Plans ({plans.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Source Concept</TableHead>
                <TableHead>Target Platforms</TableHead>
                <TableHead>Derivatives</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Confidence</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {plans.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="max-w-xs truncate">{p.source_concept}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {(Array.isArray(p.target_platforms_json) ? p.target_platforms_json : []).map((t: any, i: number) => (
                        <span key={i} className="rounded bg-purple-50 px-1.5 py-0.5 text-xs text-purple-700">{t.platform || t}</span>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="text-xs">{(Array.isArray(p.derivative_types_json) ? p.derivative_types_json : []).join(', ')}</TableCell>
                  <TableCell>{p.plan_status}</TableCell>
                  <TableCell>{(p.confidence * 100).toFixed(0)}%</TableCell>
                </TableRow>
              ))}
              {plans.length === 0 && (
                <TableRow><TableCell colSpan={5} className="text-center text-zinc-400">No plans yet</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
