'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchAgentRunsV2 } from '@/lib/brain-phase-c-api';
import { fetchBrainMemory } from '@/lib/brain-phase-a-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Library } from 'lucide-react';

interface MemEntry { id: string; entry_type: string; scope_type: string; summary: string; confidence: number; platform: string | null; }
interface AgentRun { id: string; agent_slug: string; memory_refs_json: string[] | null; confidence: number; run_status: string; }

export default function AgentMemoryPage() {
  const brandId = useBrandId();
  const [memories, setMemories] = useState<MemEntry[]>([]);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!brandId) return;
    setLoading(true);
    Promise.all([fetchBrainMemory(brandId, ''), fetchAgentRunsV2(brandId, '')])
      .then(([m, r]) => { setMemories(m); setRuns(r); })
      .finally(() => setLoading(false));
  }, [brandId]);

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand.</div>;

  const runsWithMemory = runs.filter(r => r.memory_refs_json && r.memory_refs_json.length > 0);

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold flex items-center gap-2"><Library className="h-6 w-6" /> Agent Memory Binding</h1>
      {loading ? <p>Loading…</p> : (
        <>
          <Card>
            <CardHeader><CardTitle>Brain Memory Entries ({memories.length})</CardTitle></CardHeader>
            <CardContent>
              <Table>
                <TableHeader><TableRow><TableHead>Type</TableHead><TableHead>Scope</TableHead><TableHead>Summary</TableHead><TableHead>Confidence</TableHead><TableHead>Platform</TableHead></TableRow></TableHeader>
                <TableBody>
                  {memories.slice(0, 30).map(m => (
                    <TableRow key={m.id}>
                      <TableCell className="font-semibold">{m.entry_type}</TableCell>
                      <TableCell>{m.scope_type}</TableCell>
                      <TableCell className="max-w-xs truncate">{m.summary}</TableCell>
                      <TableCell>{(m.confidence * 100).toFixed(0)}%</TableCell>
                      <TableCell>{m.platform ?? '—'}</TableCell>
                    </TableRow>
                  ))}
                  {memories.length === 0 && <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground">No memory entries. Recompute brain memory first.</TableCell></TableRow>}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Agent Runs with Memory Refs ({runsWithMemory.length})</CardTitle></CardHeader>
            <CardContent>
              <Table>
                <TableHeader><TableRow><TableHead>Agent</TableHead><TableHead>Status</TableHead><TableHead>Confidence</TableHead><TableHead>Memory Refs</TableHead></TableRow></TableHeader>
                <TableBody>
                  {runsWithMemory.map(r => (
                    <TableRow key={r.id}>
                      <TableCell className="font-semibold">{r.agent_slug}</TableCell>
                      <TableCell>{r.run_status}</TableCell>
                      <TableCell>{(r.confidence * 100).toFixed(0)}%</TableCell>
                      <TableCell className="text-xs max-w-xs truncate">{r.memory_refs_json?.join(', ')}</TableCell>
                    </TableRow>
                  ))}
                  {runsWithMemory.length === 0 && <TableRow><TableCell colSpan={4} className="text-center text-muted-foreground">No memory-bound runs yet.</TableCell></TableRow>}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
