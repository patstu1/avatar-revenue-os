"use client";
import { useEffect, useState } from "react";
import {
  fetchCrmContacts,
  fetchCrmSyncs,
  runCrmSync,
  createCrmContact,
} from "@/lib/live-execution-api";

const BRAND = "00000000-0000-0000-0000-000000000001";

export default function CrmSyncPage() {
  const [contacts, setContacts] = useState<any[]>([]);
  const [syncs, setSyncs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");

  async function load() {
    setLoading(true);
    const [c, s] = await Promise.all([fetchCrmContacts(BRAND), fetchCrmSyncs(BRAND)]);
    setContacts(c); setSyncs(s);
    setLoading(false);
  }

  async function addContact() {
    if (!email) return;
    await createCrmContact(BRAND, { email, name: name || undefined });
    setEmail(""); setName("");
    load();
  }

  useEffect(() => { load(); }, []);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">CRM / Audience Sync</h1>

      <div className="flex gap-3 items-end">
        <div>
          <label className="block text-sm font-medium">Email</label>
          <input value={email} onChange={e => setEmail(e.target.value)} className="border rounded p-2 w-64" />
        </div>
        <div>
          <label className="block text-sm font-medium">Name</label>
          <input value={name} onChange={e => setName(e.target.value)} className="border rounded p-2 w-48" />
        </div>
        <button onClick={addContact} className="px-4 py-2 bg-blue-600 text-white rounded">Add Contact</button>
        <button onClick={() => runCrmSync(BRAND).then(load)} className="px-4 py-2 bg-green-600 text-white rounded">Run CRM Sync</button>
      </div>

      {loading ? <p>Loading…</p> : (
        <>
          <section>
            <h2 className="text-lg font-semibold mb-2">Contacts ({contacts.length})</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm border">
                <thead className="bg-gray-100"><tr>
                  <th className="p-2 text-left">Email</th><th className="p-2 text-left">Name</th>
                  <th className="p-2 text-left">Lifecycle</th><th className="p-2 text-left">Segment</th>
                  <th className="p-2 text-left">Sync Status</th><th className="p-2 text-left">Source</th>
                </tr></thead>
                <tbody>
                  {contacts.map((c: any) => (
                    <tr key={c.id} className="border-t">
                      <td className="p-2">{c.email ?? "—"}</td><td className="p-2">{c.name ?? "—"}</td>
                      <td className="p-2">{c.lifecycle_stage}</td><td className="p-2">{c.segment ?? "—"}</td>
                      <td className="p-2">{c.sync_status}</td><td className="p-2">{c.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-2">Sync History ({syncs.length})</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm border">
                <thead className="bg-gray-100"><tr>
                  <th className="p-2 text-left">Provider</th><th className="p-2 text-left">Direction</th>
                  <th className="p-2 text-left">Synced</th><th className="p-2 text-left">Failed</th>
                  <th className="p-2 text-left">Status</th>
                </tr></thead>
                <tbody>
                  {syncs.map((s: any) => (
                    <tr key={s.id} className="border-t">
                      <td className="p-2">{s.provider}</td><td className="p-2">{s.direction}</td>
                      <td className="p-2">{s.contacts_synced}</td><td className="p-2">{s.contacts_failed}</td>
                      <td className="p-2">{s.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
