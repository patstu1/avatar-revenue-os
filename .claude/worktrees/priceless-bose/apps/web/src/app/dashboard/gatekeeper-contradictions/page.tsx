'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { gatekeeperApi } from '@/lib/gatekeeper-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, AlertOctagon, RefreshCcw } from 'lucide-react';

interface Contradiction {
  module_a: string;
  module_b: string;
  contradiction_type: string;
  description: string;
  severity: string;
}

const severityColor = (s: string) => {
  switch (s) {
    case 'critical': return 'border-red-600 bg-red-600/10';
    case 'high': return 'border-orange-600 bg-orange-600/10';
    case 'medium': return 'border-yellow-600 bg-yellow-600/10';
    case 'low': return 'border-gray-600 bg-gray-600/10';
    default: return 'border-gray-600 bg-gray-600/10';
  }
};

const severityBadge = (s: string) => {
  switch (s) {
    case 'critical': return 'bg-red-600';
    case 'high': return 'bg-orange-600';
    case 'medium': return 'bg-yellow-600';
    case 'low': return 'bg-gray-600';
    default: return 'bg-gray-600';
  }
};

export default function ContradictionsDashboard() {
  const brandId = useBrandId();
  const [items, setItems] = useState<Contradiction[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await gatekeeperApi.contradictions(brandId);
      setItems(Array.isArray(res.data) ? res.data : []);
    } catch {
      setError('Failed to load contradictions data.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await gatekeeperApi.recomputeContradictions(brandId);
      setTimeout(fetchData, 3000);
    } catch {
      setError('Failed to recompute contradictions.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => { fetchData(); }, [brandId]);

  if (loading) return <div className="text-center py-8 text-gray-400">Loading contradictions...</div>;
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
          <AlertOctagon className="h-8 w-8 text-red-400" />
          <h1 className="text-3xl font-bold text-white">Contradictions</h1>
        </div>
        <Button onClick={handleRecompute} disabled={recomputing}>
          {recomputing ? (
            <><RefreshCcw className="mr-2 h-4 w-4 animate-spin" />Recomputing...</>
          ) : (
            <><RefreshCcw className="mr-2 h-4 w-4" />Recompute</>
          )}
        </Button>
      </div>

      {items.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {items.map((c, i) => (
            <Card key={i} className={`border ${severityColor(c.severity)}`}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base text-white">
                    {c.module_a} <span className="text-gray-500 mx-2">vs</span> {c.module_b}
                  </CardTitle>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium text-white ${severityBadge(c.severity)}`}>
                    {c.severity}
                  </span>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-gray-400 mb-2">
                  <span className="font-medium text-gray-300">Type:</span> {c.contradiction_type}
                </p>
                <p className="text-sm text-gray-300">{c.description}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="py-8">
            <p className="text-center text-gray-500">No contradictions detected. Recompute to analyze.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
