'use client';

import { useState } from 'react';
import { CheckCircle, ArrowRight, Star, Video, Palette, Zap } from 'lucide-react';

const INCLUDED = [
  '5 custom AI-generated UGC videos per month',
  'Hook optimization using performance data',
  'Platform-native formatting (TikTok, Reels, Shorts)',
  'Brand voice and aesthetic alignment',
  'Revision round included per video',
];

const PROOF = [
  { metric: '2.4x', label: 'avg engagement lift vs stock content' },
  { metric: '< 24h', label: 'turnaround per video' },
  { metric: '85%', label: 'client retention rate' },
];

export default function AiUgcStarterPage() {
  const [submitted, setSubmitted] = useState(false);
  const [form, setForm] = useState({ name: '', email: '', company: '', message: '' });
  const [sending, setSending] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSending(true);
    try {
      await fetch('/api/v1/leads/capture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          offer_slug: 'ai-ugc-starter',
          brand_slug: 'aesthetic-theory',
          ...form,
        }),
      });
    } catch {}
    setSubmitted(true);
    setSending(false);
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-3xl mx-auto px-6 py-16">
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 bg-violet-900/40 text-violet-300 px-4 py-1.5 rounded-full text-sm mb-6">
            <Video size={14} /> Aesthetic Theory
          </div>
          <h1 className="text-4xl font-bold mb-4">AI UGC Starter Pack</h1>
          <p className="text-xl text-gray-400 max-w-xl mx-auto">
            AI-powered short-form video content for brands that want to scale UGC without scaling headcount.
          </p>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 mb-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold">For</h2>
            <span className="text-violet-400 font-medium">DTC brands, e-commerce, SaaS</span>
          </div>
          <p className="text-gray-400 mb-6">
            Brands spending $5K+/mo on content who need consistent, high-performing UGC at scale.
            Ideal for teams that want AI-native content creation without hiring more creators.
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
                <p className="text-sm text-gray-500">Starting at</p>
                <p className="text-3xl font-bold">$1,500<span className="text-lg text-gray-500 font-normal">/mo</span></p>
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 mb-8">
          {PROOF.map((p, i) => (
            <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
              <p className="text-2xl font-bold text-violet-400">{p.metric}</p>
              <p className="text-xs text-gray-500 mt-1">{p.label}</p>
            </div>
          ))}
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8">
          {submitted ? (
            <div className="text-center py-8">
              <CheckCircle size={48} className="text-emerald-400 mx-auto mb-4" />
              <h3 className="text-xl font-semibold mb-2">Request Received</h3>
              <p className="text-gray-400">We'll be in touch within 24 hours to discuss your content needs.</p>
            </div>
          ) : (
            <>
              <h3 className="text-lg font-semibold mb-4">Get Started</h3>
              <form onSubmit={handleSubmit} className="space-y-4">
                <input
                  type="text" placeholder="Your name" required value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-violet-500 focus:outline-none"
                />
                <input
                  type="email" placeholder="Work email" required value={form.email}
                  onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-violet-500 focus:outline-none"
                />
                <input
                  type="text" placeholder="Company / Brand" value={form.company}
                  onChange={e => setForm(f => ({ ...f, company: e.target.value }))}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-violet-500 focus:outline-none"
                />
                <textarea
                  placeholder="Tell us about your content needs (optional)" value={form.message}
                  onChange={e => setForm(f => ({ ...f, message: e.target.value }))}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-violet-500 focus:outline-none h-24 resize-none"
                />
                <button
                  type="submit" disabled={sending}
                  className="w-full bg-violet-600 hover:bg-violet-500 text-white font-semibold py-3 rounded-lg flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
                >
                  {sending ? 'Submitting...' : 'Request Your Starter Pack'}
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
