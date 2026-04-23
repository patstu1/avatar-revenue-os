'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { gatekeeperApi } from '@/lib/gatekeeper-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, Link2, RefreshCcw } from 'lucide-react';

interface DependencyRow {
  module_name: string;
  provider_key: string;
  credential_present: boolean;
  integration_live: boolean;
  blocked_by_external: boolean;
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

export default function DependencyReadinessDashboard() {
  const brandId = useBrandId();
  const [rows, setRows] = useState<DependencyRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await gatekeeperApi.dependencies(brandId);
      setRows(Array.isArray(res.data) ? res.data : []);
    } catch {
      setError('Failed to load dependency readiness data.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await gatekeeperApi.recomputeDependencies(brandId);
      setTimeout(fetchData, 3000);
    } catch {
      setError('Failed to recompute dependencies.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => { fetchData(); }, [brandId]);

  if (loading) return <div className="text-center py-8 text-gray-400">Loading dependency readiness...</div>;
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
          <Link2 className="h-8 w-8 text-yellow-400" />
          <h1 className="text-3xl font-bold text-white">Dependency Readiness</h1>
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
          <CardTitle className="text-white">Dependency Checks ({rows.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {rows.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Module</TableHead>
                  <TableHead>Provider</TableHead>
                  <TableHead>Credential</TableHead>
                  <TableHead>Integration</TableHead>
                  <TableHead>Blocked External</TableHead>
                  <TableHead>Gate</TableHead>
                  <TableHead>Severity</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r, i) => (
                  <TableRow key={`${r.module_name}-${r.provider_key}-${i}`}>
                    <TableCell className="font-medium text-gray-200">{r.module_name}</TableCell>
                    <TableCell className="font-mono text-sm text-gray-300">{r.provider_key}</TableCell>
                    <TableCell>
                      <span className={r.credential_present ? 'text-green-400' : 'text-red-400'}>
                        {r.credential_present ? 'Present' : 'Missing'}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className={r.integration_live ? 'text-green-400' : 'text-red-400'}>
                        {r.integration_live ? 'Live' : 'Down'}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className={r.blocked_by_external ? 'text-red-400 font-semibold' : 'text-green-400'}>
                        {r.blocked_by_external ? 'Blocked' : 'Clear'}
                      </span>
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
            <p className="text-center text-gray-500 py-8">No dependency data. Recompute to generate.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
