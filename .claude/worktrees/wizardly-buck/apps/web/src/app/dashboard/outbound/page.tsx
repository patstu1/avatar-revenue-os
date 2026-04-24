"use client";
import { useState } from "react";

interface OutboundTarget {
  id: string;
  company: string;
  category: string;
  contact: string;
  proofAsset: string;
  packageToPitch: string;
  status: "new" | "contacted" | "replied" | "meeting" | "closed" | "lost";
  notes: string;
}

const STATUS_COLORS: Record<string, string> = {
  new: "bg-gray-700 text-gray-300",
  contacted: "bg-blue-900 text-blue-300",
  replied: "bg-yellow-900 text-yellow-300",
  meeting: "bg-purple-900 text-purple-300",
  closed: "bg-emerald-900 text-emerald-300",
  lost: "bg-red-900 text-red-300",
};

const PROOF_ASSETS = [
  "CeraVe Product Showcase",
  "5 Skincare Mistakes",
  "30-Day Transformation",
  "AI Tool Demo",
  "AI UGC Sample",
];

const PACKAGES = [
  "AI UGC Starter ($1,500/mo)",
  "Beauty Content Pack ($2,500/mo)",
  "Fitness Content Pack ($2,500/mo)",
  "AI Tool Review Pack ($2,000/mo)",
  "Full Creative Retainer ($7,500/mo)",
];

const CATEGORIES = ["Beauty/Skincare", "Fitness/Wellness", "AI/SaaS", "E-commerce", "Health", "Finance", "Other"];

const INITIAL_TARGETS: OutboundTarget[] = [
  { id: "1", company: "", category: "Beauty/Skincare", contact: "", proofAsset: PROOF_ASSETS[0], packageToPitch: PACKAGES[1], status: "new", notes: "" },
];

export default function OutboundPage() {
  const [targets, setTargets] = useState<OutboundTarget[]>(INITIAL_TARGETS);

  const addRow = () => {
    setTargets(prev => [...prev, {
      id: String(Date.now()),
      company: "",
      category: "Beauty/Skincare",
      contact: "",
      proofAsset: PROOF_ASSETS[0],
      packageToPitch: PACKAGES[0],
      status: "new",
      notes: "",
    }]);
  };

  const update = (id: string, field: keyof OutboundTarget, value: string) => {
    setTargets(prev => prev.map(t => t.id === id ? { ...t, [field]: value } : t));
  };

  const remove = (id: string) => {
    setTargets(prev => prev.filter(t => t.id !== id));
  };

  const stats = {
    total: targets.length,
    contacted: targets.filter(t => t.status !== "new").length,
    meetings: targets.filter(t => t.status === "meeting").length,
    closed: targets.filter(t => t.status === "closed").length,
    pipeline: targets.filter(t => ["contacted", "replied", "meeting"].includes(t.status)).reduce((s, t) => {
      const match = t.packageToPitch.match(/\$([\d,]+)/);
      return s + (match ? parseInt(match[1].replace(",", "")) : 0);
    }, 0),
  };

  return (
    <div className="p-6 max-w-[1400px] mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Outbound Pipeline</h1>
          <p className="text-gray-400 text-sm">Track prospects, attach proof, pitch packages</p>
        </div>
        <div className="flex gap-3">
          <a href="/proof" target="_blank" className="px-4 py-2 bg-gray-800 text-gray-300 rounded-lg text-sm hover:bg-gray-700 transition">
            View Proof Gallery
          </a>
          <a href="/offers" target="_blank" className="px-4 py-2 bg-gray-800 text-gray-300 rounded-lg text-sm hover:bg-gray-700 transition">
            View Offer Sheet
          </a>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-5 gap-4 mb-6">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="text-2xl font-bold text-white">{stats.total}</div>
          <div className="text-xs text-gray-500">Total Targets</div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="text-2xl font-bold text-blue-400">{stats.contacted}</div>
          <div className="text-xs text-gray-500">Contacted</div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="text-2xl font-bold text-purple-400">{stats.meetings}</div>
          <div className="text-xs text-gray-500">Meetings</div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="text-2xl font-bold text-emerald-400">{stats.closed}</div>
          <div className="text-xs text-gray-500">Closed</div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="text-2xl font-bold text-amber-400">${stats.pipeline.toLocaleString()}</div>
          <div className="text-xs text-gray-500">Pipeline Value/mo</div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-400 text-xs uppercase">
                <th className="px-4 py-3 text-left">Company</th>
                <th className="px-4 py-3 text-left">Category</th>
                <th className="px-4 py-3 text-left">Contact</th>
                <th className="px-4 py-3 text-left">Proof to Send</th>
                <th className="px-4 py-3 text-left">Package</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Notes</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {targets.map(t => (
                <tr key={t.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="px-4 py-2">
                    <input value={t.company} onChange={e => update(t.id, "company", e.target.value)} placeholder="Brand name..." className="bg-transparent border-none text-white text-sm w-full focus:outline-none focus:ring-1 focus:ring-blue-500 rounded px-1" />
                  </td>
                  <td className="px-4 py-2">
                    <select value={t.category} onChange={e => update(t.id, "category", e.target.value)} className="bg-gray-800 border-none text-gray-300 text-xs rounded px-2 py-1">
                      {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </td>
                  <td className="px-4 py-2">
                    <input value={t.contact} onChange={e => update(t.id, "contact", e.target.value)} placeholder="Email/IG..." className="bg-transparent border-none text-white text-sm w-full focus:outline-none focus:ring-1 focus:ring-blue-500 rounded px-1" />
                  </td>
                  <td className="px-4 py-2">
                    <select value={t.proofAsset} onChange={e => update(t.id, "proofAsset", e.target.value)} className="bg-gray-800 border-none text-gray-300 text-xs rounded px-2 py-1">
                      {PROOF_ASSETS.map(p => <option key={p} value={p}>{p}</option>)}
                    </select>
                  </td>
                  <td className="px-4 py-2">
                    <select value={t.packageToPitch} onChange={e => update(t.id, "packageToPitch", e.target.value)} className="bg-gray-800 border-none text-gray-300 text-xs rounded px-2 py-1">
                      {PACKAGES.map(p => <option key={p} value={p}>{p}</option>)}
                    </select>
                  </td>
                  <td className="px-4 py-2">
                    <select value={t.status} onChange={e => update(t.id, "status", e.target.value as OutboundTarget["status"])} className={`border-none text-xs rounded px-2 py-1 font-medium ${STATUS_COLORS[t.status]}`}>
                      {Object.keys(STATUS_COLORS).map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </td>
                  <td className="px-4 py-2">
                    <input value={t.notes} onChange={e => update(t.id, "notes", e.target.value)} placeholder="Notes..." className="bg-transparent border-none text-gray-400 text-xs w-full focus:outline-none focus:ring-1 focus:ring-blue-500 rounded px-1" />
                  </td>
                  <td className="px-4 py-2">
                    <button onClick={() => remove(t.id)} className="text-gray-600 hover:text-red-400 text-xs">&times;</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="px-4 py-3 border-t border-gray-800">
          <button onClick={addRow} className="text-sm text-blue-400 hover:text-blue-300 font-medium">+ Add Target</button>
        </div>
      </div>
    </div>
  );
}
