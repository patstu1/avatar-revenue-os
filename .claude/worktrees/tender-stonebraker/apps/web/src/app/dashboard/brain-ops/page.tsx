"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import {
  Activity,
  Brain,
  CheckCircle2,
  Circle,
  AlertTriangle,
  XCircle,
  RefreshCw,
  ExternalLink,
  Zap,
} from "lucide-react";

interface Subsystem {
  name: string;
  table: string;
  total: number;
  recent_6h: number;
  latest_at: string | null;
  status: "LIVE" | "IDLE" | "EMPTY" | "MISSING";
  error?: string;
}

interface PublishEntry {
  platform: string;
  url: string;
  published_at: string | null;
}

interface BrainOpsStatus {
  generated_at: string;
  summary: {
    total_subsystems: number;
    live: number;
    idle: number;
    empty: number;
    missing: number;
  };
  scheduler: {
    distinct_jobs_last_1h: number;
    distinct_jobs_last_6h: number;
    completed_last_1h: number;
    failed_or_retrying_last_6h: number;
  };
  destination_publishing: {
    real_posts_published: number;
    latest: PublishEntry[];
  };
  subsystems: Subsystem[];
}

interface JobRow {
  name: string;
  status: string;
  queue: string;
  created_at: string | null;
  duration_seconds: number | null;
}

function StatusIcon({ status }: { status: Subsystem["status"] }) {
  if (status === "LIVE")
    return <CheckCircle2 size={14} className="text-emerald-400" />;
  if (status === "IDLE") return <Circle size={14} className="text-yellow-400" />;
  if (status === "EMPTY") return <Circle size={14} className="text-gray-600" />;
  return <XCircle size={14} className="text-red-500" />;
}

function StatusBadge({ status }: { status: Subsystem["status"] }) {
  const map: Record<Subsystem["status"], string> = {
    LIVE: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    IDLE: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
    EMPTY: "bg-gray-700/30 text-gray-500 border-gray-700",
    MISSING: "bg-red-500/10 text-red-400 border-red-500/30",
  };
  return (
    <span
      className={`px-2 py-0.5 text-[10px] font-semibold rounded border ${map[status]}`}
    >
      {status}
    </span>
  );
}

function formatAge(iso: string | null): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return `${Math.floor(hr / 24)}d ago`;
}

export default function BrainOpsPage() {
  const [status, setStatus] = useState<BrainOpsStatus | null>(null);
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  async function load() {
    try {
      setError(null);
      const [statusRes, jobsRes] = await Promise.all([
        api.get<BrainOpsStatus>("/api/v1/brain-ops/status"),
        api.get<{ jobs: JobRow[] }>("/api/v1/brain-ops/recent-jobs?limit=30"),
      ]);
      setStatus(statusRes.data);
      setJobs(jobsRes.data.jobs || []);
      setLastRefresh(new Date());
    } catch (e: any) {
      setError(e?.message || "Failed to load brain ops status");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 30_000); // refresh every 30s
    return () => clearInterval(interval);
  }, []);

  if (loading && !status) {
    return (
      <div className="p-8">
        <div className="text-gray-400">Loading brain operations state…</div>
      </div>
    );
  }

  if (error && !status) {
    return (
      <div className="p-8">
        <div className="text-red-400">Error: {error}</div>
      </div>
    );
  }

  if (!status) return null;

  const sum = status.summary;
  const pct = sum.total_subsystems
    ? Math.round((sum.live / sum.total_subsystems) * 100)
    : 0;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Brain className="text-brand-400" size={28} />
            Brain Operations
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Real runtime state of every autonomous subsystem. Auto-refresh every
            30s.
          </p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-sm text-gray-200 rounded-lg border border-gray-700"
        >
          <RefreshCw size={14} />
          Refresh
        </button>
      </div>

      {/* Top-line summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="text-xs text-gray-500 uppercase tracking-wide">
            Subsystems Live
          </div>
          <div className="text-3xl font-bold text-emerald-400 mt-1">
            {sum.live}{" "}
            <span className="text-lg text-gray-500">
              / {sum.total_subsystems}
            </span>
          </div>
          <div className="text-xs text-gray-500 mt-1">{pct}% producing</div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="text-xs text-gray-500 uppercase tracking-wide">
            Jobs Completed (1h)
          </div>
          <div className="text-3xl font-bold text-white mt-1">
            {status.scheduler.completed_last_1h.toLocaleString()}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {status.scheduler.distinct_jobs_last_1h} distinct job types
          </div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="text-xs text-gray-500 uppercase tracking-wide">
            Real Posts Published
          </div>
          <div className="text-3xl font-bold text-emerald-400 mt-1">
            {status.destination_publishing.real_posts_published}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            with verified platform URLs
          </div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="text-xs text-gray-500 uppercase tracking-wide">
            Failed / Retrying (6h)
          </div>
          <div
            className={`text-3xl font-bold mt-1 ${
              status.scheduler.failed_or_retrying_last_6h > 0
                ? "text-yellow-400"
                : "text-gray-500"
            }`}
          >
            {status.scheduler.failed_or_retrying_last_6h}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            tasks needing attention
          </div>
        </div>
      </div>

      {/* Destination Publishing Proof */}
      {status.destination_publishing.latest.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <Zap size={16} className="text-brand-400" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wide">
              Latest Real Destination Publishes
            </h2>
          </div>
          <div className="space-y-2">
            {status.destination_publishing.latest.map((p, i) => (
              <a
                key={i}
                href={p.url}
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-between p-2 hover:bg-gray-800 rounded group"
              >
                <div className="flex items-center gap-3">
                  <span className="px-2 py-0.5 text-[10px] font-semibold bg-brand-500/10 text-brand-400 rounded border border-brand-500/30">
                    {p.platform}
                  </span>
                  <span className="text-sm text-gray-300 font-mono truncate max-w-xl">
                    {p.url}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">
                    {formatAge(p.published_at)}
                  </span>
                  <ExternalLink
                    size={14}
                    className="text-gray-500 group-hover:text-brand-400"
                  />
                </div>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Subsystems grid */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Activity size={16} className="text-brand-400" />
          <h2 className="text-sm font-bold text-white uppercase tracking-wide">
            Subsystem Activity (last 6h)
          </h2>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-800/50 text-xs text-gray-400 uppercase">
                <th className="text-left px-4 py-2 font-semibold">Subsystem</th>
                <th className="text-right px-4 py-2 font-semibold">Total</th>
                <th className="text-right px-4 py-2 font-semibold">
                  Last 6h
                </th>
                <th className="text-left px-4 py-2 font-semibold">Latest</th>
                <th className="text-left px-4 py-2 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody>
              {status.subsystems.map((s) => (
                <tr
                  key={s.table}
                  className="border-t border-gray-800 hover:bg-gray-800/30"
                >
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-2">
                      <StatusIcon status={s.status} />
                      <span className="text-gray-200">{s.name}</span>
                    </div>
                    <div className="text-[10px] text-gray-600 font-mono ml-6">
                      {s.table}
                    </div>
                  </td>
                  <td className="px-4 py-2 text-right text-gray-300 font-mono">
                    {s.total.toLocaleString()}
                  </td>
                  <td
                    className={`px-4 py-2 text-right font-mono ${
                      s.recent_6h > 0 ? "text-emerald-400" : "text-gray-600"
                    }`}
                  >
                    {s.recent_6h}
                  </td>
                  <td className="px-4 py-2 text-gray-500 text-xs">
                    {formatAge(s.latest_at)}
                  </td>
                  <td className="px-4 py-2">
                    <StatusBadge status={s.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recent jobs stream */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Activity size={16} className="text-brand-400" />
          <h2 className="text-sm font-bold text-white uppercase tracking-wide">
            Recent Jobs (last hour)
          </h2>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-gray-800/50 text-[10px] text-gray-400 uppercase">
                <th className="text-left px-4 py-2 font-semibold">Job</th>
                <th className="text-left px-4 py-2 font-semibold">Status</th>
                <th className="text-right px-4 py-2 font-semibold">
                  Duration
                </th>
                <th className="text-left px-4 py-2 font-semibold">When</th>
              </tr>
            </thead>
            <tbody>
              {jobs.slice(0, 30).map((j, i) => (
                <tr
                  key={i}
                  className="border-t border-gray-800 hover:bg-gray-800/30"
                >
                  <td className="px-4 py-1.5 text-gray-300 font-mono text-xs">
                    {j.name.replace(/^workers\./, "")}
                  </td>
                  <td className="px-4 py-1.5">
                    <span
                      className={`px-1.5 py-0.5 text-[9px] font-semibold rounded ${
                        j.status === "COMPLETED"
                          ? "bg-emerald-500/10 text-emerald-400"
                          : j.status === "FAILED"
                            ? "bg-red-500/10 text-red-400"
                            : "bg-yellow-500/10 text-yellow-400"
                      }`}
                    >
                      {j.status}
                    </span>
                  </td>
                  <td className="px-4 py-1.5 text-right text-gray-500 font-mono">
                    {j.duration_seconds !== null
                      ? `${j.duration_seconds.toFixed(2)}s`
                      : "—"}
                  </td>
                  <td className="px-4 py-1.5 text-gray-500">
                    {formatAge(j.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="text-xs text-gray-600 text-right">
        Last refreshed: {lastRefresh.toLocaleTimeString()}
      </div>
    </div>
  );
}
