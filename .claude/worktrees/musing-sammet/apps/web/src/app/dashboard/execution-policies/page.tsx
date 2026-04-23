'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchExecutionPolicies, recomputeExecutionPolicies } from '@/lib/autonomous-phase-b-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Shield, RefreshCcw } from 'lucide-react';

interface Policy {
  id: string;
  action_type: string;
  execution_mode: string;
  risk_level: string;
  cost_class: string;
  approval_requirement: string;
  kill_switch_class: string;
  confidence_threshold: number;
  explanation: string | null;
}

const MODE_COLORS: Record<string, string> = {
  autonomous: 'bg-green-100 text-green-800',
  guarded: 'bg-yellow-100 text-yellow-800',
  manual: 'bg-red-100 text-red-800',
};

export default function ExecutionPoliciesPage() {
  const brandId = useBrandId();
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      setPolicies(await fetchExecutionPolicies(brandId, ''));
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [brandId]);

  const handleRecompute = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      await recomputeExecutionPolicies(brandId, '');
      await load();
    } catch { /* empty */ }
    setLoading(false);
  };

  if (!brandId) return <p className="p-8 text-zinc-400">Select a brand first.</p>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="h-6 w-6 text-blue-500" />
          <h1 className="text-2xl font-bold">Execution Policies</h1>
        </div>
        <Button onClick={handleRecompute} disabled={loading} size="sm" variant="outline">
          <RefreshCcw className="mr-2 h-4 w-4" /> Recompute
        </Button>
      </div>

      <Card>
        <CardHeader><CardTitle>Active Policies ({policies.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Action Type</TableHead>
                <TableHead>Mode</TableHead>
                <TableHead>Risk</TableHead>
                <TableHead>Cost</TableHead>
                <TableHead>Approval</TableHead>
                <TableHead>Kill Switch</TableHead>
                <TableHead>Confidence</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {policies.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="font-mono text-sm">{p.action_type}</TableCell>
                  <TableCell>
                    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${MODE_COLORS[p.execution_mode] || 'bg-zinc-100'}`}>
                      {p.execution_mode}
                    </span>
                  </TableCell>
                  <TableCell>{p.risk_level}</TableCell>
                  <TableCell>{p.cost_class}</TableCell>
                  <TableCell>{p.approval_requirement}</TableCell>
                  <TableCell>{p.kill_switch_class}</TableCell>
                  <TableCell>{(p.confidence_threshold * 100).toFixed(0)}%</TableCell>
                </TableRow>
              ))}
              {policies.length === 0 && (
                <TableRow><TableCell colSpan={7} className="text-center text-zinc-400">No policies — click Recompute</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
