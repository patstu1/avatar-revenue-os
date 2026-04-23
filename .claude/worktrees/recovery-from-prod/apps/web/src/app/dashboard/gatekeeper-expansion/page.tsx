'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { gatekeeperApi } from '@/lib/gatekeeper-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, Lock, RefreshCcw, CheckCircle2, XCircle } from 'lucide-react';

interface ExpansionPermission {
  expansion_target: string;
  prerequisites_met: boolean;
  blockers_resolved: boolean;
  test_coverage_sufficient: boolean;
  dependencies_ready: boolean;
  permission_granted: boolean;
  blocking_reasons: string[];
}

const BoolIndicator = ({ value, trueLabel, falseLabel }: { value: boolean; trueLabel?: string; falseLabel?: string }) => (
  <div className="flex items-center gap-1.5">
    {value ? (
      <CheckCircle2 className="h-4 w-4 text-green-400" />
    ) : (
      <XCircle className="h-4 w-4 text-red-400" />
    )}
    <span className={value ? 'text-green-400 text-sm' : 'text-red-400 text-sm'}>
      {value ? (trueLabel ?? 'Yes') : (falseLabel ?? 'No')}
    </span>
  </div>
);

export default function ExpansionPermissionsDashboard() {
  const brandId = useBrandId();
  const [items, setItems] = useState<ExpansionPermission[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await gatekeeperApi.expansionPermissions(brandId);
      setItems(Array.isArray(res.data) ? res.data : []);
    } catch {
      setError('Failed to load expansion permissions.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await gatekeeperApi.recomputeExpansionPermissions(brandId);
      setTimeout(fetchData, 3000);
    } catch {
      setError('Failed to recompute expansion permissions.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => { fetchData(); }, [brandId]);

  if (loading) return <div className="text-center py-8 text-gray-400">Loading expansion permissions...</div>;
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
          <Lock className="h-8 w-8 text-orange-400" />
          <h1 className="text-3xl font-bold text-white">Expansion Permissions</h1>
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
          {items.map((p, i) => (
            <Card key={i} className={`border ${p.permission_granted ? 'border-green-600 bg-green-600/5' : 'border-red-600 bg-red-600/5'}`}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base text-white">{p.expansion_target}</CardTitle>
                  <span className={`px-3 py-1 rounded text-sm font-bold text-white ${p.permission_granted ? 'bg-green-600' : 'bg-red-600'}`}>
                    {p.permission_granted ? 'GRANTED' : 'BLOCKED'}
                  </span>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <BoolIndicator value={p.prerequisites_met} trueLabel="Prerequisites Met" falseLabel="Prerequisites Missing" />
                  <BoolIndicator value={p.blockers_resolved} trueLabel="Blockers Resolved" falseLabel="Blockers Remain" />
                  <BoolIndicator value={p.test_coverage_sufficient} trueLabel="Tests Sufficient" falseLabel="Tests Insufficient" />
                  <BoolIndicator value={p.dependencies_ready} trueLabel="Dependencies Ready" falseLabel="Dependencies Not Ready" />
                </div>
                {p.blocking_reasons && p.blocking_reasons.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-800">
                    <p className="text-xs font-medium text-gray-400 mb-1">Blocking Reasons:</p>
                    <ul className="space-y-1">
                      {p.blocking_reasons.map((reason, ri) => (
                        <li key={ri} className="text-sm text-red-400 flex items-start gap-2">
                          <span className="text-red-500 mt-0.5">•</span>
                          {reason}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="py-8">
            <p className="text-center text-gray-500">No expansion permissions data. Recompute to generate.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
