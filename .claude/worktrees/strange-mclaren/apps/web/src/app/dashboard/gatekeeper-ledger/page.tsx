'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { gatekeeperApi } from '@/lib/gatekeeper-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, ScrollText } from 'lucide-react';

interface LedgerEntry {
  gate_type: string;
  action: string;
  module_name: string;
  result: string;
  created_at: string;
}

const resultBadge = (r: string) => {
  switch (r) {
    case 'pass':
    case 'passed':
      return 'bg-green-600';
    case 'fail':
    case 'failed':
      return 'bg-red-600';
    case 'warning':
      return 'bg-yellow-600';
    case 'skipped':
      return 'bg-gray-600';
    default:
      return 'bg-gray-600';
  }
};

const gateTypeBadge = (t: string) => {
  switch (t) {
    case 'completion': return 'bg-blue-600';
    case 'truth': return 'bg-purple-600';
    case 'closure': return 'bg-cyan-600';
    case 'tests': return 'bg-green-700';
    case 'dependencies': return 'bg-yellow-700';
    case 'contradictions': return 'bg-red-700';
    case 'commands': return 'bg-indigo-600';
    case 'expansion': return 'bg-orange-700';
    default: return 'bg-gray-600';
  }
};

export default function AuditLedgerDashboard() {
  const brandId = useBrandId();
  const [entries, setEntries] = useState<LedgerEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await gatekeeperApi.auditLedger(brandId);
      setEntries(Array.isArray(res.data) ? res.data : []);
    } catch {
      setError('Failed to load audit ledger.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [brandId]);

  if (loading) return <div className="text-center py-8 text-gray-400">Loading audit ledger...</div>;
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
      <div className="flex items-center gap-3">
        <ScrollText className="h-8 w-8 text-gray-400" />
        <h1 className="text-3xl font-bold text-white">Audit Ledger</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-white">Audit History ({entries.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {entries.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Gate Type</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Module</TableHead>
                  <TableHead>Result</TableHead>
                  <TableHead>Created At</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries.map((e, i) => (
                  <TableRow key={i}>
                    <TableCell>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium text-white ${gateTypeBadge(e.gate_type)}`}>
                        {e.gate_type}
                      </span>
                    </TableCell>
                    <TableCell className="text-gray-300">{e.action}</TableCell>
                    <TableCell className="font-medium text-gray-200">{e.module_name}</TableCell>
                    <TableCell>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium text-white ${resultBadge(e.result)}`}>
                        {e.result}
                      </span>
                    </TableCell>
                    <TableCell className="text-sm text-gray-400">
                      {e.created_at ? new Date(e.created_at).toLocaleString() : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-center text-gray-500 py-8">No audit ledger entries yet.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
