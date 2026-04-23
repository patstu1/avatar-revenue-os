'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchRecoveryAutonomy, recomputeRecoveryAutonomy } from '@/lib/autonomous-phase-c-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Recycle, RefreshCcw } from 'lucide-react';

interface Esc {
  id: string;
  incident_type: string;
  escalation_requirement: string;
  severity: string;
  status: string;
}

interface Heal {
  id: string;
  incident_type: string;
  action_taken: string;
  action_mode: string;
  escalation_requirement: string;
  confidence: number;
}

export default function RecoveryAutonomyPage() {
  const brandId = useBrandId();
  const [escalations, setEscalations] = useState<Esc[]>([]);
  const [healing, setHealing] = useState<Heal[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      const data = await fetchRecoveryAutonomy(brandId, '');
      setEscalations(data.escalations || []);
      setHealing(data.self_healing || []);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [brandId]);

  const recompute = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      await recomputeRecoveryAutonomy(brandId, '');
      await load();
    } catch { /* empty */ }
    setLoading(false);
  };

  if (!brandId) return <p className="p-8 text-zinc-400">Select a brand first.</p>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Recycle className="h-6 w-6 text-rose-600" />
          <h1 className="text-2xl font-bold">Recovery + Self-Healing</h1>
        </div>
        <Button onClick={recompute} disabled={loading} size="sm" variant="outline">
          <RefreshCcw className="mr-2 h-4 w-4" /> Recompute
        </Button>
      </div>
      <Card>
        <CardHeader><CardTitle>Recovery escalations ({escalations.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Incident</TableHead>
                <TableHead>Severity</TableHead>
                <TableHead>Escalation</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {escalations.map((e) => (
                <TableRow key={e.id}>
                  <TableCell className="font-mono text-xs">{e.incident_type}</TableCell>
                  <TableCell>{e.severity}</TableCell>
                  <TableCell>{e.escalation_requirement}</TableCell>
                  <TableCell>{e.status}</TableCell>
                </TableRow>
              ))}
              {escalations.length === 0 && (
                <TableRow><TableCell colSpan={4} className="text-center text-zinc-400">None</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Self-healing actions ({healing.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Incident</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Mode</TableHead>
                <TableHead>Escalation</TableHead>
                <TableHead>Confidence</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {healing.map((h) => (
                <TableRow key={h.id}>
                  <TableCell className="font-mono text-xs">{h.incident_type}</TableCell>
                  <TableCell className="max-w-xs truncate text-xs">{h.action_taken}</TableCell>
                  <TableCell>{h.action_mode}</TableCell>
                  <TableCell>{h.escalation_requirement}</TableCell>
                  <TableCell>{(h.confidence * 100).toFixed(0)}%</TableCell>
                </TableRow>
              ))}
              {healing.length === 0 && (
                <TableRow><TableCell colSpan={5} className="text-center text-zinc-400">None</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
