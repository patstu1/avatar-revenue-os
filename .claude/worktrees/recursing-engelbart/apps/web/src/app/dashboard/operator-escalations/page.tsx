'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchOperatorEscalations } from '@/lib/autonomous-phase-d-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Bell } from 'lucide-react';

interface Esc {
  id: string;
  command: string;
  reason: string;
  urgency: string;
  confidence: number;
  expected_upside: number;
  risk: string;
  consequence_if_ignored: string | null;
  status: string;
}

interface Cmd {
  id: string;
  command_text: string;
  command_type: string;
  urgency: string;
  status: string;
}

export default function OperatorEscalationsPage() {
  const brandId = useBrandId();
  const [escalations, setEscalations] = useState<Esc[]>([]);
  const [commands, setCommands] = useState<Cmd[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      const data = await fetchOperatorEscalations(brandId, '');
      setEscalations(data.escalations || []);
      setCommands(data.commands || []);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [brandId]);

  if (!brandId) return <p className="p-8 text-zinc-400">Select a brand first.</p>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-3">
        <Bell className="h-6 w-6 text-amber-500" />
        <h1 className="text-2xl font-bold">Operator Escalations</h1>
      </div>
      <Card>
        <CardHeader><CardTitle>Escalation Events ({escalations.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Command</TableHead>
                <TableHead>Reason</TableHead>
                <TableHead>Urgency</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead>Upside</TableHead>
                <TableHead>Risk</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {escalations.map((e) => (
                <TableRow key={e.id}>
                  <TableCell className="max-w-xs truncate font-mono text-xs">{e.command}</TableCell>
                  <TableCell className="max-w-xs truncate text-xs">{e.reason}</TableCell>
                  <TableCell>{e.urgency}</TableCell>
                  <TableCell>{(e.confidence * 100).toFixed(0)}%</TableCell>
                  <TableCell>${e.expected_upside.toLocaleString()}</TableCell>
                  <TableCell>{e.risk}</TableCell>
                  <TableCell>{e.status}</TableCell>
                </TableRow>
              ))}
              {escalations.length === 0 && (
                <TableRow><TableCell colSpan={7} className="text-center text-zinc-400">No escalations</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Operator Commands ({commands.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Command</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Urgency</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {commands.map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="max-w-sm truncate font-mono text-xs">{c.command_text}</TableCell>
                  <TableCell>{c.command_type}</TableCell>
                  <TableCell>{c.urgency}</TableCell>
                  <TableCell>{c.status}</TableCell>
                </TableRow>
              ))}
              {commands.length === 0 && (
                <TableRow><TableCell colSpan={4} className="text-center text-zinc-400">No commands</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
