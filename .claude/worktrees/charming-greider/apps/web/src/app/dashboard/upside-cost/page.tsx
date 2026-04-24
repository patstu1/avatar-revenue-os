'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchUpsideCostEstimates } from '@/lib/brain-phase-b-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { DollarSign } from 'lucide-react';

interface UCEstimate {
  id: string;
  scope_label: string;
  expected_upside: number;
  expected_cost: number;
  expected_payback_days: number;
  operational_burden: number;
  concentration_risk: number;
  net_value: number;
}

export default function UpsideCostPage() {
  const brandId = useBrandId();
  const [rows, setRows] = useState<UCEstimate[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!brandId) return;
    setLoading(true);
    fetchUpsideCostEstimates(brandId, '').then(setRows).finally(() => setLoading(false));
  }, [brandId]);

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand.</div>;

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold flex items-center gap-2"><DollarSign className="h-6 w-6" /> Cost / Upside Estimates</h1>
      {loading ? <p>Loading…</p> : (
        <Card>
          <CardHeader><CardTitle>Estimates ({rows.length})</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Scope</TableHead>
                  <TableHead>Upside</TableHead>
                  <TableHead>Cost</TableHead>
                  <TableHead>Net</TableHead>
                  <TableHead>Payback</TableHead>
                  <TableHead>Ops Burden</TableHead>
                  <TableHead>Concentration</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map(r => (
                  <TableRow key={r.id}>
                    <TableCell className="font-mono text-xs max-w-xs truncate">{r.scope_label}</TableCell>
                    <TableCell className="text-green-400">${Number(r.expected_upside ?? 0).toFixed(0)}</TableCell>
                    <TableCell className="text-red-400">${Number(r.expected_cost ?? 0).toFixed(0)}</TableCell>
                    <TableCell className={(r.net_value ?? 0) >= 0 ? 'text-green-400 font-semibold' : 'text-red-400 font-semibold'}>${Number(r.net_value ?? 0).toFixed(0)}</TableCell>
                    <TableCell>{r.expected_payback_days ?? 0}d</TableCell>
                    <TableCell>{(Number(r.operational_burden ?? 0) * 100).toFixed(0)}%</TableCell>
                    <TableCell>{(Number(r.concentration_risk ?? 0) * 100).toFixed(0)}%</TableCell>
                  </TableRow>
                ))}
                {rows.length === 0 && <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground">No estimates.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
