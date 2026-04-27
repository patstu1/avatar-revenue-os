"use client";

/**
 * AI Buyer Trust Test — interactive hero form + inline result card.
 *
 * Visual rules (locked):
 *   - zinc-only palette; matches existing ProofHook /about card pattern
 *     (rounded-md border border-zinc-800 bg-zinc-900/40)
 *   - same primary CTA styling as marketing-shell.CTA
 *   - inputs use bg-zinc-950 text-zinc-100 border-zinc-800 — the same
 *     contrast as the rest of the dark-neutral site
 *
 * Behavior:
 *   - All fields visible at once (no quiz wizard) so the form is usable
 *     in under 30 seconds.
 *   - Inline validation surfaces on submit; field-level errors from the
 *     backend (e.g. blocked URL, throwaway email) map to the right input.
 *   - On submit, the form card is replaced inline by ScoreResultCard.
 *   - "Test another business" resets the form.
 */

import { useState } from "react";

import {
  type TrustTestResult,
  TrustTestError,
  submitTrustTest,
} from "@/lib/ai-buyer-trust-api";

import { ScoreResultCard } from "./ScoreResultCard";

type FormState = {
  website_url: string;
  company_name: string;
  industry: string;
  contact_email: string;
  competitor_url: string;
  city_or_market: string;
  /** Honeypot: humans never fill this. Bots that auto-complete by name
   * (or that submit the form via headless click on every input) do.
   * Backend rejects on non-empty. */
  bot_field: string;
};

const EMPTY_FORM: FormState = {
  website_url: "",
  company_name: "",
  industry: "",
  contact_email: "",
  competitor_url: "",
  city_or_market: "",
  bot_field: "",
};

export function AiBuyerTrustTest() {
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<{ field: string | null; message: string } | null>(
    null,
  );
  const [result, setResult] = useState<TrustTestResult | null>(null);

  const onChange =
    (field: keyof FormState) =>
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setForm((f) => ({ ...f, [field]: e.target.value }));
    };

  const onSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      const r = await submitTrustTest({
        website_url: form.website_url.trim(),
        company_name: form.company_name.trim(),
        industry: form.industry.trim(),
        contact_email: form.contact_email.trim(),
        competitor_url: form.competitor_url.trim() || undefined,
        city_or_market: form.city_or_market.trim() || undefined,
        bot_field: form.bot_field,
      });
      setResult(r);
    } catch (err) {
      if (err instanceof TrustTestError) {
        setError({ field: err.field, message: err.message });
      } else {
        setError({
          field: null,
          message:
            "Something went wrong submitting the test. Try again, or email hello@proofhook.com.",
        });
      }
    } finally {
      setSubmitting(false);
    }
  };

  const onReset = () => {
    setResult(null);
    setError(null);
  };

  if (result) {
    return <ScoreResultCard result={result} onReset={onReset} />;
  }

  return (
    <article
      data-testid="trust-test-form-card"
      className="rounded-md border border-zinc-800 bg-zinc-900/40 p-6 sm:p-8"
    >
      <p className="font-mono text-xs uppercase tracking-wider text-zinc-500">
        AI Buyer Trust Test
      </p>
      <h2 className="mt-2 text-xl font-semibold tracking-tight text-zinc-100">
        Check your AI Buyer Trust Score
      </h2>
      <p className="mt-3 text-sm text-zinc-400 leading-relaxed">
        We scan public website signals like proof, offers, FAQs, schema,
        comparison readiness, and trust structure.
      </p>

      <form
        onSubmit={onSubmit}
        className="mt-6 space-y-4"
        noValidate
        data-testid="trust-test-form"
      >
        {/* Honeypot — visually hidden + tab-skipped + autocomplete-off so
            humans never fill it. Bots that auto-complete by name do. */}
        <div
          aria-hidden
          style={{
            position: "absolute",
            left: "-10000px",
            top: "auto",
            width: "1px",
            height: "1px",
            overflow: "hidden",
          }}
        >
          <label htmlFor="company_role">Leave this field blank</label>
          <input
            id="company_role"
            name="company_role"
            type="text"
            tabIndex={-1}
            autoComplete="off"
            value={form.bot_field}
            onChange={(e) =>
              setForm((f) => ({ ...f, bot_field: e.target.value }))
            }
          />
        </div>
        <Field
          id="website_url"
          label="Website URL"
          required
          type="url"
          placeholder="https://your-business.com"
          value={form.website_url}
          onChange={onChange("website_url")}
          error={error?.field === "website_url" ? error.message : undefined}
          autoComplete="url"
          inputMode="url"
        />
        <Field
          id="company_name"
          label="Company name"
          required
          type="text"
          placeholder="Your business name"
          value={form.company_name}
          onChange={onChange("company_name")}
          error={error?.field === "company_name" ? error.message : undefined}
          autoComplete="organization"
        />
        <Field
          id="industry"
          label="Industry / category"
          required
          type="text"
          placeholder="e.g. SaaS, med spa, law firm, agency, ecommerce"
          value={form.industry}
          onChange={onChange("industry")}
          error={error?.field === "industry" ? error.message : undefined}
        />
        <Field
          id="contact_email"
          label="Email"
          required
          type="email"
          placeholder="you@your-business.com"
          value={form.contact_email}
          onChange={onChange("contact_email")}
          error={error?.field === "contact_email" ? error.message : undefined}
          autoComplete="email"
          inputMode="email"
        />
        <Field
          id="competitor_url"
          label="Top competitor URL"
          required={false}
          type="url"
          placeholder="Optional — used in your full Authority Snapshot"
          value={form.competitor_url}
          onChange={onChange("competitor_url")}
          error={error?.field === "competitor_url" ? error.message : undefined}
          autoComplete="url"
          inputMode="url"
        />
        <Field
          id="city_or_market"
          label="City or market"
          required={false}
          type="text"
          placeholder="Optional — for local-business signal weighting"
          value={form.city_or_market}
          onChange={onChange("city_or_market")}
          error={error?.field === "city_or_market" ? error.message : undefined}
        />

        {error && error.field === null ? (
          <p
            role="alert"
            className="rounded-md border border-zinc-700 bg-zinc-950 p-3 text-sm text-zinc-300"
          >
            {error.message}
          </p>
        ) : null}

        <div className="pt-2">
          <button
            type="submit"
            disabled={submitting || !canSubmit(form)}
            data-cta="trust-test-submit"
            className="inline-block w-full rounded-md border border-zinc-100 bg-zinc-100 px-5 py-3 text-sm font-medium text-zinc-950 hover:bg-zinc-200 disabled:cursor-not-allowed disabled:border-zinc-700 disabled:bg-zinc-800 disabled:text-zinc-500 sm:w-auto"
          >
            {submitting ? "Scanning your site…" : "Test My Business"}
          </button>
          <p className="mt-3 text-xs text-zinc-500 leading-relaxed">
            Based on public website signals: offers, proof, FAQs, schema,
            comparisons, crawlability, and trust structure.
          </p>
        </div>
      </form>
    </article>
  );
}

function canSubmit(form: FormState): boolean {
  return (
    form.website_url.trim().length > 3 &&
    form.company_name.trim().length > 0 &&
    form.industry.trim().length > 0 &&
    /\S+@\S+\.\S+/.test(form.contact_email.trim())
  );
}

function Field({
  id,
  label,
  required,
  type,
  placeholder,
  value,
  onChange,
  error,
  autoComplete,
  inputMode,
}: {
  id: string;
  label: string;
  required: boolean;
  type: "text" | "url" | "email";
  placeholder: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  error: string | undefined;
  autoComplete?: string;
  inputMode?: "url" | "email";
}) {
  return (
    <div>
      <label
        htmlFor={id}
        className="block font-mono text-[11px] uppercase tracking-wider text-zinc-500"
      >
        {label}
        {required ? null : (
          <span className="ml-1 text-zinc-600 normal-case tracking-normal">
            (optional)
          </span>
        )}
      </label>
      <input
        id={id}
        name={id}
        type={type}
        required={required}
        autoComplete={autoComplete}
        inputMode={inputMode}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        aria-invalid={!!error}
        aria-describedby={error ? `${id}-error` : undefined}
        className="mt-1.5 block w-full rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2.5 text-sm text-zinc-100 placeholder-zinc-600 focus:border-zinc-500 focus:outline-none focus:ring-0"
      />
      {error ? (
        <p id={`${id}-error`} className="mt-1.5 text-xs text-zinc-300">
          {error}
        </p>
      ) : null}
    </div>
  );
}
