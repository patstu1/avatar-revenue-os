'use client';

import { useState } from 'react';
import { CheckCircle, ArrowRight, Crown, Shield, BarChart3 } from 'lucide-react';

const INCLUDED = [
  '20+ custom videos per month across all formats',
  'Dedicated creative strategist',
  'Full brand voice and aesthetic alignment',
  'Multi-platform distribution (TikTok, Instagram, YouTube, X)',
  'Weekly performance reviews and strategy adjustments',
  'Priority turnaround (same-day for urgent requests)',
  'A/B testing and optimization on hooks, CTAs, formats',
  'Monthly creative brief and content calendar',
  'Unlimited revisions',
  'Quarterly brand audit and competitive analysis',
];

const PROOF = [
  { metric: '4.7x', label: 'avg content output increase' },
  { metric: '$180K+', label: 'revenue attributed to retainer clients (avg)' },
  { metric: '100%', label: 'client satisfaction score' },
];

export default function FullCreativeRetainerPage() {
  const [submitted, setSubmitted] = useState(false);
  const [form, setForm] = useState({ name: '', email: '', company: '', message: '', revenue: '' });
  const [sending, setSending] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSending(true);
    try {
      await fetch('/api/v1/leads/capture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ offer_slug: 'full-creative-retainer', brand_slug: 'aesthetic-theory', ...form }),
      });
    } catch {}
    setSubmitted(true);
    setSending(false);
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-3xl mx-auto px-6 py-16">
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 bg-amber-900/40 text-amber-300 px-4 py-1.5 rounded-full text-sm mb-6">
            <Crown size={14} /> Aesthetic Theory — Premium
          </div>
          <h1 className="text-4xl font-bold mb-4">Full Creative Retainer</h1>
          <p className="text-xl text-gray-400 max-w-xl mx-auto">
            Your entire content engine, managed. Strategy, production, optimization, and distribution — all handled.
          </p>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 mb-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold">For</h2>
            <span className="text-amber-400 font-medium">Established brands doing $200K+/mo</span>
          </div>
          <p className="text-gray-400 mb-6">
            For brands that want to hand off their entire content operation. You focus on product and customers —
            we handle everything from strategy to published, monetized content across all platforms.
          </p>

          <h3 className="font-semibold mb-3">What's Included</h3>
          <ul className="space-y-2 mb-6">
            {INCLUDED.map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-gray-300">
                <CheckCircle size={16} className="text-emerald-400 mt-0.5 shrink-0" />
                {item}
              </li>
            ))}
          </ul>

          <div className="border-t border-gray-800 pt-6">
            <div className="flex items-end justify-between">
              <div>
                <p className="text-sm text-gray-500">Monthly retainer</p>
                <p className="text-3xl font-bold">$7,500<span className="text-lg text-gray-500 font-normal">/mo</span></p>
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-500">Minimum engagement</p>
                <p className="text-sm text-gray-400">3 months</p>
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 mb-8">
          {PROOF.map((p, i) => (
            <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
              <p className="text-2xl font-bold text-amber-400">{p.metric}</p>
              <p className="text-xs text-gray-500 mt-1">{p.label}</p>
            </div>
          ))}
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8">
          {submitted ? (
            <div className="text-center py-8">
              <CheckCircle size={48} className="text-emerald-400 mx-auto mb-4" />
              <h3 className="text-xl font-semibold mb-2">Application Received</h3>
              <p className="text-gray-400">We review retainer applications within 48 hours. Expect a call from our creative director.</p>
            </div>
          ) : (
            <>
              <h3 className="text-lg font-semibold mb-4">Apply for Retainer</h3>
              <form onSubmit={handleSubmit} className="space-y-4">
                <input type="text" placeholder="Your name" required value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-amber-500 focus:outline-none" />
                <input type="email" placeholder="Work email" required value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-amber-500 focus:outline-none" />
                <input type="text" placeholder="Brand / Company" required value={form.company} onChange={e => setForm(f => ({ ...f, company: e.target.value }))} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-amber-500 focus:outline-none" />
                <input type="text" placeholder="Current monthly revenue (approx)" value={form.revenue} onChange={e => setForm(f => ({ ...f, revenue: e.target.value }))} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-amber-500 focus:outline-none" />
                <textarea placeholder="What does your content operation look like today?" value={form.message} onChange={e => setForm(f => ({ ...f, message: e.target.value }))} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-amber-500 focus:outline-none h-24 resize-none" />
                <button type="submit" disabled={sending} className="w-full bg-amber-600 hover:bg-amber-500 text-white font-semibold py-3 rounded-lg flex items-center justify-center gap-2 transition-colors disabled:opacity-50">
                  {sending ? 'Submitting...' : 'Apply for Full Retainer'}
                  <ArrowRight size={16} />
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
