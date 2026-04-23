'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { providerRegistryApi } from '@/lib/provider-registry-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, Activity, CheckCircle2, XCircle } from 'lucide-react';

interface ReadinessEntry {
  provider_key: string;
  credential_status: string;
  integration_status: string;
  is_ready: boolean;
  missing_env_keys: string[];
  operator_action: string | null;
}

const credentialColor = (status: string) => {
  switch (status) {
    case 'configured':
    case 'not_required':
      return 'bg-green-600';
    case 'partial':
      return 'bg-yellow-600';
    case 'not_configured':
      return 'bg-red-600';
    default:
      return 'bg-gray-600';
  }
};

export default function ProviderReadinessDashboard() {
  const brandId = useBrandId();
  const [entries, setEntries] = useState<ReadinessEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await providerRegistryApi.listReadiness(brandId);
      setEntries(res.data);
    } catch {
      setError('Failed to load provider readiness.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading provider readiness...</div>;
  if (error)
    return (
      <Alert variant="destructive">
        <Terminal className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );

  const readyCount = entries.filter((e) => e.is_ready).length;
  const totalCount = entries.length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Activity className="h-8 w-8 text-emerald-400" />
          <div>
            <h1 className="text-3xl font-bold">Provider Readiness</h1>
            {totalCount > 0 && (
              <p className="text-sm text-gray-400 mt-1">
                {readyCount} / {totalCount} providers ready
              </p>
            )}
          </div>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Readiness Report</CardTitle>
        </CardHeader>
        <CardContent>
          {entries.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Provider</TableHead>
                  <TableHead>Credentials</TableHead>
                  <TableHead>Integration</TableHead>
                  <TableHead>Ready</TableHead>
                  <TableHead>Missing Env Keys</TableHead>
                  <TableHead>Operator Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries.map((e) => (
                  <TableRow key={e.provider_key}>
                    <TableCell className="font-mono text-sm font-medium">{e.provider_key}</TableCell>
                    <TableCell>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium text-white ${credentialColor(e.credential_status)}`}>
                        {e.credential_status?.replace(/_/g, ' ')}
                      </span>
                    </TableCell>
                    <TableCell className="text-gray-400">{e.integration_status}</TableCell>
                    <TableCell>
                      {e.is_ready ? (
                        <CheckCircle2 className="h-5 w-5 text-green-400" />
                      ) : (
                        <XCircle className="h-5 w-5 text-red-400" />
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-gray-400 font-mono">
                      {e.missing_env_keys?.length > 0 ? e.missing_env_keys.join(', ') : '—'}
                    </TableCell>
                    <TableCell className="text-sm text-gray-400 max-w-[280px] truncate" title={e.operator_action ?? ''}>
                      {e.operator_action ?? '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-center text-gray-500 py-8">
              No readiness data. Run an audit from Provider Registry first.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
