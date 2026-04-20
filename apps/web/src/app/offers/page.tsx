"use client";
import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

interface OfferPackage {
  id: string;
  name: string;
  description: string;
  price: number;
  cluster: string;
}

interface GalleryData {
  offers: OfferPackage[];
}

const PACKAGE_DETAILS: Record<string, { who: string; includes: string[]; highlight?: boolean }> = {
  "AI UGC Starter Pack": {
    who: "Brands starting with AI-generated short-form content",
    includes: ["10 short-form videos/month", "Motion + Ken Burns compositing", "Platform-ready formats (Reels, TikTok, Shorts)", "Hooks + scripts included", "Weekly delivery"],
  },
  "Beauty Content Pack": {
    who: "Beauty, skincare, and wellness brands",
    includes: ["25 beauty/skincare videos/month", "Product showcases + routine explainers", "Ingredient breakdowns + comparison reels", "Platform-optimized captions + CTAs", "Bi-weekly delivery batches"],
  },
  "Fitness Content Pack": {
    who: "Fitness, health, and supplement brands",
    includes: ["25 fitness/wellness videos/month", "Workout demos + transformation promos", "Nutrition explainers + challenge content", "Community-ready format", "Bi-weekly delivery batches"],
  },
  "AI Tool Review Pack": {
    who: "SaaS, AI, and tech companies",
    includes: ["20 AI/SaaS tool reviews/month", "Demo walkthroughs + feature highlights", "Comparison reels + alternative breakdowns", "Affiliate-ready CTAs", "Weekly delivery"],
  },
  "Full Creative Retainer": {
    who: "Brands that need a complete content engine",
    includes: ["50 videos/month across all formats", "Scripts + hooks + presenter videos", "Multi-cluster coverage", "Dedicated production queue", "Priority delivery + revision rounds", "Monthly strategy call"],
    highlight: true,
  },
};

export default function OffersPage() {
  const [data, setData] = useState<GalleryData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/proof-gallery`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="min-h-screen bg-gray-950 flex items-center justify-center"><div className="text-white">Loading...</div></div>;

  const packages = (data?.offers || [])
    .filter(o => o.price >= 1000)
    .sort((a, b) => a.price - b.price);

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-5xl mx-auto px-6 py-12">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold tracking-tight mb-3">AI Video Packages</h1>
          <p className="text-gray-400 text-lg max-w-2xl mx-auto">
            Short-form video production powered by AI. Real videos, real hooks, real results. No fluff.
          </p>
        </div>

        {/* Package cards */}
        <div className="space-y-6">
          {packages.map(pkg => {
            const details = PACKAGE_DETAILS[pkg.name] || { who: "Growing brands", includes: [pkg.description] };
            const isHighlight = details.highlight;

            return (
              <div key={pkg.id} className={`rounded-xl border p-6 md:p-8 transition ${isHighlight ? "bg-gradient-to-r from-blue-950/60 to-purple-950/60 border-blue-700/50" : "bg-gray-900 border-gray-800 hover:border-gray-600"}`}>
                <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-6">
                  {/* Left */}
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h2 className="text-xl font-bold">{pkg.name}</h2>
                      {isHighlight && <span className="px-2 py-0.5 rounded text-xs font-semibold bg-blue-600 text-white">Most Popular</span>}
                    </div>
                    <p className="text-gray-400 text-sm mb-4">For: {details.who}</p>
                    <ul className="space-y-2">
                      {details.includes.map((item, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-gray-300">
                          <span className="text-emerald-400 mt-0.5">&#10003;</span>
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Right — price + CTA */}
                  <div className="flex flex-col items-center md:items-end gap-3 min-w-[180px]">
                    <div className="text-right">
                      <div className="text-3xl font-bold">${pkg.price.toLocaleString()}</div>
                      <div className="text-gray-500 text-sm">per month</div>
                    </div>
                    <a
                      href="mailto:hello@storistudio.app?subject=Interest%20in%20"
                      className={`px-6 py-3 rounded-lg font-semibold text-sm transition w-full text-center ${isHighlight ? "bg-white text-gray-900 hover:bg-gray-100" : "bg-gray-800 text-white hover:bg-gray-700 border border-gray-700"}`}
                    >
                      Get Started
                    </a>
                    <a href="/proof" className="text-xs text-gray-500 hover:text-gray-300 transition">
                      View sample work &rarr;
                    </a>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Bottom CTA */}
        <div className="mt-12 text-center">
          <p className="text-gray-500 text-sm mb-4">Need something custom? We build content systems for brands at any scale.</p>
          <a href="mailto:hello@storistudio.app?subject=Custom%20Package%20Inquiry" className="text-blue-400 hover:text-blue-300 text-sm font-medium">
            Contact for custom pricing &rarr;
          </a>
        </div>
      </div>
    </div>
  );
}
