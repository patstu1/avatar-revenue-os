#!/usr/bin/env python3
"""Generate all package page.tsx files for the 3 verticals."""
import os

BASE = os.path.join(os.path.dirname(__file__), "..", "apps", "web", "src", "app", "offers")

# Per-vertical copy
VERTICALS = {
    "aesthetic-theory": {
        "brandName": "Aesthetic Theory",
        "verticalOpener": "Creative packages for beauty, skincare, aesthetics, and wellness brands that need stronger short-form assets, sharper hooks, and better offer support.",
    },
    "body-theory": {
        "brandName": "Body Theory",
        "verticalOpener": "Creative packages for fitness, supplement, recovery, and wellness brands that need more usable content and stronger campaign-ready assets.",
    },
    "tool-signal": {
        "brandName": "Tool Signal",
        "verticalOpener": "Creative packages for AI, SaaS, and software brands that need product-facing short-form content, stronger proof, and better top-of-funnel creative.",
    },
}

# Per-package × per-vertical copy
PACKAGES = {
    "ugc-starter-pack": {
        "price": "$1,500",
        "deliverables": ["4 short-form video assets", "3 hook variations", "1 CTA angle", "Light editing and packaging", "7-day turnaround"],
        "salesMicrocopy": "Fastest way to get usable creative live.",
        "aesthetic-theory": {
            "headline": "Short-form beauty creative that makes your brand look current fast.",
            "subheadline": "Built for skincare, beauty, aesthetics, and wellness brands that need fresh content, stronger hooks, and more usable assets without waiting on a full production cycle.",
            "primaryCta": "Get the Starter Pack",
            "secondaryCta": "See what's included",
            "bestFit": ["Beauty and skincare brands", "Wellness and aesthetics brands", "Founders who need quick proof-of-concept assets", "Brands testing short-form creative for the first time"],
        },
        "body-theory": {
            "headline": "Fast-turn fitness creative for brands that need more usable content now.",
            "subheadline": "Designed for supplement, recovery, fitness, and wellness brands that need short-form assets, stronger hooks, and more content to work with right away.",
            "primaryCta": "Get the Starter Pack",
            "secondaryCta": "See what's included",
            "bestFit": ["Supplement and recovery brands", "Fitness and wellness brands", "Founders who need fast proof-of-concept assets", "Brands entering short-form content for the first time"],
        },
        "tool-signal": {
            "headline": "Fast-turn short-form content for software and AI brands that need proof fast.",
            "subheadline": "A simple entry package for SaaS and AI companies that want more founder-style, product-facing, or explain-it-fast content without building an in-house production process first.",
            "primaryCta": "Get the Starter Pack",
            "secondaryCta": "See what's included",
            "bestFit": ["SaaS and AI startups", "Developer tools and productivity brands", "Founders who need quick product-facing assets", "Software brands testing short-form creative"],
        },
        "outcome": "You leave with usable short-form creative you can post, test, and build from immediately.",
        "hooks": [],
    },
    "growth-content-pack": {
        "price": "Starting at $2,500/month",
        "deliverables": ["8 to 12 short-form assets per month", "Multiple hook and caption variations", "2 CTA angles", "Monthly creative refresh", "Structured delivery cadence"],
        "salesMicrocopy": "Built for brands that need steady output, not random content bursts.",
        "aesthetic-theory": {
            "headline": "A monthly beauty content engine for brands that need more output and more consistency.",
            "subheadline": "For brands that want recurring short-form creative, cleaner offer alignment, and a steadier stream of assets for social, paid, and campaign support.",
            "primaryCta": "Start the Growth Pack",
            "secondaryCta": "Request package details",
            "bestFit": ["Growing DTC beauty brands", "Aesthetic and skincare businesses scaling content", "Wellness brands that need monthly creative volume", "Brands with active social channels that need consistent output"],
        },
        "body-theory": {
            "headline": "A monthly content pack for fitness brands that need steady creative volume.",
            "subheadline": "For brands that want recurring assets for social, campaigns, and product pushes without rebuilding the content process every week.",
            "primaryCta": "Start the Growth Pack",
            "secondaryCta": "Request package details",
            "bestFit": ["Growing supplement and fitness brands", "Recovery and wellness companies scaling content", "Brands with active social channels", "Teams that need consistent monthly output"],
        },
        "tool-signal": {
            "headline": "A monthly content engine for SaaS brands that need more top-of-funnel assets.",
            "subheadline": "For teams that want a steady stream of short-form content around product value, founder presence, use cases, and offer support.",
            "primaryCta": "Start the Growth Pack",
            "secondaryCta": "Request package details",
            "bestFit": ["Growing SaaS and AI companies", "Developer tools building audience", "Software brands with active social channels", "Teams that need consistent top-of-funnel content"],
        },
        "outcome": "You get a repeatable monthly stream of creative that helps you stay visible and gives you more to test.",
        "hooks": [],
    },
    "performance-creative-pack": {
        "price": "Starting at $4,500/month",
        "deliverables": ["12 to 20 short-form assets per month", "Hook and angle testing variations", "Offer and landing page support", "Monthly optimization pass", "Creative reporting and iteration recommendations"],
        "salesMicrocopy": "More variants, better hooks, stronger testing.",
        "aesthetic-theory": {
            "headline": "Beauty creative built to test, improve, and perform harder.",
            "subheadline": "Made for brands that already understand creative affects conversion and want stronger hooks, more variations, and a more serious testing cadence.",
            "primaryCta": "Apply for the Performance Pack",
            "secondaryCta": "View deliverables",
            "bestFit": ["Beauty brands running paid traffic", "Teams with active offers or campaigns", "Brands that know creative quality affects results", "DTC brands ready to scale content volume"],
        },
        "body-theory": {
            "headline": "Performance-focused fitness creative with more hooks, more variants, and more testing room.",
            "subheadline": "For brands running offers or paid traffic that need stronger creative angles, better testing coverage, and more useful output each month.",
            "primaryCta": "Apply for the Performance Pack",
            "secondaryCta": "View deliverables",
            "bestFit": ["Fitness brands running paid traffic", "Supplement brands with active campaigns", "Brands that already know creative quality affects results", "Teams ready to scale creative testing"],
        },
        "tool-signal": {
            "headline": "Performance creative for SaaS brands that want more testable content and sharper hooks.",
            "subheadline": "Built for teams running campaigns, launches, or active acquisition who need stronger creative angles, more variants, and better alignment between content and offer.",
            "primaryCta": "Apply for the Performance Pack",
            "secondaryCta": "View deliverables",
            "bestFit": ["SaaS brands running paid acquisition", "AI companies with active campaigns", "Teams that need creative testing at scale", "Software brands with active ad spend"],
        },
        "outcome": "You get more creative, more testable variants, and a stronger performance-oriented content system.",
        "hooks": [],
    },
    "full-creative-retainer": {
        "price": "Starting at $7,500/month",
        "deliverables": ["Recurring short-form creative production", "Multi-angle hook development", "Offer and landing support", "Reporting and strategy layer", "Priority turnaround", "Higher-volume monthly delivery"],
        "salesMicrocopy": "A deeper creative partnership for brands that need serious output.",
        "aesthetic-theory": {
            "headline": "A full creative partner for beauty brands that need serious output.",
            "subheadline": "For beauty and aesthetics brands that want recurring production, stronger campaign support, and a more complete creative system behind their offers.",
            "primaryCta": "Book the Full Retainer",
            "secondaryCta": "Talk through your needs",
            "bestFit": ["Funded beauty brands", "Aggressive growth teams in aesthetics", "Businesses with active ad spend", "Brands that need creative as an ongoing operating function"],
        },
        "body-theory": {
            "headline": "A serious creative retainer for fitness and wellness brands that want more output.",
            "subheadline": "For brands that need a consistent partner producing recurring content, stronger campaign assets, and a more reliable creative rhythm.",
            "primaryCta": "Book the Full Retainer",
            "secondaryCta": "Talk through your needs",
            "bestFit": ["Funded fitness and supplement brands", "Aggressive growth teams", "Businesses with active ad spend", "Brands that need creative as an ongoing function"],
        },
        "tool-signal": {
            "headline": "A full creative retainer for AI and SaaS brands that need output at speed.",
            "subheadline": "For teams that need recurring short-form content, stronger product-facing assets, faster execution, and a more complete creative support layer.",
            "primaryCta": "Book the Full Retainer",
            "secondaryCta": "Talk through your needs",
            "bestFit": ["Funded SaaS and AI companies", "Aggressive growth teams in tech", "Businesses with active ad spend", "Brands that need creative as an ongoing operating function"],
        },
        "outcome": "You get a more complete creative engine with stronger support, faster execution, and more strategic continuity.",
        "hooks": [],
    },
    "launch-sprint": {
        "price": "Starting at $5,000",
        "deliverables": ["Fast-turn asset batch", "Launch-focused hook set", "CTA alignment", "Compressed delivery timeline", "Campaign-ready creative package"],
        "salesMicrocopy": "For urgent campaigns that need creative now, not next month.",
        "aesthetic-theory": {
            "headline": "Fast-turn beauty creative for launches, pushes, and seasonal moments.",
            "subheadline": "Built for promotions, launches, and urgent campaign windows when your brand needs strong creative quickly and cannot afford delay.",
            "primaryCta": "Start a Launch Sprint",
            "secondaryCta": "Get launch support",
            "bestFit": ["Product launches in beauty and skincare", "Seasonal promotion pushes", "Event or campaign windows", "Brands with urgent content demand"],
        },
        "body-theory": {
            "headline": "Fast-turn creative for supplement drops, campaign pushes, and fitness launches.",
            "subheadline": "When timing matters, this sprint gives your brand a concentrated batch of campaign-ready creative built for immediate use.",
            "primaryCta": "Start a Launch Sprint",
            "secondaryCta": "Get launch support",
            "bestFit": ["Supplement drops and product launches", "Seasonal fitness campaign pushes", "Event or promotion windows", "Brands with urgent content demand"],
        },
        "tool-signal": {
            "headline": "Fast-turn launch creative for product pushes, feature launches, and campaign windows.",
            "subheadline": "For SaaS and AI teams that need launch-ready short-form creative quickly enough to support a real release window.",
            "primaryCta": "Start a Launch Sprint",
            "secondaryCta": "Get launch support",
            "bestFit": ["Product and feature launches", "Funding announcements and pushes", "Seasonal or event campaigns", "Teams with urgent content demand"],
        },
        "outcome": "You get a concentrated batch of launch-ready creative fast enough to matter.",
        "hooks": [],
    },
}

# Strategy upgrade (backend upsell, still gets a page)
STRATEGY = {
    "slug": "creative-strategy-funnel-upgrade",
    "price": "Starting at $2,500",
    "deliverables": ["Messaging refinement", "Offer positioning review", "Landing page or funnel upgrade recommendations", "Content-to-CTA alignment", "Strategic improvement plan"],
    "salesMicrocopy": "Make the content and the conversion path work together.",
    "headline": {
        "aesthetic-theory": "Tighten the message, sharpen the offer, and improve the conversion path.",
        "body-theory": "Make your content, offer, and conversion path actually work together.",
        "tool-signal": "Strengthen the message, the offer, and the path from content to conversion.",
    },
    "subheadline": {
        "aesthetic-theory": "For brands with decent traffic or content activity that still need the offer, messaging, and landing path to work together more cleanly.",
        "body-theory": "Best for fitness and wellness brands with active campaigns that need cleaner messaging, stronger offer positioning, and a better content-to-conversion path.",
        "tool-signal": "Ideal for SaaS and AI brands that have product activity but need better content positioning, sharper messaging, and a cleaner conversion path.",
    },
    "bestFit": {
        "aesthetic-theory": ["Brands with traffic but weak conversion", "Teams with scattered messaging", "Clients already buying content who need stronger downstream performance"],
        "body-theory": ["Fitness brands with traffic but weak conversion", "Teams with scattered messaging", "Clients who need stronger downstream performance"],
        "tool-signal": ["SaaS brands with product activity but weak positioning", "Teams with scattered messaging", "Clients who need a cleaner conversion path"],
    },
    "outcome": "You leave with a clearer message, a stronger offer path, and a better conversion foundation.",
}

TEMPLATE = '''"use client";

import PackagePage from "@/components/PackagePage";

export default function Page() {{
  return (
    <PackagePage
      brandSlug="{brandSlug}"
      brandName="{brandName}"
      verticalOpener="{verticalOpener}"
      packageSlug="{packageSlug}"
      headline="{headline}"
      subheadline="{subheadline}"
      price="{price}"
      deliverables={{{deliverables}}}
      bestFit={{{bestFit}}}
      outcome="{outcome}"
      primaryCta="{primaryCta}"
      secondaryCta="{secondaryCta}"
      salesMicrocopy="{salesMicrocopy}"
      hooks={{[]}}
    />
  );
}}
'''

def esc(s):
    return s.replace('"', '\\"').replace('\n', ' ')

def arr(items):
    return "[" + ", ".join(f'"{esc(i)}"' for i in items) + "]"

for brand_slug, brand_info in VERTICALS.items():
    for pkg_slug, pkg in PACKAGES.items():
        v = pkg[brand_slug]
        code = TEMPLATE.format(
            brandSlug=brand_slug,
            brandName=brand_info["brandName"],
            verticalOpener=esc(brand_info["verticalOpener"]),
            packageSlug=pkg_slug,
            headline=esc(v["headline"]),
            subheadline=esc(v["subheadline"]),
            price=esc(pkg["price"]),
            deliverables=arr(pkg["deliverables"]),
            bestFit=arr(v["bestFit"]),
            outcome=esc(pkg["outcome"]),
            primaryCta=esc(v["primaryCta"]),
            secondaryCta=esc(v["secondaryCta"]),
            salesMicrocopy=esc(pkg["salesMicrocopy"]),
        )
        path = os.path.join(BASE, brand_slug, pkg_slug, "page.tsx")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(code)
        print(f"  {brand_slug}/{pkg_slug}/page.tsx")

    # Strategy upgrade page
    s = STRATEGY
    code = TEMPLATE.format(
        brandSlug=brand_slug,
        brandName=brand_info["brandName"],
        verticalOpener=esc(brand_info["verticalOpener"]),
        packageSlug=s["slug"],
        headline=esc(s["headline"][brand_slug]),
        subheadline=esc(s["subheadline"][brand_slug]),
        price=esc(s["price"]),
        deliverables=arr(s["deliverables"]),
        bestFit=arr(s["bestFit"][brand_slug]),
        outcome=esc(s["outcome"]),
        primaryCta="Upgrade the Funnel",
        secondaryCta="See how it works",
        salesMicrocopy=esc(s["salesMicrocopy"]),
    )
    path = os.path.join(BASE, brand_slug, s["slug"], "page.tsx")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(code)
    print(f"  {brand_slug}/{s['slug']}/page.tsx")

print(f"\nGenerated 18 package pages (5 front + 1 upsell) x 3 verticals")
