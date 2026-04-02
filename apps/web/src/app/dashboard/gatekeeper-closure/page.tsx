'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { gatekeeperApi } from '@/lib/gatekeeper-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, GitMerge, RefreshCcw } from 'lucide-react';

interface ClosureRow {
  module_name: string;
  has_execution_path: boolean;
  has_downstream_action: boolean;
  dead_end_detected: boolean;
  stale_blocker_detected: boolean;
  orphaned_recommendation: boolean;
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

const boolCell = (val: boolean, invert = false) => {
  const isGood = invert ? !val : val;
  return (
    <span className={isGood ? 'text-green-400' : 'text-red-400'}>
      {val ? 'Yes' : 'No'}
    </span>
  );
};

export default function ExecutionClosureDashboard() {
  const brandId = useBrandId();
  const [rows, setRows] = useState<ClosureRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await gatekeeperApi.executionClosure(brandId);
      setRows(Array.isArray(res.data) ? res.data : []);
    } catch {
      setError('Failed to load execution closure data.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await gatekeeperApi.recomputeExecutionClosure(brandId);
      setTimeout(fetchData, 3000);
    } catch {
      setError('Failed to recompute execution closure.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => { fetchData(); }, [brandId]);

  if (loading) return <div className="text-center py-8 text-gray-400">Loading execution closure...</div>;
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
          <GitMerge className="h-8 w-8 text-cyan-400" />
          <h1 className="text-3xl font-bold text-white">Execution Closure</h1>
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
          <CardTitle className="text-white">Closure Analysis ({rows.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {rows.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Module</TableHead>
                  <TableHead>Execution Path</TableHead>
                  <TableHead>Downstream Action</TableHead>
                  <TableHead>Dead End</TableHead>
                  <TableHead>Stale Blocker</TableHead>
                  <TableHead>Orphaned Rec.</TableHead>
                  <TableHead>Gate</TableHead>
                  <TableHead>Severity</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow key={r.module_name}>
                    <TableCell className="font-medium text-gray-200">{r.module_name}</TableCell>
                    <TableCell>{boolCell(r.has_execution_path)}</TableCell>
                    <TableCell>{boolCell(r.has_downstream_action)}</TableCell>
                    <TableCell>{boolCell(r.dead_end_detected, true)}</TableCell>
                    <TableCell>{boolCell(r.stale_blocker_detected, true)}</TableCell>
                    <TableCell>{boolCell(r.orphaned_recommendation, true)}</TableCell>
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
            <p className="text-center text-gray-500 py-8">No execution closure data. Recompute to generate.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
