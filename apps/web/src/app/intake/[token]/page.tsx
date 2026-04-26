"use client";

/**
 * ProofHook public intake form.
 *
 * Driven by the email link in the buyer's intake invite (sent the moment
 * Stripe webhook activates a Client). The token in the URL is the token
 * column on intake_requests.token — opaque, single-purpose. Fetches the
 * schema from the API, renders fields, posts responses back. After a
 * successful submission the existing fulfillment cascade runs server-side
 * (ClientProject → ProjectBrief → ProductionJob queued).
 *
 * Intentionally minimal: ProofHook header, dark layout matching the rest
 * of the app, no redesign. Calls the API at /api/v1/intake/{token} and
 * /api/v1/intake/{token}/submit which are mounted in apps/api/main.py.
 */

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ??
  (typeof window !== "undefined" ? window.location.origin : "");

type SchemaField = {
  field_id: string;
  label: string;
  type?: string;
  required?: boolean;
};

type IntakeSchema = {
  fields: SchemaField[];
  package_slug?: string;
  package_name?: string;
  source?: string;
};

type IntakePayload = {
  intake_request_id: string;
  client_id: string;
  status: string;
  title: string;
  instructions?: string;
  schema: IntakeSchema;
  completed: boolean;
};

type SubmitState =
  | { kind: "loading" }
  | { kind: "invalid" }
  | { kind: "ready"; intake: IntakePayload }
  | { kind: "submitting"; intake: IntakePayload }
  | { kind: "error"; intake: IntakePayload; message: string }
  | { kind: "completed"; intake: IntakePayload | null };

export default function IntakePage() {
  const params = useParams();
  const token = (params?.token as string) ?? "";

  const [state, setState] = useState<SubmitState>({ kind: "loading" });
  const [responses, setResponses] = useState<Record<string, string>>({});
  const [submitterEmail, setSubmitterEmail] = useState<string>("");

  useEffect(() => {
    if (!token) {
      setState({ kind: "invalid" });
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${API_BASE}/api/v1/intake/${encodeURIComponent(token)}`, {
          headers: { Accept: "application/json" },
        });
        if (cancelled) return;
        if (r.status === 404) {
          setState({ kind: "invalid" });
          return;
        }
        if (!r.ok) {
          setState({ kind: "invalid" });
          return;
        }
        const data: IntakePayload = await r.json();
        if (data.completed) {
          setState({ kind: "completed", intake: data });
          return;
        }
        setState({ kind: "ready", intake: data });
      } catch {
        if (!cancelled) setState({ kind: "invalid" });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const fields = useMemo<SchemaField[]>(() => {
    if (state.kind !== "ready" && state.kind !== "submitting" && state.kind !== "error") return [];
    return state.intake?.schema?.fields ?? [];
  }, [state]);

  const requiredMissing = useMemo(() => {
    return fields
      .filter((f) => f.required)
      .filter((f) => !((responses[f.field_id] ?? "").trim().length))
      .map((f) => f.label);
  }, [fields, responses]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (state.kind !== "ready") return;
    if (requiredMissing.length > 0) return;
    setState({ kind: "submitting", intake: state.intake });
    try {
      const r = await fetch(
        `${API_BASE}/api/v1/intake/${encodeURIComponent(token)}/submit`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            responses,
            submitter_email: submitterEmail || "",
          }),
        }
      );
      const body = await r.json().catch(() => ({}));
      if (!r.ok) {
        setState({
          kind: "error",
          intake: state.intake,
          message: body?.detail ?? `Submit failed (${r.status})`,
        });
        return;
      }
      setState({ kind: "completed", intake: state.intake });
    } catch (err) {
      setState({
        kind: "error",
        intake: state.intake,
        message: err instanceof Error ? err.message : "Network error",
      });
    }
  }

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 font-sans antialiased">
      <header className="border-b border-zinc-800 px-6 py-4">
        <div className="mx-auto max-w-2xl">
          <p className="font-mono text-sm text-zinc-400">ProofHook</p>
          <h1 className="mt-1 text-xl font-semibold tracking-tight">Project intake</h1>
        </div>
      </header>

      <div className="mx-auto max-w-2xl px-6 py-10">
        {state.kind === "loading" && (
          <p className="text-zinc-400" data-testid="intake-loading">
            Loading your intake form…
          </p>
        )}

        {state.kind === "invalid" && (
          <section data-testid="intake-invalid" className="space-y-3">
            <h2 className="text-lg font-semibold">This link isn&apos;t valid</h2>
            <p className="text-zinc-400">
              The link may have expired or already been used. If you&apos;ve already
              completed your intake, no further action is needed. If you think this
              is a mistake, reply to your purchase confirmation email and we&apos;ll
              send you a new link.
            </p>
          </section>
        )}

        {state.kind === "completed" && (
          <section data-testid="intake-completed" className="space-y-3">
            <h2 className="text-lg font-semibold">Thanks — your intake is in.</h2>
            <p className="text-zinc-400">
              We&apos;ve got what we need to start production. You&apos;ll get a
              delivery email when your pack is ready.
            </p>
          </section>
        )}

        {(state.kind === "ready" || state.kind === "submitting" || state.kind === "error") && (
          <form onSubmit={handleSubmit} data-testid="intake-form" className="space-y-6">
            {state.intake.instructions && (
              <p className="text-zinc-400 leading-relaxed">{state.intake.instructions}</p>
            )}

            {fields.map((f) => {
              const fieldType = (f.type ?? "text").toLowerCase();
              const value = responses[f.field_id] ?? "";
              const isTextarea = fieldType === "textarea";
              const Tag = isTextarea ? "textarea" : "input";
              return (
                <div key={f.field_id} className="space-y-1.5">
                  <label
                    htmlFor={`f_${f.field_id}`}
                    className="block text-sm font-medium text-zinc-200"
                  >
                    {f.label}
                    {f.required && <span className="ml-1 text-red-400">*</span>}
                  </label>
                  <Tag
                    id={`f_${f.field_id}`}
                    name={f.field_id}
                    required={!!f.required}
                    rows={isTextarea ? 4 : undefined}
                    type={isTextarea ? undefined : "text"}
                    value={value}
                    onChange={(e) =>
                      setResponses((prev) => ({ ...prev, [f.field_id]: e.target.value }))
                    }
                    className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
                  />
                </div>
              );
            })}

            <div className="space-y-1.5">
              <label
                htmlFor="submitter_email"
                className="block text-sm font-medium text-zinc-200"
              >
                Your email
              </label>
              <input
                id="submitter_email"
                type="email"
                value={submitterEmail}
                onChange={(e) => setSubmitterEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
              />
            </div>

            {state.kind === "error" && (
              <p data-testid="intake-error" className="text-sm text-red-400">
                {state.message}
              </p>
            )}

            <button
              type="submit"
              disabled={state.kind === "submitting" || requiredMissing.length > 0}
              className="rounded-md border border-zinc-100 bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-950 hover:bg-zinc-200 disabled:cursor-not-allowed disabled:border-zinc-700 disabled:bg-zinc-800 disabled:text-zinc-500"
            >
              {state.kind === "submitting" ? "Submitting…" : "Submit intake"}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
