"use client";
import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

interface ProofAsset {
  id: string;
  cluster: string;
  title: string;
  video_url: string;
  cover_url: string | null;
  duration_seconds: number;
}

interface OfferPackage {
  id: string;
  name: string;
  description: string;
  price: number;
  cluster: string;
}

interface ClusterInfo {
  name: string;
  niche: string;
  revenue_role: string;
  channels: number;
  proof_count: number;
  offers: OfferPackage[];
}

interface GalleryData {
  clusters: ClusterInfo[];
  proof_assets: ProofAsset[];
  offers: OfferPackage[];
  total_proof_videos: number;
  total_offers: number;
}

const CLUSTER_LABELS: Record<string, { label: string; desc: string; color: string }> = {
  aesthetic_theory: { label: "Beauty & Skincare", desc: "Product showcases, routine explainers, ingredient deep-dives", color: "from-pink-600 to-rose-500" },
  skin_age_lane: { label: "Anti-Aging & Dermatology", desc: "Treatment visuals, before/after content, clinical authority", color: "from-purple-600 to-pink-500" },
  body_theory: { label: "Fitness & Wellness", desc: "Workout promos, transformation stories, nutrition explainers", color: "from-emerald-600 to-teal-500" },
  tool_signal: { label: "AI & Tech Tools", desc: "Product demos, comparison reels, feature walkthroughs", color: "from-blue-600 to-cyan-500" },
  ugc_proof: { label: "UGC Creative Samples", desc: "Brand-ready templates: unboxing, reviews, testimonials", color: "from-amber-600 to-orange-500" },
};

const PACKAGE_FIT: Record<string, string> = {
  aesthetic_theory: "Beauty Content Pack / Full Retainer",
  skin_age_lane: "Beauty Content Pack / Full Retainer",
  body_theory: "Fitness Content Pack / Full Retainer",
  tool_signal: "AI Tool Review Pack / Full Retainer",
  ugc_proof: "AI UGC Starter Pack / Full Retainer",
};

export default function ProofGalleryPage() {
  const [data, setData] = useState<GalleryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/proof-gallery`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="min-h-screen bg-gray-950 flex items-center justify-center"><div className="text-white text-lg">Loading portfolio...</div></div>;
  if (!data) return <div className="min-h-screen bg-gray-950 flex items-center justify-center"><div className="text-red-400">Failed to load gallery</div></div>;

  const filtered = filter === "all" ? data.proof_assets : data.proof_assets.filter(p => p.cluster === filter);
  const clusters = [...new Set(data.proof_assets.map(p => p.cluster))];

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <div className="border-b border-gray-800 bg-gray-950/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-6">
          <h1 className="text-3xl font-bold tracking-tight">AI Creative Portfolio</h1>
          <p className="text-gray-400 mt-1">Short-form video production across beauty, fitness, tech, and UGC</p>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Filter tabs */}
        <div className="flex gap-2 mb-8 flex-wrap">
          <button onClick={() => setFilter("all")} className={`px-4 py-2 rounded-lg text-sm font-medium transition ${filter === "all" ? "bg-white text-gray-900" : "bg-gray-800 text-gray-300 hover:bg-gray-700"}`}>All Categories</button>
          {clusters.map(c => (
            <button key={c} onClick={() => setFilter(c)} className={`px-4 py-2 rounded-lg text-sm font-medium transition ${filter === c ? "bg-white text-gray-900" : "bg-gray-800 text-gray-300 hover:bg-gray-700"}`}>
              {CLUSTER_LABELS[c]?.label || c}
            </button>
          ))}
        </div>

        {/* Proof grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
          {filtered.map(p => {
            const meta = CLUSTER_LABELS[p.cluster] || { label: p.cluster, desc: "", color: "from-gray-600 to-gray-500" };
            return (
              <div key={p.id} className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden hover:border-gray-600 transition group">
                {/* Video */}
                <div className="relative aspect-video bg-gray-800">
                  <video
                    src={p.video_url}
                    poster={p.cover_url || undefined}
                    className="w-full h-full object-cover"
                    muted
                    loop
                    playsInline
                    onMouseEnter={e => (e.target as HTMLVideoElement).play()}
                    onMouseLeave={e => { const v = e.target as HTMLVideoElement; v.pause(); v.currentTime = 0; }}
                  />
                  <div className="absolute top-3 left-3">
                    <span className={`px-2 py-1 rounded text-xs font-semibold bg-gradient-to-r ${meta.color} text-white`}>
                      {meta.label}
                    </span>
                  </div>
                  <div className="absolute bottom-3 right-3 bg-black/70 px-2 py-1 rounded text-xs text-gray-200">
                    {p.duration_seconds}s
                  </div>
                </div>

                {/* Info */}
                <div className="p-4">
                  <h3 className="font-semibold text-white mb-1">{p.title}</h3>
                  <p className="text-sm text-gray-400 mb-3">{meta.desc}</p>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Package: {PACKAGE_FIT[p.cluster] || "Custom"}</span>
                    <span className="text-xs text-emerald-400 font-medium">1080p HD</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* CTA */}
        <div className="bg-gradient-to-r from-blue-900/50 to-purple-900/50 rounded-xl border border-blue-800/50 p-8 text-center mb-8">
          <h2 className="text-2xl font-bold mb-2">Ready to scale your content?</h2>
          <p className="text-gray-300 mb-6">AI-powered short-form video production starting at $1,500/mo</p>
          <a href="/offers" className="inline-block bg-white text-gray-900 px-8 py-3 rounded-lg font-semibold hover:bg-gray-100 transition">
            View Packages
          </a>
        </div>
      </div>
    </div>
  );
}
