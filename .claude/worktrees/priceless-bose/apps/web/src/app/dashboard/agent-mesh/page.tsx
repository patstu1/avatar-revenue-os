'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchAgentRegistry, fetchAgentRunsV2, recomputeAgentMesh } from '@/lib/brain-phase-c-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Bot } from 'lucide-react';

interface AgentEntry { id: string; agent_slug: string; agent_label: string; description: string | null; memory_scopes_json: string[] | null; upstream_agents_json: string[] | null; downstream_agents_json: string[] | null; }
interface AgentRun { id: string; agent_slug: string; run_status: string; confidence: number; outputs_json: Record<string, unknown> | null; memory_refs_json: string[] | null; explanation: string | null; }

const STATUS_COLORS: Record<string, string> = { completed: 'bg-green-100 text-green-800', running: 'bg-blue-100 text-blue-800', error: 'bg-red-100 text-red-800' };

export default function AgentMeshPage() {
  const brandId = useBrandId();
  const [agents, setAgents] = useState<AgentEntry[]>([]);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [recomputing, setRecomputing] = useState(false);

  const load = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      const [a, r] = await Promise.all([fetchAgentRegistry(brandId, ''), fetchAgentRunsV2(brandId, '')]);
      setAgents(a); setRuns(r);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [brandId]);

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    try { await recomputeAgentMesh(brandId, ''); await load(); } finally { setRecomputing(false); }
  };

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand.</div>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2"><Bot className="h-6 w-6" /> Agent Mesh</h1>
        <button onClick={handleRecompute} disabled={recomputing} className="rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
          {recomputing ? 'Running…' : 'Run Agent Mesh Cycle'}
        </button>
      </div>

      {loading ? <p>Loading…</p> : (
        <>
          <Card>
            <CardHeader><CardTitle>Agent Registry ({agents.length})</CardTitle></CardHeader>
            <CardContent>
              <Table>
                <TableHeader><TableRow><TableHead>Agent</TableHead><TableHead>Description</TableHead><TableHead>Memory Scopes</TableHead><TableHead>Upstream</TableHead><TableHead>Downstream</TableHead></TableRow></TableHeader>
                <TableBody>
                  {agents.map(a => (
                    <TableRow key={a.id}>
                      <TableCell className="font-semibold">{a.agent_label}</TableCell>
                      <TableCell className="max-w-xs truncate">{a.description}</TableCell>
                      <TableCell className="text-xs">{a.memory_scopes_json?.join(', ') ?? '—'}</TableCell>
                      <TableCell className="text-xs">{a.upstream_agents_json?.join(', ') || '—'}</TableCell>
                      <TableCell className="text-xs">{a.downstream_agents_json?.join(', ') || '—'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Recent Agent Runs ({runs.length})</CardTitle></CardHeader>
            <CardContent>
              <Table>
                <TableHeader><TableRow><TableHead>Agent</TableHead><TableHead>Status</TableHead><TableHead>Confidence</TableHead><TableHead>Memory Refs</TableHead><TableHead>Explanation</TableHead></TableRow></TableHeader>
                <TableBody>
                  {runs.map(r => (
                    <TableRow key={r.id}>
                      <TableCell className="font-semibold">{r.agent_slug}</TableCell>
                      <TableCell><span className={`rounded px-2 py-0.5 text-xs font-semibold ${STATUS_COLORS[r.run_status] || 'bg-gray-100'}`}>{r.run_status}</span></TableCell>
                      <TableCell>{(r.confidence * 100).toFixed(0)}%</TableCell>
                      <TableCell className="text-xs max-w-xs truncate">{r.memory_refs_json?.join(', ') || '—'}</TableCell>
                      <TableCell className="max-w-xs truncate">{r.explanation ?? '—'}</TableCell>
                    </TableRow>
                  ))}
                  {runs.length === 0 && <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground">No runs yet.</TableCell></TableRow>}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
