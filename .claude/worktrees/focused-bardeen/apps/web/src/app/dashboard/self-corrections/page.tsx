'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchSelfCorrections } from '@/lib/brain-phase-d-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Recycle } from 'lucide-react';

interface Correction { id: string; correction_type: string; reason: string; effect_target: string; severity: string; applied: boolean; confidence: number; explanation: string | null; }

const SEV_COLORS: Record<string, string> = { critical: 'bg-red-100 text-red-800', high: 'bg-orange-100 text-orange-800', medium: 'bg-yellow-100 text-yellow-800', low: 'bg-gray-100 text-gray-800' };

export default function SelfCorrectionsPage() {
  const brandId = useBrandId();
  const [rows, setRows] = useState<Correction[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => { if (brandId) { setLoading(true); fetchSelfCorrections(brandId, '').then(setRows).finally(() => setLoading(false)); } }, [brandId]);

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand.</div>;

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold flex items-center gap-2"><Recycle className="h-6 w-6" /> Self-Corrections</h1>
      {loading ? <p>Loading…</p> : (
        <Card>
          <CardHeader><CardTitle>Corrections ({rows.length})</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader><TableRow><TableHead>Type</TableHead><TableHead>Target</TableHead><TableHead>Severity</TableHead><TableHead>Applied</TableHead><TableHead>Confidence</TableHead><TableHead>Reason</TableHead></TableRow></TableHeader>
              <TableBody>
                {rows.map(r => (
                  <TableRow key={r.id}>
                    <TableCell className="font-semibold">{r.correction_type}</TableCell>
                    <TableCell className="font-mono text-xs">{r.effect_target}</TableCell>
                    <TableCell><span className={`rounded px-2 py-0.5 text-xs font-semibold ${SEV_COLORS[r.severity] || 'bg-gray-100'}`}>{r.severity}</span></TableCell>
                    <TableCell>{r.applied ? 'Yes' : 'No'}</TableCell>
                    <TableCell>{(r.confidence * 100).toFixed(0)}%</TableCell>
                    <TableCell className="max-w-xs truncate">{r.reason}</TableCell>
                  </TableRow>
                ))}
                {rows.length === 0 && <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground">No corrections. System is healthy.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
