'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchBufferProfiles, createBufferProfile } from '@/lib/buffer-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Send } from 'lucide-react';

interface Profile { id: string; platform: string; display_name: string; buffer_profile_id: string | null; credential_status: string; last_sync_status: string; is_active: boolean; }

const CRED_COLORS: Record<string, string> = { connected: 'bg-green-100 text-green-800', not_connected: 'bg-red-100 text-red-800', expired: 'bg-orange-100 text-orange-800', revoked: 'bg-red-100 text-red-800' };

export default function BufferProfilesPage() {
  const brandId = useBrandId();
  const [rows, setRows] = useState<Profile[]>([]);
  const [loading, setLoading] = useState(false);
  const [newName, setNewName] = useState('');
  const [newPlatform, setNewPlatform] = useState('tiktok');

  useEffect(() => { if (brandId) { setLoading(true); fetchBufferProfiles(brandId, '').then(setRows).finally(() => setLoading(false)); } }, [brandId]);

  const handleCreate = async () => {
    if (!brandId || !newName) return;
    await createBufferProfile(brandId, { display_name: newName, platform: newPlatform }, '');
    setRows(await fetchBufferProfiles(brandId, ''));
    setNewName('');
  };

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand.</div>;

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold flex items-center gap-2"><Send className="h-6 w-6" /> Buffer Profiles</h1>
      <p className="text-sm text-muted-foreground">Buffer is the primary social distribution layer. Connect profiles here to enable publishing.</p>

      <Card>
        <CardHeader><CardTitle>Add Profile</CardTitle></CardHeader>
        <CardContent className="flex gap-3">
          <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="Display name" className="border rounded px-3 py-1.5 text-sm flex-1" />
          <select value={newPlatform} onChange={e => setNewPlatform(e.target.value)} className="border rounded px-3 py-1.5 text-sm">
            {['tiktok','instagram','youtube','twitter','reddit','linkedin','facebook'].map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          <button onClick={handleCreate} className="rounded bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90">Add</button>
        </CardContent>
      </Card>

      {loading ? <p>Loading…</p> : (
        <Card>
          <CardHeader><CardTitle>Profiles ({rows.length})</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Platform</TableHead><TableHead>Buffer ID</TableHead><TableHead>Credential</TableHead><TableHead>Sync</TableHead><TableHead>Active</TableHead></TableRow></TableHeader>
              <TableBody>
                {rows.map(r => (
                  <TableRow key={r.id}>
                    <TableCell className="font-semibold">{r.display_name}</TableCell>
                    <TableCell>{r.platform}</TableCell>
                    <TableCell className="font-mono text-xs">{r.buffer_profile_id || '—'}</TableCell>
                    <TableCell><span className={`rounded px-2 py-0.5 text-xs font-semibold ${CRED_COLORS[r.credential_status] || 'bg-gray-100'}`}>{r.credential_status}</span></TableCell>
                    <TableCell>{r.last_sync_status}</TableCell>
                    <TableCell>{r.is_active ? 'Yes' : 'No'}</TableCell>
                  </TableRow>
                ))}
                {rows.length === 0 && <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground">No profiles. Add one above.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
