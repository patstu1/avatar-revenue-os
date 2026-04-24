'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { providerRegistryApi } from '@/lib/provider-registry-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, AlertTriangle } from 'lucide-react';

interface Blocker {
  provider_key: string;
  blocker_type: string;
  severity: string;
  description: string;
  operator_action_needed: string;
}

const severityBadge = (severity: string) => {
  switch (severity) {
    case 'high':
      return 'bg-red-600';
    case 'medium':
      return 'bg-yellow-600';
    case 'low':
      return 'bg-gray-600';
    default:
      return 'bg-gray-600';
  }
};

export default function ProviderBlockersDashboard() {
  const brandId = useBrandId();
  const [blockers, setBlockers] = useState<Blocker[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await providerRegistryApi.listBlockers(brandId);
      setBlockers(res.data);
    } catch {
      setError('Failed to load provider blockers.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading provider blockers...</div>;
  if (error)
    return (
      <Alert variant="destructive">
        <Terminal className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );

  const highCount = blockers.filter((b) => b.severity === 'high').length;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <AlertTriangle className="h-8 w-8 text-red-400" />
        <div>
          <h1 className="text-3xl font-bold">Provider Blockers</h1>
          {blockers.length > 0 && (
            <p className="text-sm text-gray-400 mt-1">
              {blockers.length} blocker{blockers.length !== 1 ? 's' : ''} found
              {highCount > 0 && <span className="text-red-400 ml-1">({highCount} high severity)</span>}
            </p>
          )}
        </div>
      </div>

      {blockers.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {blockers.map((b, idx) => (
            <Card key={`${b.provider_key}-${idx}`} className="border-gray-700">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="font-mono text-base">{b.provider_key}</CardTitle>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium text-white ${severityBadge(b.severity)}`}>
                    {b.severity}
                  </span>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Type</p>
                  <p className="text-sm text-gray-300">{b.blocker_type?.replace(/_/g, ' ')}</p>
                </div>
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Description</p>
                  <p className="text-sm text-gray-400">{b.description}</p>
                </div>
                <div className="pt-2 border-t border-gray-700">
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Action Needed</p>
                  <p className="text-sm text-yellow-300 font-mono">{b.operator_action_needed}</p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="py-8">
            <p className="text-center text-gray-500">No blockers detected. All provider credentials are configured.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
