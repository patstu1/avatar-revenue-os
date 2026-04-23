'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { providerRegistryApi } from '@/lib/provider-registry-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, GitBranch } from 'lucide-react';

interface Dependency {
  provider_key: string;
  module_path: string;
  dependency_type: string;
  description: string;
}

const depTypeBadge = (type: string) => {
  switch (type) {
    case 'primary':
      return 'bg-blue-600';
    case 'required':
      return 'bg-red-600';
    case 'optional':
      return 'bg-gray-600';
    default:
      return 'bg-gray-600';
  }
};

export default function ProviderDependenciesDashboard() {
  const brandId = useBrandId();
  const [deps, setDeps] = useState<Dependency[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await providerRegistryApi.listDependencies(brandId);
      setDeps(res.data);
    } catch {
      setError('Failed to load provider dependencies.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading dependency map...</div>;
  if (error)
    return (
      <Alert variant="destructive">
        <Terminal className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );

  const grouped = deps.reduce<Record<string, Dependency[]>>((acc, d) => {
    (acc[d.provider_key] ||= []).push(d);
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <GitBranch className="h-8 w-8 text-purple-400" />
        <div>
          <h1 className="text-3xl font-bold">Provider Dependency Map</h1>
          <p className="text-sm text-gray-400 mt-1">
            {deps.length} dependencies across {Object.keys(grouped).length} providers
          </p>
        </div>
      </div>

      {Object.keys(grouped).length > 0 ? (
        Object.entries(grouped).map(([providerKey, items]) => (
          <Card key={providerKey}>
            <CardHeader>
              <CardTitle className="font-mono text-lg">{providerKey}</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Module Path</TableHead>
                    <TableHead>Dependency Type</TableHead>
                    <TableHead>Description</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((d, idx) => (
                    <TableRow key={`${d.provider_key}-${idx}`}>
                      <TableCell className="font-mono text-sm text-gray-300">{d.module_path}</TableCell>
                      <TableCell>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium text-white ${depTypeBadge(d.dependency_type)}`}>
                          {d.dependency_type}
                        </span>
                      </TableCell>
                      <TableCell className="text-sm text-gray-400">{d.description}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        ))
      ) : (
        <Card>
          <CardContent className="py-8">
            <p className="text-center text-gray-500">No dependency data. Run an audit from Provider Registry first.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
