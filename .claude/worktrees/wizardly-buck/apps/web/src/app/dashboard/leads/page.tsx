"use client";
import { useEffect, useRef, useState } from "react";
import { API_BASE, apiFetch } from "@/lib/api";

interface Lead {
  id: string;
  company_name: string;
  contact_name: string | null;
  email: string | null;
  phone: string | null;
  instagram_handle: string | null;
  website_url: string | null;
  industry: string;
  niche_tag: string;
  estimated_size: string | null;
  fit_score: number;
  outreach_status: string;
  created_at: string;
}

interface LeadStats {
  total: number;
  by_niche: Record<string, number>;
  with_email: number;
  with_phone: number;
}

interface ImportResult {
  imported: number;
  skipped: number;
  errors: string[];
  total_leads: number;
}

const STATUS_COLORS: Record<string, string> = {
  new: "bg-gray-700 text-gray-300",
  contacted: "bg-blue-900 text-blue-300",
  replied: "bg-emerald-900 text-emerald-300",
};

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [stats, setStats] = useState<LeadStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [filter, setFilter] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    try {
      const [l, s] = await Promise.all([
        apiFetch<Lead[]>(`/api/v1/leads${filter ? `?niche=${filter}` : ""}`),
        apiFetch<LeadStats>("/api/v1/leads/stats"),
      ]);
      setLeads(l);
      setStats(s);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [filter]);

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setImporting(true);
    setImportResult(null);
    try {
      const token = localStorage.getItem("aro_token");
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_BASE}/api/v1/leads/import-csv`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });
      const data = await res.json();
      setImportResult(data);
      load();
    } catch { /* empty */ }
    setImporting(false);
    if (fileRef.current) fileRef.current.value = "";
  };

  return (
    <div className="p-6 max-w-[1400px] mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Lead Database</h1>
          <p className="text-gray-400 text-sm">B2B prospects for UGC / content packages</p>
        </div>
        <div className="flex gap-3">
          <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={handleUpload} />
          <button onClick={() => fileRef.current?.click()} disabled={importing}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-500 transition disabled:opacity-50">
            {importing ? "Importing..." : "Import CSV"}
          </button>
          <a href="/dashboard/outbound" className="px-4 py-2 bg-gray-800 text-gray-300 rounded-lg text-sm hover:bg-gray-700 transition">
            Outbound Pipeline
          </a>
        </div>
      </div>

      {/* Import result */}
      {importResult && (
        <div className={`mb-4 p-4 rounded-lg border text-sm ${importResult.imported > 0 ? "bg-emerald-900/30 border-emerald-800 text-emerald-300" : "bg-yellow-900/30 border-yellow-800 text-yellow-300"}`}>
          Imported {importResult.imported} leads, skipped {importResult.skipped}. Total in database: {importResult.total_leads}
          {importResult.errors.length > 0 && <div className="mt-2 text-xs text-red-400">{importResult.errors.join(", ")}</div>}
        </div>
      )}

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-5 gap-4 mb-6">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="text-2xl font-bold text-white">{stats.total}</div>
            <div className="text-xs text-gray-500">Total Leads</div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="text-2xl font-bold text-blue-400">{stats.with_email}</div>
            <div className="text-xs text-gray-500">With Email</div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="text-2xl font-bold text-purple-400">{stats.with_phone}</div>
            <div className="text-xs text-gray-500">With Phone</div>
          </div>
          {Object.entries(stats.by_niche).slice(0, 2).map(([niche, count]) => (
            <div key={niche} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
              <div className="text-2xl font-bold text-amber-400">{count}</div>
              <div className="text-xs text-gray-500 capitalize">{niche}</div>
            </div>
          ))}
        </div>
      )}

      {/* CSV format help */}
      <div className="mb-4 p-3 bg-gray-900 border border-gray-800 rounded-lg text-xs text-gray-400">
        <strong className="text-gray-300">CSV format:</strong> company_name, contact_name, email, phone, instagram_handle, website_url, niche_tag, estimated_size, notes
        <span className="ml-2 text-gray-500">(only company_name is required)</span>
      </div>

      {/* Filter */}
      <div className="flex gap-2 mb-4">
        {["", "beauty", "fitness", "saas", "ecommerce"].map(n => (
          <button key={n} onClick={() => setFilter(n)}
            className={`px-3 py-1 rounded text-xs font-medium transition ${filter === n ? "bg-white text-gray-900" : "bg-gray-800 text-gray-400 hover:bg-gray-700"}`}>
            {n || "All"}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-400 text-xs uppercase">
                <th className="px-4 py-3 text-left">Company</th>
                <th className="px-4 py-3 text-left">Contact</th>
                <th className="px-4 py-3 text-left">Email</th>
                <th className="px-4 py-3 text-left">Phone</th>
                <th className="px-4 py-3 text-left">Niche</th>
                <th className="px-4 py-3 text-left">Size</th>
                <th className="px-4 py-3 text-left">Status</th>
              </tr>
            </thead>
            <tbody>
              {leads.map(l => (
                <tr key={l.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="px-4 py-3 text-white font-medium">{l.company_name}</td>
                  <td className="px-4 py-3 text-gray-300">{l.contact_name || "—"}</td>
                  <td className="px-4 py-3 text-gray-300 text-xs">{l.email || "—"}</td>
                  <td className="px-4 py-3 text-gray-300 text-xs">{l.phone || "—"}</td>
                  <td className="px-4 py-3"><span className="px-2 py-0.5 rounded text-xs bg-gray-800 text-gray-300 capitalize">{l.niche_tag}</span></td>
                  <td className="px-4 py-3 text-gray-400 text-xs">{l.estimated_size || "—"}</td>
                  <td className="px-4 py-3"><span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[l.outreach_status] || STATUS_COLORS.new}`}>{l.outreach_status}</span></td>
                </tr>
              ))}
              {leads.length === 0 && !loading && (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-500">No leads yet. Import a CSV or add manually.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
