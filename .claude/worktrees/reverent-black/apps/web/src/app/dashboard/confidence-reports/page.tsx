'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchConfidenceReports } from '@/lib/brain-phase-b-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Gauge } from 'lucide-react';

interface ConfReport {
  id: string;
  scope_label: string;
  confidence_score: number;
  confidence_band: string;
  signal_strength: number;
  data_completeness: number;
  saturation_risk: number;
  blocker_severity: number;
  explanation: string | null;
}

const BAND_COLORS: Record<string, string> = {
  very_high: 'bg-green-100 text-green-800',
  high: 'bg-emerald-100 text-emerald-800',
  medium: 'bg-yellow-100 text-yellow-800',
  low: 'bg-orange-100 text-orange-800',
  very_low: 'bg-red-100 text-red-800',
};

export default function ConfidenceReportsPage() {
  const brandId = useBrandId();
  const [rows, setRows] = useState<ConfReport[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!brandId) return;
    setLoading(true);
    fetchConfidenceReports(brandId, '').then(setRows).finally(() => setLoading(false));
  }, [brandId]);

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand.</div>;

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold flex items-center gap-2"><Gauge className="h-6 w-6" /> Confidence Reports</h1>
      {loading ? <p>Loading…</p> : (
        <Card>
          <CardHeader><CardTitle>Reports ({rows.length})</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Scope</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Band</TableHead>
                  <TableHead>Signal</TableHead>
                  <TableHead>Data</TableHead>
                  <TableHead>Saturation</TableHead>
                  <TableHead>Blockers</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map(r => (
                  <TableRow key={r.id}>
                    <TableCell className="font-mono text-xs max-w-xs truncate">{r.scope_label}</TableCell>
                    <TableCell className="font-semibold">{(r.confidence_score * 100).toFixed(0)}%</TableCell>
                    <TableCell><span className={`rounded px-2 py-0.5 text-xs font-semibold ${BAND_COLORS[r.confidence_band] || 'bg-gray-100'}`}>{r.confidence_band}</span></TableCell>
                    <TableCell>{(r.signal_strength * 100).toFixed(0)}%</TableCell>
                    <TableCell>{(r.data_completeness * 100).toFixed(0)}%</TableCell>
                    <TableCell>{(r.saturation_risk * 100).toFixed(0)}%</TableCell>
                    <TableCell>{(r.blocker_severity * 100).toFixed(0)}%</TableCell>
                  </TableRow>
                ))}
                {rows.length === 0 && <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground">No confidence reports.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
