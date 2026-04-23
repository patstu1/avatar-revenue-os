'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { gatekeeperApi } from '@/lib/gatekeeper-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, RefreshCcw } from 'lucide-react';

interface CommandRow {
  command_source: string;
  command_summary: string;
  is_actionable: boolean;
  is_specific: boolean;
  has_measurable_outcome: boolean;
  quality_score: number;
  gate_passed: boolean;
}

export default function CommandQualityDashboard() {
  const brandId = useBrandId();
  const [rows, setRows] = useState<CommandRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await gatekeeperApi.operatorCommands(brandId);
      setRows(Array.isArray(res.data) ? res.data : []);
    } catch {
      setError('Failed to load operator command quality data.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await gatekeeperApi.recomputeOperatorCommands(brandId);
      setTimeout(fetchData, 3000);
    } catch {
      setError('Failed to recompute operator commands.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => { fetchData(); }, [brandId]);

  if (loading) return <div className="text-center py-8 text-gray-400">Loading command quality...</div>;
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
          <Terminal className="h-8 w-8 text-indigo-400" />
          <h1 className="text-3xl font-bold text-white">Operator Command Quality</h1>
        </div>
        <Button onClick={handleRecompute} disabled={recomputing}>
          {recomputing ? (
            <><RefreshCcw className="mr-2 h-4 w-4 animate-spin" />Recomputing...</>
          ) : (
            <><RefreshCcw className="mr-2 h-4 w-4" />Recompute</>
          )}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-white">Commands ({rows.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {rows.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Source</TableHead>
                  <TableHead>Summary</TableHead>
                  <TableHead>Actionable</TableHead>
                  <TableHead>Specific</TableHead>
                  <TableHead>Measurable</TableHead>
                  <TableHead>Quality</TableHead>
                  <TableHead>Gate</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r, i) => (
                  <TableRow key={`${r.command_source}-${i}`}>
                    <TableCell className="font-medium text-gray-200">{r.command_source}</TableCell>
                    <TableCell
                      className="max-w-[240px] truncate text-sm text-gray-400"
                      title={r.command_summary}
                    >
                      {r.command_summary}
                    </TableCell>
                    <TableCell>
                      <span className={r.is_actionable ? 'text-green-400' : 'text-red-400'}>
                        {r.is_actionable ? 'Yes' : 'No'}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className={r.is_specific ? 'text-green-400' : 'text-red-400'}>
                        {r.is_specific ? 'Yes' : 'No'}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className={r.has_measurable_outcome ? 'text-green-400' : 'text-red-400'}>
                        {r.has_measurable_outcome ? 'Yes' : 'No'}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className={`font-mono ${r.quality_score >= 0.7 ? 'text-green-400' : r.quality_score >= 0.4 ? 'text-yellow-400' : 'text-red-400'}`}>
                        {(r.quality_score * 100).toFixed(0)}%
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium text-white ${r.gate_passed ? 'bg-green-600' : 'bg-red-600'}`}>
                        {r.gate_passed ? 'PASS' : 'FAIL'}
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-center text-gray-500 py-8">No command quality data. Recompute to generate.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
