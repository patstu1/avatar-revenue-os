'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchPolicyEvaluations } from '@/lib/brain-phase-b-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Shield } from 'lucide-react';

interface PolicyEval {
  id: string;
  action_ref: string;
  policy_mode: string;
  reason: string;
  approval_needed: boolean;
  hard_stop_rule: string | null;
  rollback_rule: string | null;
  risk_score: number;
  cost_impact: number;
}

const MODE_COLORS: Record<string, string> = {
  autonomous: 'bg-green-100 text-green-800',
  guarded: 'bg-yellow-100 text-yellow-800',
  manual: 'bg-red-100 text-red-800',
};

export default function PolicyEvaluationsPage() {
  const brandId = useBrandId();
  const [rows, setRows] = useState<PolicyEval[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!brandId) return;
    setLoading(true);
    fetchPolicyEvaluations(brandId, '').then(setRows).finally(() => setLoading(false));
  }, [brandId]);

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand.</div>;

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold flex items-center gap-2"><Shield className="h-6 w-6" /> Policy Evaluations</h1>
      {loading ? <p>Loading…</p> : (
        <Card>
          <CardHeader><CardTitle>Policies ({rows.length})</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Action</TableHead>
                  <TableHead>Mode</TableHead>
                  <TableHead>Approval</TableHead>
                  <TableHead>Risk</TableHead>
                  <TableHead>Cost</TableHead>
                  <TableHead>Hard Stop</TableHead>
                  <TableHead>Rollback</TableHead>
                  <TableHead>Reason</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map(r => (
                  <TableRow key={r.id}>
                    <TableCell className="font-mono text-xs max-w-xs truncate">{r.action_ref}</TableCell>
                    <TableCell><span className={`rounded px-2 py-0.5 text-xs font-semibold ${MODE_COLORS[r.policy_mode] || 'bg-gray-100'}`}>{r.policy_mode}</span></TableCell>
                    <TableCell>{r.approval_needed ? 'Yes' : 'No'}</TableCell>
                    <TableCell>{(r.risk_score * 100).toFixed(0)}%</TableCell>
                    <TableCell>${r.cost_impact.toFixed(0)}</TableCell>
                    <TableCell className="max-w-xs truncate">{r.hard_stop_rule ?? '—'}</TableCell>
                    <TableCell className="max-w-xs truncate">{r.rollback_rule ?? '—'}</TableCell>
                    <TableCell className="max-w-xs truncate">{r.reason}</TableCell>
                  </TableRow>
                ))}
                {rows.length === 0 && <TableRow><TableCell colSpan={8} className="text-center text-muted-foreground">No policy evaluations.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
