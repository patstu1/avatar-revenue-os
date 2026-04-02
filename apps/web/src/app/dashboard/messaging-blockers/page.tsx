"use client";
import { useEffect, useState } from "react";
import { fetchMessagingBlockers, recomputeMessagingBlockers } from "@/lib/live-execution-api";

const BRAND = "00000000-0000-0000-0000-000000000001";

export default function MessagingBlockersPage() {
  const [blockers, setBlockers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setBlockers(await fetchMessagingBlockers(BRAND));
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Messaging Blockers</h1>

      <button onClick={() => recomputeMessagingBlockers(BRAND).then(load)} className="px-4 py-2 bg-red-600 text-white rounded">
        Recompute Blockers
      </button>

      {loading ? <p>Loading…</p> : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm border">
            <thead className="bg-gray-100"><tr>
              <th className="p-2 text-left">Type</th><th className="p-2 text-left">Channel</th>
              <th className="p-2 text-left">Severity</th><th className="p-2 text-left">Description</th>
              <th className="p-2 text-left">Operator Action</th><th className="p-2 text-left">Resolved</th>
            </tr></thead>
            <tbody>
              {blockers.length === 0 && <tr><td colSpan={6} className="p-4 text-center text-gray-500">No blockers detected</td></tr>}
              {blockers.map((b: any) => (
                <tr key={b.id} className="border-t">
                  <td className="p-2 font-mono text-xs">{b.blocker_type}</td>
                  <td className="p-2">{b.channel}</td>
                  <td className="p-2">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${b.severity === "critical" ? "bg-red-100 text-red-800" : b.severity === "high" ? "bg-orange-100 text-orange-800" : "bg-yellow-100 text-yellow-800"}`}>
                      {b.severity}
                    </span>
                  </td>
                  <td className="p-2">{b.description}</td>
                  <td className="p-2 text-blue-700">{b.operator_action_needed}</td>
                  <td className="p-2">{b.resolved ? "Yes" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
