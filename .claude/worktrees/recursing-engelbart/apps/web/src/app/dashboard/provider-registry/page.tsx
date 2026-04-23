'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { providerRegistryApi } from '@/lib/provider-registry-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, Database, RefreshCcw } from 'lucide-react';

interface Provider {
  provider_key: string;
  display_name: string;
  category: string;
  provider_type: string;
  credential_status: string;
  integration_status: string;
  is_primary: boolean;
  is_fallback: boolean;
  is_optional: boolean;
  effective_status?: string;
  details_json?: { effective_status?: string } | null;
}

const statusColor = (status: string) => {
  switch (status) {
    case 'configured':
    case 'live':
      return 'bg-green-600';
    case 'partial':
      return 'bg-yellow-600';
    case 'not_configured':
    case 'blocked_by_credentials':
      return 'bg-red-600';
    default:
      return 'bg-gray-600';
  }
};

export default function ProviderRegistryDashboard() {
  const brandId = useBrandId();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [auditing, setAuditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await providerRegistryApi.listProviders(brandId);
      setProviders(res.data);
    } catch {
      setError('Failed to load provider registry.');
    } finally {
      setLoading(false);
    }
  };

  const handleAudit = async () => {
    if (!brandId) return;
    setAuditing(true);
    setError(null);
    try {
      await providerRegistryApi.runAudit(brandId);
      await fetchData();
    } catch {
      setError('Failed to run provider audit.');
    } finally {
      setAuditing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading provider registry...</div>;
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
          <Database className="h-8 w-8 text-blue-400" />
          <h1 className="text-3xl font-bold">Provider Registry</h1>
        </div>
        <Button onClick={handleAudit} disabled={auditing}>
          {auditing ? (
            <>
              <RefreshCcw className="mr-2 h-4 w-4 animate-spin" />
              Running Audit...
            </>
          ) : (
            <>
              <RefreshCcw className="mr-2 h-4 w-4" />
              Run Audit
            </>
          )}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Providers ({providers.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {providers.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Provider Key</TableHead>
                  <TableHead>Display Name</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Credentials</TableHead>
                  <TableHead>Integration</TableHead>
                  <TableHead>Effective</TableHead>
                  <TableHead>Role</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {providers.map((p) => {
                  const effective = p.effective_status ?? p.details_json?.effective_status ?? p.integration_status;
                  return (
                    <TableRow key={p.provider_key}>
                      <TableCell className="font-mono text-sm">{p.provider_key}</TableCell>
                      <TableCell className="font-medium">{p.display_name}</TableCell>
                      <TableCell className="text-gray-400">{p.category?.replace(/_/g, ' ')}</TableCell>
                      <TableCell className="text-gray-400">{p.provider_type}</TableCell>
                      <TableCell>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium text-white ${statusColor(p.credential_status)}`}>
                          {p.credential_status?.replace(/_/g, ' ')}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium text-white ${statusColor(p.integration_status)}`}>
                          {p.integration_status}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium text-white ${statusColor(effective)}`}>
                          {effective?.replace(/_/g, ' ')}
                        </span>
                      </TableCell>
                      <TableCell>
                        {p.is_primary && (
                          <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-600 text-white mr-1">Primary</span>
                        )}
                        {p.is_fallback && (
                          <span className="px-2 py-0.5 rounded text-xs font-medium bg-orange-600 text-white mr-1">Fallback</span>
                        )}
                        {p.is_optional && (
                          <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-600 text-white">Optional</span>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          ) : (
            <p className="text-center text-gray-500 py-8">No providers registered. Run an audit to populate.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
