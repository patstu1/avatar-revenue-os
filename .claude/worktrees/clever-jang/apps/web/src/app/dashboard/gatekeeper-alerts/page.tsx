'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { gatekeeperApi } from '@/lib/gatekeeper-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, Bell } from 'lucide-react';

interface GatekeeperAlert {
  gate_type: string;
  severity: string;
  title: string;
  description: string;
  source_module: string;
  operator_action: string;
  resolved: boolean;
}

const severityBadge = (s: string) => {
  switch (s) {
    case 'critical': return 'bg-red-600';
    case 'high': return 'bg-orange-600';
    case 'medium': return 'bg-yellow-600';
    case 'low': return 'bg-gray-600';
    default: return 'bg-gray-600';
  }
};

const gateTypeBadge = (t: string) => {
  switch (t) {
    case 'completion': return 'bg-blue-600';
    case 'truth': return 'bg-purple-600';
    case 'closure': return 'bg-cyan-600';
    case 'tests': return 'bg-green-600';
    case 'dependencies': return 'bg-yellow-700';
    case 'contradictions': return 'bg-red-700';
    case 'commands': return 'bg-indigo-600';
    case 'expansion': return 'bg-orange-700';
    default: return 'bg-gray-600';
  }
};

export default function GatekeeperAlertsDashboard() {
  const brandId = useBrandId();
  const [alerts, setAlerts] = useState<GatekeeperAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await gatekeeperApi.alerts(brandId);
      setAlerts(Array.isArray(res.data) ? res.data : []);
    } catch {
      setError('Failed to load gatekeeper alerts.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [brandId]);

  if (loading) return <div className="text-center py-8 text-gray-400">Loading gatekeeper alerts...</div>;
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
        <Bell className="h-8 w-8 text-pink-400" />
        <h1 className="text-3xl font-bold text-white">Gatekeeper Alerts</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-white">Active Alerts ({alerts.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {alerts.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Gate Type</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Source Module</TableHead>
                  <TableHead>Action Required</TableHead>
                  <TableHead>Resolved</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {alerts.map((a, i) => (
                  <TableRow key={i}>
                    <TableCell>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium text-white ${gateTypeBadge(a.gate_type)}`}>
                        {a.gate_type}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium text-white ${severityBadge(a.severity)}`}>
                        {a.severity}
                      </span>
                    </TableCell>
                    <TableCell className="font-medium text-gray-200">{a.title}</TableCell>
                    <TableCell className="max-w-[240px] truncate text-sm text-gray-400" title={a.description}>
                      {a.description}
                    </TableCell>
                    <TableCell className="text-gray-300">{a.source_module}</TableCell>
                    <TableCell className="max-w-[200px] truncate text-sm text-gray-400" title={a.operator_action}>
                      {a.operator_action}
                    </TableCell>
                    <TableCell>
                      <span className={a.resolved ? 'text-green-400' : 'text-red-400 font-semibold'}>
                        {a.resolved ? 'Resolved' : 'Open'}
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-center text-gray-500 py-8">No gatekeeper alerts. Alerts are generated when gates are recomputed.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
