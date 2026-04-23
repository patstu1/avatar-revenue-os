'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchOverridePolicies, recomputeOverridePolicies } from '@/lib/autonomous-phase-d-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ShieldCheck, RefreshCcw } from 'lucide-react';

interface Policy {
  id: string;
  action_ref: string;
  override_mode: string;
  approval_needed: boolean;
  rollback_available: boolean;
  hard_stop_rule: string | null;
  confidence_threshold: number;
  explanation: string | null;
}

export default function OverridePoliciesPage() {
  const brandId = useBrandId();
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      const data = await fetchOverridePolicies(brandId, '');
      setPolicies(Array.isArray(data) ? data : []);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [brandId]);

  const recompute = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      await recomputeOverridePolicies(brandId, '');
      await load();
    } catch { /* empty */ }
    setLoading(false);
  };

  if (!brandId) return <p className="p-8 text-zinc-400">Select a brand first.</p>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ShieldCheck className="h-6 w-6 text-emerald-600" />
          <h1 className="text-2xl font-bold">Override / Approval Policies</h1>
        </div>
        <Button onClick={recompute} disabled={loading} size="sm" variant="outline">
          <RefreshCcw className="mr-2 h-4 w-4" /> Recompute
        </Button>
      </div>
      <Card>
        <CardHeader><CardTitle>Policies ({policies.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Action</TableHead>
                <TableHead>Mode</TableHead>
                <TableHead>Approval?</TableHead>
                <TableHead>Rollback?</TableHead>
                <TableHead>Hard Stop</TableHead>
                <TableHead>Threshold</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {policies.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="font-mono text-xs">{p.action_ref}</TableCell>
                  <TableCell>{p.override_mode}</TableCell>
                  <TableCell>{p.approval_needed ? 'Yes' : 'No'}</TableCell>
                  <TableCell>{p.rollback_available ? 'Yes' : 'No'}</TableCell>
                  <TableCell className="max-w-xs truncate text-xs">{p.hard_stop_rule ?? '—'}</TableCell>
                  <TableCell>{(p.confidence_threshold * 100).toFixed(0)}%</TableCell>
                </TableRow>
              ))}
              {policies.length === 0 && (
                <TableRow><TableCell colSpan={6} className="text-center text-zinc-400">No policies yet</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
