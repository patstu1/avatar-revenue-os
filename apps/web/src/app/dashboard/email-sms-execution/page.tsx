"use client";
import { useEffect, useState } from "react";
import {
  fetchEmailRequests,
  createEmailSend,
  fetchSmsRequests,
  createSmsSend,
} from "@/lib/live-execution-api";
import { brandsApi } from "@/lib/api";

export default function EmailSmsExecutionPage() {
  const [emails, setEmails] = useState<any[]>([]);
  const [smsList, setSmsList] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [toEmail, setToEmail] = useState("");
  const [subject, setSubject] = useState("");
  const [toPhone, setToPhone] = useState("");
  const [smsBody, setSmsBody] = useState("");
  const [brandId, setBrandId] = useState("");
  const [brands, setBrands] = useState<{id: string; name: string}[]>([]);

  async function load() {
    setLoading(true);
    const [e, s] = await Promise.all([fetchEmailRequests(brandId), fetchSmsRequests(brandId)]);
    setEmails(e); setSmsList(s);
    setLoading(false);
  }

  async function sendEmail() {
    if (!toEmail || !subject) return;
    await createEmailSend(brandId, { to_email: toEmail, subject, body_text: "Test email" });
    setToEmail(""); setSubject("");
    load();
  }

  async function sendSms() {
    if (!toPhone || !smsBody) return;
    await createSmsSend(brandId, { to_phone: toPhone, message_body: smsBody });
    setToPhone(""); setSmsBody("");
    load();
  }

  useEffect(() => {
    brandsApi.list().then((r) => {
      const list = r.data ?? r;
      setBrands(Array.isArray(list) ? list : []);
      if (Array.isArray(list) && list.length > 0) setBrandId(list[0].id);
    }).catch(() => {});
  }, []);

  useEffect(() => { if (brandId) load(); }, [brandId]);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Email & SMS Execution</h1>
      <div className="flex items-center gap-3 mb-4">
        <label className="text-sm text-gray-400">Brand:</label>
        <select aria-label="Select brand" className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white" value={brandId} onChange={e => setBrandId(e.target.value)}>
          {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="space-y-2">
          <h3 className="font-semibold">Queue Email</h3>
          <input value={toEmail} onChange={e => setToEmail(e.target.value)} placeholder="to@email.com" className="border rounded p-2 w-full" />
          <input value={subject} onChange={e => setSubject(e.target.value)} placeholder="Subject" className="border rounded p-2 w-full" />
          <button onClick={sendEmail} className="px-4 py-2 bg-blue-600 text-white rounded">Queue Email</button>
        </div>
        <div className="space-y-2">
          <h3 className="font-semibold">Queue SMS</h3>
          <input value={toPhone} onChange={e => setToPhone(e.target.value)} placeholder="+1234567890" className="border rounded p-2 w-full" />
          <input value={smsBody} onChange={e => setSmsBody(e.target.value)} placeholder="Message body" className="border rounded p-2 w-full" />
          <button onClick={sendSms} className="px-4 py-2 bg-green-600 text-white rounded">Queue SMS</button>
        </div>
      </div>

      {loading ? <p>Loading…</p> : (
        <>
          <section>
            <h2 className="text-lg font-semibold mb-2">Email Requests ({emails.length})</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm border">
                <thead className="bg-gray-100"><tr>
                  <th className="p-2 text-left">To</th><th className="p-2 text-left">Subject</th>
                  <th className="p-2 text-left">Provider</th><th className="p-2 text-left">Status</th>
                  <th className="p-2 text-left">Retries</th><th className="p-2 text-left">Error</th>
                </tr></thead>
                <tbody>
                  {emails.map((e: any) => (
                    <tr key={e.id} className="border-t">
                      <td className="p-2">{e.to_email}</td><td className="p-2">{e.subject}</td>
                      <td className="p-2">{e.provider}</td><td className="p-2">{e.status}</td>
                      <td className="p-2">{e.retry_count}</td><td className="p-2 text-red-600">{e.error_message ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-2">SMS Requests ({smsList.length})</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm border">
                <thead className="bg-gray-100"><tr>
                  <th className="p-2 text-left">To</th><th className="p-2 text-left">Body</th>
                  <th className="p-2 text-left">Provider</th><th className="p-2 text-left">Status</th>
                  <th className="p-2 text-left">Retries</th><th className="p-2 text-left">Error</th>
                </tr></thead>
                <tbody>
                  {smsList.map((s: any) => (
                    <tr key={s.id} className="border-t">
                      <td className="p-2">{s.to_phone}</td><td className="p-2 truncate max-w-xs">{s.message_body}</td>
                      <td className="p-2">{s.provider}</td><td className="p-2">{s.status}</td>
                      <td className="p-2">{s.retry_count}</td><td className="p-2 text-red-600">{s.error_message ?? "—"}</td>
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
