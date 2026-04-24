'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useBrandId } from '@/hooks/useBrandId';
import { gatekeeperApi } from '@/lib/gatekeeper-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  Terminal,
  Shield,
  RefreshCcw,
  CheckSquare,
  Eye,
  GitMerge,
  TestTube2,
  Link2,
  AlertOctagon,
  Lock,
  Bell,
  ScrollText,
} from 'lucide-react';

interface GateSummary {
  total: number;
  passing: number;
  failing: number;
  critical: number;
}

const SUB_PAGES = [
  { href: '/dashboard/gatekeeper-completion', label: 'Completion Gate', icon: CheckSquare, color: 'text-blue-400' },
  { href: '/dashboard/gatekeeper-truth', label: 'Truth Gate', icon: Eye, color: 'text-purple-400' },
  { href: '/dashboard/gatekeeper-closure', label: 'Execution Closure', icon: GitMerge, color: 'text-cyan-400' },
  { href: '/dashboard/gatekeeper-tests', label: 'Test Sufficiency', icon: TestTube2, color: 'text-green-400' },
  { href: '/dashboard/gatekeeper-dependencies', label: 'Dependencies', icon: Link2, color: 'text-yellow-400' },
  { href: '/dashboard/gatekeeper-contradictions', label: 'Contradictions', icon: AlertOctagon, color: 'text-red-400' },
  { href: '/dashboard/gatekeeper-commands', label: 'Command Quality', icon: Terminal, color: 'text-indigo-400' },
  { href: '/dashboard/gatekeeper-expansion', label: 'Expansion Perms', icon: Lock, color: 'text-orange-400' },
  { href: '/dashboard/gatekeeper-alerts', label: 'Gatekeeper Alerts', icon: Bell, color: 'text-pink-400' },
  { href: '/dashboard/gatekeeper-ledger', label: 'Audit Ledger', icon: ScrollText, color: 'text-gray-400' },
];

function countGates(items: { gate_passed?: boolean; severity?: string }[]): GateSummary {
  const total = items.length;
  const passing = items.filter((i) => i.gate_passed === true).length;
  const failing = total - passing;
  const critical = items.filter((i) => i.severity === 'critical').length;
  return { total, passing, failing, critical };
}

export default function GatekeeperOverviewDashboard() {
  const brandId = useBrandId();
  const [summary, setSummary] = useState<GateSummary>({ total: 0, passing: 0, failing: 0, critical: 0 });
  const [loading, setLoading] = useState(true);
  const [auditing, setAuditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const [comp, truth, closure, tests, deps] = await Promise.allSettled([
        gatekeeperApi.completion(brandId),
        gatekeeperApi.truth(brandId),
        gatekeeperApi.executionClosure(brandId),
        gatekeeperApi.tests(brandId),
        gatekeeperApi.dependencies(brandId),
      ]);
      const all: { gate_passed?: boolean; severity?: string }[] = [];
      for (const r of [comp, truth, closure, tests, deps]) {
        if (r.status === 'fulfilled' && Array.isArray(r.value?.data)) {
          all.push(...r.value.data);
        }
      }
      setSummary(countGates(all));
    } catch {
      setError('Failed to load gatekeeper overview.');
    } finally {
      setLoading(false);
    }
  };

  const handleFullAudit = async () => {
    if (!brandId) return;
    setAuditing(true);
    setError(null);
    try {
      await gatekeeperApi.recomputeCompletion(brandId);
      await gatekeeperApi.recomputeTruth(brandId);
      await gatekeeperApi.recomputeExecutionClosure(brandId);
      await gatekeeperApi.recomputeTests(brandId);
      await gatekeeperApi.recomputeDependencies(brandId);
      await gatekeeperApi.recomputeContradictions(brandId);
      await gatekeeperApi.recomputeOperatorCommands(brandId);
      await gatekeeperApi.recomputeExpansionPermissions(brandId);
      setTimeout(fetchData, 3000);
    } catch {
      setError('Full audit failed. Some gates may not have recomputed.');
    } finally {
      setAuditing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [brandId]);

  if (loading) return <div className="text-center py-8 text-gray-400">Loading gatekeeper overview...</div>;
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
          <Shield className="h-8 w-8 text-blue-400" />
          <h1 className="text-3xl font-bold text-white">Gatekeeper Overview</h1>
        </div>
        <Button onClick={handleFullAudit} disabled={auditing}>
          {auditing ? (
            <>
              <RefreshCcw className="mr-2 h-4 w-4 animate-spin" />
              Running Full Audit...
            </>
          ) : (
            <>
              <RefreshCcw className="mr-2 h-4 w-4" />
              Run Full Audit
            </>
          )}
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-gray-400">Total Gates</p>
            <p className="text-3xl font-bold text-white">{summary.total}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-gray-400">Passing</p>
            <p className="text-3xl font-bold text-green-400">{summary.passing}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-gray-400">Failing</p>
            <p className="text-3xl font-bold text-red-400">{summary.failing}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-gray-400">Critical Alerts</p>
            <p className="text-3xl font-bold text-red-500">{summary.critical}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-white">Gate Sub-Pages</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {SUB_PAGES.map((page) => (
              <Link
                key={page.href}
                href={page.href}
                className="flex items-center gap-3 p-4 rounded-lg border border-gray-800 hover:border-gray-600 hover:bg-gray-800/50 transition-colors"
              >
                <page.icon className={`h-5 w-5 ${page.color}`} />
                <span className="text-sm font-medium text-gray-200">{page.label}</span>
              </Link>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
