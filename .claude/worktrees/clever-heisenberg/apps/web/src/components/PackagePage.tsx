"use client";

import { useState } from "react";

interface PackagePageProps {
  brandSlug: string;
  brandName: string;
  verticalOpener: string;
  packageSlug: string;
  headline: string;
  subheadline: string;
  price: string;
  deliverables: string[];
  bestFit: string[];
  outcome: string;
  primaryCta: string;
  secondaryCta: string;
  salesMicrocopy: string;
  hooks: string[];
}

export default function PackagePage(props: PackagePageProps) {
  const [form, setForm] = useState({ name: "", email: "", company: "", message: "", package_interest: props.packageSlug });
  const [submitted, setSubmitted] = useState(false);
  const [sending, setSending] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSending(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "";
      await fetch(`${apiBase}/api/v1/leads/capture`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          offer_slug: props.packageSlug,
          brand_slug: props.brandSlug,
          ...form,
        }),
      });
    } catch {}
    setSubmitted(true);
    setSending(false);
  };

  return (
    <div style={{ minHeight: "100vh", background: "#fafafa", fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif", color: "#1a1a2e" }}>
      {/* ── HERO ── */}
      <section style={{ background: "linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)", color: "#fff", padding: "5rem 2rem 4rem", textAlign: "center" }}>
        <p style={{ fontSize: "0.85rem", textTransform: "uppercase", letterSpacing: "0.15em", opacity: 0.7, marginBottom: "1rem" }}>{props.brandName}</p>
        <h1 style={{ fontSize: "clamp(2rem, 5vw, 3.2rem)", fontWeight: 700, lineHeight: 1.15, maxWidth: 800, margin: "0 auto 1.2rem" }}>{props.headline}</h1>
        <p style={{ fontSize: "1.15rem", opacity: 0.85, maxWidth: 650, margin: "0 auto 2rem", lineHeight: 1.6 }}>{props.subheadline}</p>
        <p style={{ fontSize: "1.8rem", fontWeight: 700, marginBottom: "1.5rem" }}>{props.price}</p>
        <a href="#form" style={{ display: "inline-block", background: "#e94560", color: "#fff", padding: "16px 44px", borderRadius: 8, fontSize: "1.1rem", fontWeight: 600, textDecoration: "none", transition: "background 0.2s" }}>{props.primaryCta}</a>
        <p style={{ fontSize: "0.9rem", opacity: 0.6, marginTop: "1rem" }}>{props.salesMicrocopy}</p>
      </section>

      {/* ── PROOF STRIP ── */}
      <section style={{ background: "#fff", borderBottom: "1px solid #eee", padding: "2rem", textAlign: "center" }}>
        <p style={{ fontSize: "0.95rem", color: "#666", maxWidth: 700, margin: "0 auto" }}>{props.verticalOpener}</p>
      </section>

      {/* ── DELIVERABLES ── */}
      <section style={{ maxWidth: 800, margin: "0 auto", padding: "4rem 2rem" }}>
        <h2 style={{ fontSize: "1.6rem", fontWeight: 700, marginBottom: "2rem", textAlign: "center" }}>What's included</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1rem" }}>
          {props.deliverables.map((d, i) => (
            <div key={i} style={{ background: "#fff", borderRadius: 10, padding: "1.25rem 1.5rem", boxShadow: "0 1px 4px rgba(0,0,0,0.06)", display: "flex", alignItems: "flex-start", gap: "0.75rem" }}>
              <span style={{ color: "#e94560", fontSize: "1.2rem", fontWeight: 700, lineHeight: 1 }}>+</span>
              <span style={{ fontSize: "1rem", lineHeight: 1.5 }}>{d}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ── BEST FIT ── */}
      <section style={{ background: "#fff", padding: "4rem 2rem" }}>
        <div style={{ maxWidth: 800, margin: "0 auto" }}>
          <h2 style={{ fontSize: "1.6rem", fontWeight: 700, marginBottom: "2rem", textAlign: "center" }}>Best fit for</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1rem" }}>
            {props.bestFit.map((f, i) => (
              <div key={i} style={{ padding: "1rem 1.25rem", borderLeft: "3px solid #e94560", background: "#fafafa", borderRadius: "0 8px 8px 0" }}>
                <p style={{ fontSize: "0.95rem", lineHeight: 1.5, margin: 0 }}>{f}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── OUTCOME ── */}
      <section style={{ maxWidth: 800, margin: "0 auto", padding: "3rem 2rem", textAlign: "center" }}>
        <h2 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: "1rem" }}>What you walk away with</h2>
        <p style={{ fontSize: "1.1rem", lineHeight: 1.6, color: "#444" }}>{props.outcome}</p>
      </section>

      {/* ── CTA FORM ── */}
      <section id="form" style={{ background: "#1a1a2e", padding: "4rem 2rem", color: "#fff" }}>
        <div style={{ maxWidth: 520, margin: "0 auto" }}>
          <h2 style={{ fontSize: "1.6rem", fontWeight: 700, textAlign: "center", marginBottom: "0.5rem" }}>Tell us what you need</h2>
          <p style={{ textAlign: "center", opacity: 0.7, marginBottom: "2rem", fontSize: "0.95rem" }}>Share your brand, goals, and timeline and we'll follow up with the best-fit package.</p>
          {submitted ? (
            <div style={{ textAlign: "center", padding: "3rem 1rem" }}>
              <p style={{ fontSize: "1.3rem", fontWeight: 600, color: "#e94560" }}>Thank you. We'll be in touch.</p>
              <p style={{ opacity: 0.7, marginTop: "0.5rem" }}>You'll hear from us within 24 hours.</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Your name" required style={inputStyle} />
              <input value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} type="email" placeholder="Work email" required style={inputStyle} />
              <input value={form.company} onChange={e => setForm({ ...form, company: e.target.value })} placeholder="Company / brand name" style={inputStyle} />
              <textarea value={form.message} onChange={e => setForm({ ...form, message: e.target.value })} placeholder="What are you looking for? Tell us about your goals, timeline, and budget range." rows={4} style={{ ...inputStyle, resize: "vertical" }} />
              <button type="submit" disabled={sending} style={{ width: "100%", padding: "16px", background: "#e94560", color: "#fff", border: "none", borderRadius: 8, fontSize: "1.1rem", fontWeight: 600, cursor: "pointer", marginTop: "0.5rem", opacity: sending ? 0.7 : 1 }}>
                {sending ? "Sending..." : props.primaryCta}
              </button>
            </form>
          )}
        </div>
      </section>

      {/* ── FAQ ── */}
      <section style={{ maxWidth: 700, margin: "0 auto", padding: "4rem 2rem" }}>
        <h2 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: "2rem", textAlign: "center" }}>Questions</h2>
        {FAQ.map((q, i) => (
          <div key={i} style={{ marginBottom: "1.5rem" }}>
            <h4 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "0.4rem" }}>{q.q}</h4>
            <p style={{ fontSize: "0.95rem", color: "#555", lineHeight: 1.5, margin: 0 }}>{q.a}</p>
          </div>
        ))}
        <p style={{ textAlign: "center", marginTop: "2rem", fontSize: "0.9rem", color: "#888" }}>
          Need sharper messaging or a stronger funnel? <a href={`/offers/${props.brandSlug}/creative-strategy-funnel-upgrade`} style={{ color: "#e94560" }}>Ask about the Strategy Upgrade</a>.
        </p>
      </section>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%", padding: "14px 16px", marginBottom: "12px",
  background: "rgba(255,255,255,0.08)", border: "1px solid rgba(255,255,255,0.15)",
  borderRadius: 8, color: "#fff", fontSize: "1rem",
  outline: "none",
};

const FAQ = [
  { q: "How fast is turnaround?", a: "Most starter and sprint work ships fast. Monthly packages follow a structured delivery cadence based on scope." },
  { q: "Is this for paid ads, organic, or both?", a: "Both. Packages create usable creative for paid testing, organic posting, and general offer support." },
  { q: "Do you help with landing pages or funnels?", a: "Yes. Higher-tier packages and the Funnel Upgrade include landing and offer-path support." },
  { q: "What happens after I submit?", a: "You will be contacted to confirm fit, scope, timeline, and the right package." },
];
