"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

interface LandingPageData {
  page_id: string;
  brand_name: string;
  brand_slug: string;
  page_type: string;
  headline: string;
  subheadline: string;
  hook_angle: string;
  proof_blocks: Array<{ text: string }>;
  objection_blocks: Array<{ objection: string; answer: string }>;
  cta_blocks: Array<{ text: string; url: string }>;
  disclosure_blocks: Array<{ text: string }>;
  media_blocks: Array<{ type: string; url: string; alt: string }>;
  destination_url: string;
  tracking_params: Record<string, string>;
}

export default function DynamicLandingPage() {
  const params = useParams();
  const pageId = params?.pageId as string;
  const [page, setPage] = useState<LandingPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [formSubmitted, setFormSubmitted] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", company: "", message: "" });

  useEffect(() => {
    if (!pageId) return;
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "";
    fetch(`${apiBase}/api/v1/lp/${pageId}`)
      .then((res) => {
        if (!res.ok) throw new Error("Page not found");
        return res.json();
      })
      .then((data) => { setPage(data); setLoading(false); })
      .catch((err) => { setError(err.message); setLoading(false); });
  }, [pageId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!page) return;
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "";
    try {
      await fetch(`${apiBase}/api/v1/leads/capture`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          offer_slug: page.page_type,
          brand_slug: page.brand_slug,
          ...form,
        }),
      });
      setFormSubmitted(true);
    } catch {}
  };

  if (loading) return <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh" }}>Loading...</div>;
  if (error || !page) return <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh", color: "#e53e3e" }}>{error || "Page not found"}</div>;

  return (
    <div style={{ minHeight: "100vh", background: "#f8f9fa", fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" }}>
      {/* Hero */}
      <div style={{ background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)", color: "#fff", padding: "4rem 2rem", textAlign: "center" }}>
        <h1 style={{ fontSize: "2.5rem", marginBottom: "1rem", lineHeight: 1.2 }}>{page.headline}</h1>
        {page.subheadline && <h2 style={{ fontSize: "1.2rem", fontWeight: 400, opacity: 0.9 }}>{page.subheadline}</h2>}
      </div>

      <div style={{ maxWidth: 800, margin: "0 auto", padding: "3rem 2rem" }}>
        {/* CTAs */}
        {page.cta_blocks.length > 0 && (
          <div style={{ textAlign: "center", padding: "2rem 0" }}>
            {page.cta_blocks.map((cta, i) => (
              <a key={i} href={cta.url || page.destination_url || "#"} style={{ display: "inline-block", background: "#667eea", color: "#fff", padding: "16px 40px", borderRadius: 8, textDecoration: "none", fontSize: "1.1rem", fontWeight: 600, margin: "0.5rem" }}>
                {cta.text || "Get Started"}
              </a>
            ))}
          </div>
        )}

        {/* Proof blocks */}
        {page.proof_blocks.map((p, i) => (
          <div key={i} style={{ background: "#fff", borderRadius: 8, padding: "1.5rem", margin: "1rem 0", boxShadow: "0 1px 3px rgba(0,0,0,0.1)" }}>
            <p>{p.text}</p>
          </div>
        ))}

        {/* Objection blocks */}
        {page.objection_blocks.map((obj, i) => (
          <div key={i} style={{ margin: "1.5rem 0", padding: "1.5rem", borderLeft: "4px solid #667eea", background: "#fff" }}>
            <h4 style={{ color: "#667eea", marginBottom: "0.5rem" }}>{obj.objection}</h4>
            <p>{obj.answer}</p>
          </div>
        ))}

        {/* Lead capture form */}
        <h3 style={{ textAlign: "center", margin: "2rem 0 1rem" }}>Get in Touch</h3>
        {formSubmitted ? (
          <p style={{ textAlign: "center", fontSize: "1.2rem", color: "#667eea", padding: "2rem" }}>Thank you! We will be in touch soon.</p>
        ) : (
          <form onSubmit={handleSubmit} style={{ maxWidth: 500, margin: "0 auto", padding: "2rem", background: "#fff", borderRadius: 12, boxShadow: "0 4px 12px rgba(0,0,0,0.1)" }}>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Your name" required style={{ width: "100%", padding: 12, margin: "8px 0", border: "1px solid #ddd", borderRadius: 6, fontSize: "1rem" }} />
            <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} type="email" placeholder="Your email" required style={{ width: "100%", padding: 12, margin: "8px 0", border: "1px solid #ddd", borderRadius: 6, fontSize: "1rem" }} />
            <input value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} placeholder="Company (optional)" style={{ width: "100%", padding: 12, margin: "8px 0", border: "1px solid #ddd", borderRadius: 6, fontSize: "1rem" }} />
            <textarea value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} placeholder="Tell us about your needs..." style={{ width: "100%", padding: 12, margin: "8px 0", border: "1px solid #ddd", borderRadius: 6, fontSize: "1rem", minHeight: 80 }} />
            <button type="submit" style={{ width: "100%", padding: 14, background: "#667eea", color: "#fff", border: "none", borderRadius: 6, fontSize: "1.1rem", fontWeight: 600, cursor: "pointer", marginTop: 12 }}>Submit</button>
          </form>
        )}

        {/* Disclosures */}
        {page.disclosure_blocks.map((d, i) => (
          <p key={i} style={{ fontSize: "0.8rem", color: "#666", marginTop: "2rem", textAlign: "center" }}>{d.text}</p>
        ))}
      </div>
    </div>
  );
}
