"use client";

/**
 * Operator dashboard — AI Buyer Trust Test reports.
 *
 * Minimal patch-1 surface: list reports, click to expand a detail drawer,
 * mark qualified or archive. Reuses dashboard's tanstack-query pattern
 * and the same dark zinc palette as the rest of the operator UI.
 */

import { useEffect, useMemo, useState } from "react";

import {
  type AuthorityReportDetail,
  type AuthorityReportListItem,
  aiSearchAuthorityApi,
} from "@/lib/ai-search-authority-api";

const STATUS_OPTIONS = [
  { value: "", label: "All" },
  { value: "scored", label: "Scored" },
  { value: "qualified", label: "Qualified" },
  { value: "proposal_created", label: "Proposal created" },
  { value: "archived", label: "Archived" },
  { value: "failed", label: "Failed" },
];

const SCORE_BANDS: { label: string; min?: number; max?: number }[] = [
  { label: "All scores" },
  { label: "Not ready (0–39)", min: 0, max: 39 },
  { label: "Weak (40–59)", min: 40, max: 59 },
  { label: "Developing (60–74)", min: 60, max: 74 },
  { label: "Strong (75–89)", min: 75, max: 89 },
  { label: "Authority-ready (90+)", min: 90, max: 100 },
];

export default function AiSearchAuthorityDashboardPage() {
  const [items, setItems] = useState<AuthorityReportListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [bandIndex, setBandIndex] = useState(0);
  const [selected, setSelected] = useState<AuthorityReportDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const band = SCORE_BANDS[bandIndex];

  const params = useMemo(
    () => ({
      limit: 100,
      status: statusFilter || undefined,
      score_min: band?.min,
      score_max: band?.max,
      search: search.trim() || undefined,
    }),
    [statusFilter, band, search],
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    aiSearchAuthorityApi
      .list(params)
      .then((resp) => {
        if (!cancelled) setItems(resp.items);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Error");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [params]);

  const openDetail = async (id: string) => {
    setDetailLoading(true);
    try {
      const d = await aiSearchAuthorityApi.detail(id);
      setSelected(d);
    } finally {
      setDetailLoading(false);
    }
  };

  const refresh = async () => {
    const resp = await aiSearchAuthorityApi.list(params);
    setItems(resp.items);
    if (selected) {
      const d = await aiSearchAuthorityApi.detail(selected.id);
      setSelected(d);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header>
          <p className="font-mono text-xs uppercase tracking-wider text-zinc-500">
            AI Buyer Trust Infrastructure
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">
            AI Search Authority — reports
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-zinc-400 leading-relaxed">
            Every public AI Buyer Trust Test submission. Click a row to view
            the full Authority Snapshot — per-dimension evidence, buyer
            questions, recommended pages, schema, and proof assets.
          </p>
        </header>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <input
            type="search"
            placeholder="Search company, domain, email…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-72 rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 focus:border-zinc-500 focus:outline-none"
          />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 focus:border-zinc-500 focus:outline-none"
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <select
            value={bandIndex}
            onChange={(e) => setBandIndex(Number(e.target.value))}
            className="rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 focus:border-zinc-500 focus:outline-none"
          >
            {SCORE_BANDS.map((b, i) => (
              <option key={b.label} value={i}>
                {b.label}
              </option>
            ))}
          </select>
        </div>

        {error ? (
          <p className="mt-6 text-sm text-zinc-300">{error}</p>
        ) : null}

        <div className="mt-6 overflow-hidden rounded-md border border-zinc-800">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-zinc-800 bg-zinc-900/40 text-zinc-400">
              <tr>
                <th className="px-4 py-2 font-medium">Company</th>
                <th className="px-4 py-2 font-medium">Domain</th>
                <th className="px-4 py-2 font-medium">Email</th>
                <th className="px-4 py-2 font-medium">Score</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Recommended</th>
                <th className="px-4 py-2 font-medium">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {loading && items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-6 text-center text-zinc-500">
                    Loading…
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-6 text-center text-zinc-500">
                    No reports yet.
                  </td>
                </tr>
              ) : (
                items.map((item) => (
                  <tr
                    key={item.id}
                    onClick={() => openDetail(item.id)}
                    className="cursor-pointer hover:bg-zinc-900/40"
                  >
                    <td className="px-4 py-2 text-zinc-100">{item.company_name}</td>
                    <td className="px-4 py-2 text-zinc-400">{item.website_domain}</td>
                    <td className="px-4 py-2 text-zinc-400">{item.contact_email}</td>
                    <td className="px-4 py-2 font-mono text-zinc-200">
                      {item.total_score}
                      <span className="ml-2 text-xs text-zinc-500">
                        {item.score_label}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-zinc-400">{item.report_status}</td>
                    <td className="px-4 py-2 text-zinc-300">
                      {item.recommended_package_slug ?? "—"}
                    </td>
                    <td className="px-4 py-2 text-zinc-500">
                      {item.created_at?.slice(0, 10) ?? "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {selected ? (
          <DetailPanel
            report={selected}
            loading={detailLoading}
            onClose={() => setSelected(null)}
            onRefresh={refresh}
          />
        ) : null}
      </div>
    </div>
  );
}

function DetailPanel({
  report,
  loading,
  onClose,
  onRefresh,
}: {
  report: AuthorityReportDetail;
  loading: boolean;
  onClose: () => void;
  onRefresh: () => Promise<void>;
}) {
  const [actioning, setActioning] = useState<string | null>(null);

  const markQualified = async () => {
    setActioning("qualify");
    try {
      await aiSearchAuthorityApi.markQualified(report.id);
      await onRefresh();
    } finally {
      setActioning(null);
    }
  };

  const archive = async () => {
    setActioning("archive");
    try {
      await aiSearchAuthorityApi.archive(report.id);
      await onRefresh();
    } finally {
      setActioning(null);
    }
  };

  return (
    <aside
      role="dialog"
      aria-label="Authority report detail"
      className="fixed inset-y-0 right-0 z-30 w-full max-w-2xl overflow-y-auto border-l border-zinc-800 bg-zinc-950 p-6 shadow-2xl sm:p-8"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-wider text-zinc-500">
            Authority report · {report.report_status}
          </p>
          <h2 className="mt-2 text-xl font-semibold tracking-tight text-zinc-100">
            {report.company_name}
          </h2>
          <p className="mt-1 text-sm text-zinc-400">
            {report.website_url} · {report.contact_email}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-sm text-zinc-400 hover:text-zinc-200"
        >
          Close
        </button>
      </div>

      <div className="mt-6 flex items-baseline gap-4">
        <span className="text-4xl font-semibold text-zinc-100">
          {report.total_score}
        </span>
        <span className="text-sm text-zinc-500">
          / 100 · {report.score_label} · {report.confidence_label}
        </span>
      </div>

      <RecommendedLanesBlock report={report} />

      <div className="mt-6 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={markQualified}
          disabled={!!actioning || report.report_status === "qualified"}
          className="rounded-md border border-zinc-100 bg-zinc-100 px-3 py-1.5 text-sm font-medium text-zinc-950 hover:bg-zinc-200 disabled:cursor-not-allowed disabled:border-zinc-700 disabled:bg-zinc-800 disabled:text-zinc-500"
        >
          {actioning === "qualify" ? "Marking…" : "Mark qualified"}
        </button>
        <button
          type="button"
          onClick={archive}
          disabled={!!actioning || report.report_status === "archived"}
          className="rounded-md border border-zinc-700 px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-900 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {actioning === "archive" ? "Archiving…" : "Archive"}
        </button>
        {report.lead_opportunity_id ? (
          <a
            href={`/dashboard/expansion-pack2-a/leads`}
            className="rounded-md border border-zinc-700 px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-900"
          >
            View lead →
          </a>
        ) : null}
      </div>

      <Section title="Top gaps">
        {report.top_gaps && report.top_gaps.length ? (
          <ul className="space-y-3">
            {report.top_gaps.map((g, i) => (
              <li key={i} className="rounded-md border border-zinc-800 bg-zinc-900/40 p-3 text-sm">
                <pre className="whitespace-pre-wrap text-zinc-300">
                  {JSON.stringify(g, null, 2)}
                </pre>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-zinc-500">None.</p>
        )}
      </Section>

      <Section title="Buyer questions (full list)">
        {report.buyer_questions && report.buyer_questions.length ? (
          <ul className="space-y-2">
            {report.buyer_questions.map((q) => (
              <li key={q.question} className="rounded-md border border-zinc-800 bg-zinc-900/40 p-3">
                <p className="font-medium text-zinc-100 text-sm">{q.question}</p>
                <p className="mt-1 text-xs text-zinc-400">{q.rationale}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-zinc-500">None.</p>
        )}
      </Section>

      <Section title="Recommended pages">
        <pre className="whitespace-pre-wrap rounded-md border border-zinc-800 bg-zinc-900/40 p-3 text-xs text-zinc-300">
          {JSON.stringify(report.recommended_pages, null, 2)}
        </pre>
      </Section>

      <Section title="Recommended schema">
        <pre className="whitespace-pre-wrap rounded-md border border-zinc-800 bg-zinc-900/40 p-3 text-xs text-zinc-300">
          {JSON.stringify(report.recommended_schema, null, 2)}
        </pre>
      </Section>

      <Section title="Recommended proof assets">
        <pre className="whitespace-pre-wrap rounded-md border border-zinc-800 bg-zinc-900/40 p-3 text-xs text-zinc-300">
          {JSON.stringify(report.recommended_proof_assets, null, 2)}
        </pre>
      </Section>

      <Section title="Recommended comparison surfaces">
        <pre className="whitespace-pre-wrap rounded-md border border-zinc-800 bg-zinc-900/40 p-3 text-xs text-zinc-300">
          {JSON.stringify(report.recommended_comparison_surfaces, null, 2)}
        </pre>
      </Section>

      <Section title="Authority Graph">
        <pre className="whitespace-pre-wrap rounded-md border border-zinc-800 bg-zinc-900/40 p-3 text-xs text-zinc-300">
          {JSON.stringify(report.authority_graph, null, 2)}
        </pre>
      </Section>

      <Section title="Monitoring recommendation">
        <p className="text-sm text-zinc-300 leading-relaxed">
          {report.monitoring_recommendation || "—"}
        </p>
      </Section>

      <Section title="Scanned pages">
        <pre className="whitespace-pre-wrap rounded-md border border-zinc-800 bg-zinc-900/40 p-3 text-xs text-zinc-300">
          {JSON.stringify(report.scanned_pages, null, 2)}
        </pre>
      </Section>

      <p className="mt-6 text-xs text-zinc-500">
        formula {report.formula_version} · report {report.report_version} ·
        scan {report.scan_version}
      </p>
      {loading ? (
        <p className="mt-2 text-xs text-zinc-500">Refreshing…</p>
      ) : null}
    </aside>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-6">
      <p className="font-mono text-[11px] uppercase tracking-wider text-zinc-500">
        {title}
      </p>
      <div className="mt-2">{children}</div>
    </section>
  );
}

function RecommendedLanesBlock({ report }: { report: AuthorityReportDetail }) {
  const primary = report.recommended_package_slug;
  const publicResult =
    (report.public_result as
      | { recommended_package?: { secondary_slug?: string | null; creative_proof_slug?: string | null } }
      | undefined) ?? undefined;
  const secondary = publicResult?.recommended_package?.secondary_slug ?? null;
  const creative = publicResult?.recommended_package?.creative_proof_slug ?? null;

  return (
    <div
      data-testid="recommended-lanes"
      className="mt-6 rounded-md border border-zinc-800 bg-zinc-900/40 p-4"
    >
      <p className="font-mono text-[11px] uppercase tracking-wider text-zinc-500">
        Recommended packages
      </p>
      <div className="mt-3 grid gap-4 sm:grid-cols-2">
        <div data-testid="lane-ai-authority">
          <p className="font-mono text-[11px] uppercase tracking-wider text-zinc-500">
            AI Authority lane
          </p>
          <p className="mt-1 text-sm text-zinc-100">{primary ?? "—"}</p>
          {secondary ? (
            <p className="mt-1 text-xs text-zinc-400">+ {secondary}</p>
          ) : null}
        </div>
        <div data-testid="lane-creative-proof">
          <p className="font-mono text-[11px] uppercase tracking-wider text-zinc-500">
            Creative Proof companion
          </p>
          <p className="mt-1 text-sm text-zinc-100">{creative ?? "—"}</p>
        </div>
      </div>
    </div>
  );
}
