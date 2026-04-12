'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, Gauge, RefreshCcw } from 'lucide-react';

interface OutputReport {
  id: string;
  account_id: string;
  platform: string;
  current_output_per_week: number;
  recommended_output_per_week: number;
  max_safe_output_per_week: number;
  max_profitable_output_per_week: number;
  throttle_reason: string | null;
  confidence: number;
}

function truncId(id: string): string {
  return id.length > 8 ? id.slice(0, 8) + '…' : id;
}

export default function MaxOutputPage() {
  const brandId = useBrandId();
  const [reports, setReports] = useState<OutputReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.get(`/api/v1/brands/${brandId}/account-output`);
      const data = res.data;
      setReports(Array.isArray(data) ? data : []);
    } catch {
      setError('Failed to load account output reports.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await api.post(`/api/v1/brands/${brandId}/account-output/recompute`);
      setTimeout(fetchData, 3000);
    } catch {
      setError('Failed to recompute account output.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => { fetchData(); }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading account max output…</div>;
  if (error)
    return (
      <Alert variant="destructive">
        <Terminal className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Gauge className="h-8 w-8 text-emerald-400" />
          <div>
            <h1 className="text-3xl font-bold">Account Max Output</h1>
            <p className="text-sm text-muted-foreground max-w-3xl mt-1">
              Per-account output ceiling analysis. Compares current posting rate against safe,
              profitable, and recommended maximums — with throttle reasons when limits apply.
            </p>
          </div>
        </div>
        <Button onClick={handleRecompute} disabled={recomputing}>
          {recomputing ? (
            <><RefreshCcw className="mr-2 h-4 w-4 animate-spin" />Recomputing…</>
          ) : (
            <><RefreshCcw className="mr-2 h-4 w-4" />Recompute</>
          )}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Output Reports</CardTitle>
        </CardHeader>
        <CardContent>
          {reports.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Account</TableHead>
                    <TableHead>Platform</TableHead>
                    <TableHead className="text-right">Current/wk</TableHead>
                    <TableHead className="text-right">Recommended/wk</TableHead>
                    <TableHead className="text-right">Max Safe/wk</TableHead>
                    <TableHead className="text-right">Max Profitable/wk</TableHead>
                    <TableHead>Throttle Reason</TableHead>
                    <TableHead className="text-right">Confidence</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {reports.map((r) => {
                    const isThrottled = !!r.throttle_reason;
                    return (
                      <TableRow key={r.id} className={isThrottled ? 'bg-amber-900/10' : ''}>
                        <TableCell className="font-mono text-xs" title={r.account_id}>
                          {truncId(r.account_id)}
                        </TableCell>
                        <TableCell className="text-xs">{r.platform}</TableCell>
                        <TableCell className="text-right text-xs">{Number(r.current_output_per_week ?? 0).toFixed(1)}</TableCell>
                        <TableCell className="text-right text-xs">{Number(r.recommended_output_per_week ?? 0).toFixed(1)}</TableCell>
                        <TableCell className="text-right text-xs">{Number(r.max_safe_output_per_week ?? 0).toFixed(1)}</TableCell>
                        <TableCell className="text-right text-xs">{Number(r.max_profitable_output_per_week ?? 0).toFixed(1)}</TableCell>
                        <TableCell className={`text-xs ${isThrottled ? 'text-amber-400' : 'text-muted-foreground'}`}>
                          {r.throttle_reason ?? '—'}
                        </TableCell>
                        <TableCell className="text-right text-xs">{Number(r.confidence ?? 0).toFixed(2)}</TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">No output reports. Recompute to generate.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
