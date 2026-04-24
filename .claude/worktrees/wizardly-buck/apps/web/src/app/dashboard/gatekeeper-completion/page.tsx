'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { gatekeeperApi } from '@/lib/gatekeeper-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, CheckSquare, RefreshCcw } from 'lucide-react';

interface CompletionRow {
  module_name: string;
  completion_score: number;
  missing_layers: string[];
  gate_passed: boolean;
  severity: string;
}

const severityColor = (s: string) => {
  switch (s) {
    case 'critical': return 'bg-red-600';
    case 'high': return 'bg-orange-600';
    case 'medium': return 'bg-yellow-600';
    case 'low': return 'bg-gray-600';
    default: return 'bg-gray-600';
  }
};

export default function CompletionGateDashboard() {
  const brandId = useBrandId();
  const [rows, setRows] = useState<CompletionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await gatekeeperApi.completion(brandId);
      setRows(Array.isArray(res.data) ? res.data : []);
    } catch {
      setError('Failed to load completion gate data.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await gatekeeperApi.recomputeCompletion(brandId);
      setTimeout(fetchData, 3000);
    } catch {
      setError('Failed to recompute completion gate.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => { fetchData(); }, [brandId]);

  if (loading) return <div className="text-center py-8 text-gray-400">Loading completion gate...</div>;
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
          <CheckSquare className="h-8 w-8 text-blue-400" />
          <h1 className="text-3xl font-bold text-white">Completion Gate</h1>
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
          <CardTitle className="text-white">Module Completion ({rows.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {rows.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Module</TableHead>
                  <TableHead>Completion</TableHead>
                  <TableHead>Missing Layers</TableHead>
                  <TableHead>Gate</TableHead>
                  <TableHead>Severity</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow key={r.module_name}>
                    <TableCell className="font-medium text-gray-200">{r.module_name}</TableCell>
                    <TableCell className="text-gray-300">
                      {(r.completion_score * 100).toFixed(0)}%
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {(r.missing_layers ?? []).map((l) => (
                          <span key={l} className="px-2 py-0.5 rounded text-xs bg-gray-700 text-gray-300">
                            {l}
                          </span>
                        ))}
                        {(!r.missing_layers || r.missing_layers.length === 0) && (
                          <span className="text-xs text-gray-500">—</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium text-white ${r.gate_passed ? 'bg-green-600' : 'bg-red-600'}`}>
                        {r.gate_passed ? 'PASS' : 'FAIL'}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium text-white ${severityColor(r.severity)}`}>
                        {r.severity}
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-center text-gray-500 py-8">No completion gate data. Recompute to generate.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
