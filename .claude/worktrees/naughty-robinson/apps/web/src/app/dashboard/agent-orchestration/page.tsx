'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchAgentRuns } from '@/lib/autonomous-phase-d-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Bot } from 'lucide-react';

interface AgentRun {
  id: string;
  agent_type: string;
  run_status: string;
  output_json: Record<string, unknown> | null;
  started_at: string | null;
}

interface AgentMsg {
  id: string;
  sender_agent: string;
  receiver_agent: string | null;
  message_type: string;
  explanation: string | null;
}

export default function AgentOrchestrationPage() {
  const brandId = useBrandId();
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [messages, setMessages] = useState<AgentMsg[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      const data = await fetchAgentRuns(brandId, '');
      setRuns(data.runs || []);
      setMessages(data.messages || []);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [brandId]);

  if (!brandId) return <p className="p-8 text-zinc-400">Select a brand first.</p>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-3">
        <Bot className="h-6 w-6 text-indigo-500" />
        <h1 className="text-2xl font-bold">Agent Orchestration</h1>
      </div>
      <Card>
        <CardHeader><CardTitle>Agent runs ({runs.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Agent</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Recommendation</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-mono text-xs">{r.agent_type}</TableCell>
                  <TableCell>{r.run_status}</TableCell>
                  <TableCell className="max-w-sm truncate text-xs">
                    {r.output_json ? (r.output_json as Record<string, string>).recommendation ?? '—' : '—'}
                  </TableCell>
                </TableRow>
              ))}
              {runs.length === 0 && (
                <TableRow><TableCell colSpan={3} className="text-center text-zinc-400">No agent runs yet</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Inter-agent messages ({messages.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>From</TableHead>
                <TableHead>To</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Explanation</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {messages.map((m) => (
                <TableRow key={m.id}>
                  <TableCell className="font-mono text-xs">{m.sender_agent}</TableCell>
                  <TableCell className="font-mono text-xs">{m.receiver_agent ?? '—'}</TableCell>
                  <TableCell>{m.message_type}</TableCell>
                  <TableCell className="max-w-sm truncate text-xs">{m.explanation ?? '—'}</TableCell>
                </TableRow>
              ))}
              {messages.length === 0 && (
                <TableRow><TableCell colSpan={4} className="text-center text-zinc-400">No messages</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
