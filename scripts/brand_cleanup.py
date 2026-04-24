#!/usr/bin/env python3
"""Controlled brand cleanup + activation-prep pass.

This script:
  STEP 1: Archives 4 brands safely (is_active=false) — preserves all FK data.
  STEP 2: Builds a full FK-reference dependency snapshot for 6 delete candidates
          across every table with a brand_id foreign key.
  STEP 3: Classifies each delete candidate as:
            SAFE_TO_DELETE       — zero references anywhere
            SHOULD_ARCHIVE_INSTEAD — has low-risk noise references (auto-generated)
            BLOCKED_FROM_DELETE  — has meaningful references that must be preserved
  STEP 4: Hard-deletes ONLY brands classified SAFE_TO_DELETE.
          Any ambiguity → kept + marked archive.
  STEP 5: Writes a JSON artifact to /tmp/brand_cleanup_report.json for audit.

Usage:
  docker exec aro-api python scripts/brand_cleanup.py            # dry-run
  docker exec aro-api python scripts/brand_cleanup.py --apply    # apply archive
  docker exec aro-api python scripts/brand_cleanup.py --apply --delete-safe
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/app")

# ── Target brands (by slug) ─────────────────────────────────────────────

ARCHIVE_SLUGS = {
    "v2b",
    "my-test-brand-e87695",
    "deploy-proof",
    "wire-audit-brand",
}

DELETE_CANDIDATE_SLUGS = {
    "audit-brand",
    "cascade-brand",
    "ep2b-test",  # (two duplicate brands share this slug)
    "revenue-machine",
    "handoff-brand-62f67c",
}

LIVE_SLUGS = {
    "aesthetic-theory",
    "tool-signal",
    "velvet-wire",
    "body-theory",
    "ai-finance-pro",
}

# Whitelist of tables where a FK reference represents REAL user/operator work.
# If a brand has rows in ANY of these, it is BLOCKED_FROM_DELETE.
# Everything else (trend signals, brain decisions, gatekeeper reports, agent
# runs, etc.) is worker-generated noise that does not represent real work.
MEANINGFUL_TABLES = {
    # Content pipeline
    "content_items",
    "content_briefs",
    "scripts",
    "script_variants",
    "media_jobs",
    "assets",
    # Quality
    "qa_reports",
    "approvals",
    "similarity_reports",
    # Publishing
    "publish_jobs",
    "buffer_publish_jobs",
    "buffer_publish_attempts",
    "buffer_profiles",
    # Accounts / brand identity
    "creator_accounts",
    "creator_platform_accounts",
    "avatars",
    "avatar_provider_profiles",
    "voice_provider_profiles",
    "ai_personalities",
    # Monetization / offers
    "offers",
    "sponsor_profiles",
    "sponsor_opportunities",
    "affiliate_network_accounts",
    "af_links",
    "af_offers",
    # Revenue / performance (real measured data)
    "performance_metrics",
    "attribution_events",
    "revenue_ledger_entries",
    "creator_revenue_events",
    # Experiments (real user-initiated tests)
    "experiments",
    "experiment_variants",
    # GM strategy sessions
    "gm_sessions",
    "gm_blueprints",
}


def _collect_fk_tables(conn) -> list[str]:
    """Find every table that has a FK constraint pointing at brands.id."""
    from sqlalchemy import text

    rows = conn.execute(
        text(
            """
        SELECT DISTINCT tc.table_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND ccu.table_name = 'brands'
          AND ccu.column_name = 'id'
        ORDER BY tc.table_name
        """
        )
    ).fetchall()
    return [r[0] for r in rows]


def _count_refs_in_table(conn, table: str, brand_id: str) -> int:
    from sqlalchemy import text

    try:
        return int(
            conn.execute(
                text(f'SELECT COUNT(*) FROM "{table}" WHERE brand_id = :bid'),
                {"bid": brand_id},
            ).scalar()
            or 0
        )
    except Exception:
        return -1  # column may not be brand_id in all tables


def _snapshot_brand(conn, brand_id: str, name: str, slug: str, fk_tables: list[str]) -> dict:
    """Count references for a single brand across every FK table."""
    from sqlalchemy import text

    meta = conn.execute(
        text("SELECT name, slug, is_active, created_at, updated_at FROM brands WHERE id = :bid"),
        {"bid": brand_id},
    ).fetchone()
    if not meta:
        return {"error": "brand_not_found", "id": brand_id}

    refs: dict[str, int] = {}
    total_meaningful = 0
    total_noise = 0
    meaningful_breakdown: dict[str, int] = {}

    for table in fk_tables:
        count = _count_refs_in_table(conn, table, brand_id)
        if count == -1:
            continue
        if count > 0:
            refs[table] = count
            if table in MEANINGFUL_TABLES:
                total_meaningful += count
                meaningful_breakdown[table] = count
            else:
                total_noise += count

    # Specific meaningful-content counts (shown even if zero, for clarity)
    key_tables = [
        "content_items",
        "content_briefs",
        "scripts",
        "media_jobs",
        "publish_jobs",
        "buffer_publish_jobs",
        "buffer_profiles",
        "creator_accounts",
        "avatars",
        "offers",
        "qa_reports",
        "approvals",
        "performance_metrics",
        "experiments",
    ]
    key_counts = {t: refs.get(t, 0) for t in key_tables}

    # Real publish proof
    real_publishes = int(
        conn.execute(
            text("SELECT COUNT(*) FROM publish_jobs WHERE brand_id = :bid AND platform_post_url LIKE 'https://%'"),
            {"bid": brand_id},
        ).scalar()
        or 0
    )

    return {
        "brand_id": brand_id,
        "name": meta[0],
        "slug": meta[1],
        "is_active": bool(meta[2]),
        "created_at": meta[3].isoformat() if meta[3] else None,
        "updated_at": meta[4].isoformat() if meta[4] else None,
        "total_tables_with_refs": len(refs),
        "total_meaningful_refs": total_meaningful,
        "total_noise_refs": total_noise,
        "real_publishes_with_platform_url": real_publishes,
        "key_counts": key_counts,
        "meaningful_breakdown": meaningful_breakdown,
        "all_refs": refs,
    }


def _classify(snapshot: dict) -> str:
    """Classify a snapshot into SAFE_TO_DELETE / SHOULD_ARCHIVE_INSTEAD / BLOCKED."""
    if snapshot.get("real_publishes_with_platform_url", 0) > 0:
        return "BLOCKED_FROM_DELETE"
    if snapshot.get("total_meaningful_refs", 0) > 0:
        return "BLOCKED_FROM_DELETE"
    if snapshot.get("total_noise_refs", 0) > 0:
        return "SHOULD_ARCHIVE_INSTEAD"
    return "SAFE_TO_DELETE"


def _archive_brands(conn, slugs: set[str], apply: bool) -> list[dict]:
    """Set is_active=false on each brand with a matching slug."""
    from sqlalchemy import text

    results = []
    for slug in slugs:
        rows = conn.execute(
            text("SELECT id, name, is_active FROM brands WHERE slug = :s"),
            {"s": slug},
        ).fetchall()
        for r in rows:
            brand_id, name, is_active = str(r[0]), r[1], bool(r[2])
            action = "NO_CHANGE" if not is_active else ("WILL_ARCHIVE" if not apply else "ARCHIVED")
            if apply and is_active:
                conn.execute(
                    text("UPDATE brands SET is_active = false, updated_at = NOW() WHERE id = :bid"),
                    {"bid": brand_id},
                )
            results.append(
                {"brand_id": brand_id, "name": name, "slug": slug, "was_active": is_active, "action": action}
            )
    return results


def _delete_brand(conn, brand_id: str) -> bool:
    """Hard-delete a brand by id. Used only for SAFE_TO_DELETE classifications."""
    from sqlalchemy import text

    result = conn.execute(
        text("DELETE FROM brands WHERE id = :bid"),
        {"bid": brand_id},
    )
    return result.rowcount > 0


def main(apply: bool, delete_safe: bool):
    import os

    from sqlalchemy import create_engine, text

    engine = create_engine(os.environ.get("DATABASE_URL_SYNC", ""), pool_size=2)

    report: dict = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "apply": apply,
        "delete_safe": delete_safe,
        "live_brands": [],
        "archive_operations": [],
        "delete_candidate_snapshots": [],
        "deletes_performed": [],
        "deletes_skipped": [],
        "verification": {},
    }

    with engine.connect() as conn:
        # ── Pre-verify live brands intact ─────────────────────────
        print("=" * 75)
        print("  PRE-CHECK: Live brand inventory")
        print("=" * 75)
        for slug in sorted(LIVE_SLUGS):
            row = conn.execute(
                text("SELECT id, name, is_active FROM brands WHERE slug = :s"),
                {"s": slug},
            ).fetchone()
            if row:
                bp_count = conn.execute(
                    text("SELECT COUNT(*) FROM buffer_profiles WHERE brand_id = :bid"),
                    {"bid": str(row[0])},
                ).scalar()
                real_pubs = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM publish_jobs WHERE brand_id = :bid AND platform_post_url LIKE 'https://%'"
                    ),
                    {"bid": str(row[0])},
                ).scalar()
                entry = {
                    "slug": slug,
                    "name": row[1],
                    "is_active": bool(row[2]),
                    "buffer_profiles": int(bp_count or 0),
                    "real_publishes": int(real_pubs or 0),
                }
                report["live_brands"].append(entry)
                print(f"  [OK] {row[1]:25s} slug={slug:20s} buffer={bp_count} real_pubs={real_pubs} active={row[2]}")
            else:
                print(f"  [MISSING] {slug}")

        # ── STEP 1: Archive ───────────────────────────────────────
        print()
        print("=" * 75)
        print(f"  STEP 1: ARCHIVE BRANDS  (apply={apply})")
        print("=" * 75)
        archive_results = _archive_brands(conn, ARCHIVE_SLUGS, apply=apply)
        report["archive_operations"] = archive_results
        for r in archive_results:
            print(f"  [{r['action']:14s}] {r['name']:25s} slug={r['slug']:25s} was_active={r['was_active']}")
        if apply:
            conn.commit()

        # ── STEP 2: Dependency snapshot ───────────────────────────
        print()
        print("=" * 75)
        print("  STEP 2: DEPENDENCY SNAPSHOT — delete candidates")
        print("=" * 75)
        fk_tables = _collect_fk_tables(conn)
        print(f"  Scanning {len(fk_tables)} FK tables per candidate...")
        print()

        # Collect ALL rows matching delete candidate slugs (handles duplicate ep2b-test)
        candidate_rows = conn.execute(
            text("SELECT id, name, slug FROM brands WHERE slug = ANY(:slugs) ORDER BY slug, created_at"),
            {"slugs": list(DELETE_CANDIDATE_SLUGS)},
        ).fetchall()

        for row in candidate_rows:
            brand_id, name, slug = str(row[0]), row[1], row[2]
            snap = _snapshot_brand(conn, brand_id, name, slug, fk_tables)
            classification = _classify(snap)
            snap["classification"] = classification
            report["delete_candidate_snapshots"].append(snap)

            print(f"  [{classification:22s}] {name:25s} slug={slug:25s}")
            print(f"    brand_id={brand_id}")
            print(f"    tables with refs: {snap['total_tables_with_refs']}")
            print(f"    meaningful refs:  {snap['total_meaningful_refs']}")
            print(f"    noise refs:       {snap['total_noise_refs']}")
            print(f"    real publishes:   {snap['real_publishes_with_platform_url']}")
            non_zero_keys = {k: v for k, v in snap["key_counts"].items() if v > 0}
            if non_zero_keys:
                print(f"    key counts:       {non_zero_keys}")
            print()

        # ── STEP 3: Auto-archive any BLOCKED_FROM_DELETE or SHOULD_ARCHIVE_INSTEAD
        # delete-candidates (preservation-first policy)
        print()
        print("=" * 75)
        print(f"  STEP 3: ARCHIVE NON-SAFE DELETE CANDIDATES  (apply={apply})")
        print("=" * 75)
        report["candidate_archive_operations"] = []
        for snap in report["delete_candidate_snapshots"]:
            if snap["classification"] in ("BLOCKED_FROM_DELETE", "SHOULD_ARCHIVE_INSTEAD"):
                if snap["is_active"]:
                    if apply:
                        conn.execute(
                            text("UPDATE brands SET is_active = false, updated_at = NOW() WHERE id = :bid"),
                            {"bid": snap["brand_id"]},
                        )
                        action = "ARCHIVED"
                    else:
                        action = "WILL_ARCHIVE"
                else:
                    action = "NO_CHANGE"
                entry = {
                    "brand_id": snap["brand_id"],
                    "name": snap["name"],
                    "slug": snap["slug"],
                    "was_active": snap["is_active"],
                    "classification": snap["classification"],
                    "action": action,
                    "reason": f"{snap['total_meaningful_refs']} meaningful refs, {snap['real_publishes_with_platform_url']} real publishes",
                }
                report["candidate_archive_operations"].append(entry)
                print(f"  [{action:14s}] {snap['name']:25s} slug={snap['slug']:25s} class={snap['classification']}")
        if apply:
            conn.commit()

        # ── STEP 4: Safe delete ONLY for SAFE_TO_DELETE ───────────
        print()
        print("=" * 75)
        print(f"  STEP 4: SAFE DELETE  (delete_safe={delete_safe})")
        print("=" * 75)
        for snap in report["delete_candidate_snapshots"]:
            if snap["classification"] == "SAFE_TO_DELETE":
                if delete_safe and apply:
                    try:
                        ok = _delete_brand(conn, snap["brand_id"])
                        report["deletes_performed"].append(
                            {
                                "brand_id": snap["brand_id"],
                                "name": snap["name"],
                                "slug": snap["slug"],
                                "success": ok,
                            }
                        )
                        print(f"  [DELETED]  {snap['name']} ({snap['slug']}) id={snap['brand_id']}")
                    except Exception as e:
                        report["deletes_skipped"].append(
                            {
                                "brand_id": snap["brand_id"],
                                "name": snap["name"],
                                "reason": f"delete_error: {e}",
                            }
                        )
                        print(f"  [DELETE_ERROR] {snap['name']}: {e}")
                else:
                    report["deletes_skipped"].append(
                        {
                            "brand_id": snap["brand_id"],
                            "name": snap["name"],
                            "reason": "dry_run_or_delete_flag_not_set",
                        }
                    )
                    print(f"  [WOULD_DELETE] {snap['name']} ({snap['slug']}) - pass --apply --delete-safe to execute")
            else:
                report["deletes_skipped"].append(
                    {
                        "brand_id": snap["brand_id"],
                        "name": snap["name"],
                        "reason": snap["classification"],
                    }
                )
                print(f"  [KEPT]     {snap['name']} ({snap['slug']}) - {snap['classification']}")

        if apply and delete_safe:
            conn.commit()

        # ── Post-verify live brands unchanged ─────────────────────
        print()
        print("=" * 75)
        print("  POST-VERIFICATION: Live brands + AI Finance Pro proof intact")
        print("=" * 75)
        verification = {}
        for slug in sorted(LIVE_SLUGS):
            row = conn.execute(
                text("SELECT id, name, is_active FROM brands WHERE slug = :s"),
                {"s": slug},
            ).fetchone()
            if not row:
                print(f"  [MISSING] {slug}")
                verification[slug] = {"status": "MISSING"}
                continue

            bp = conn.execute(
                text("SELECT COUNT(*) FROM buffer_profiles WHERE brand_id = :bid"),
                {"bid": str(row[0])},
            ).scalar()
            real_pubs = conn.execute(
                text("SELECT COUNT(*) FROM publish_jobs WHERE brand_id = :bid AND platform_post_url LIKE 'https://%'"),
                {"bid": str(row[0])},
            ).scalar()
            verification[slug] = {
                "present": True,
                "is_active": bool(row[2]),
                "buffer_profiles": int(bp or 0),
                "real_publishes": int(real_pubs or 0),
            }
            ok = row[2] and (bp or real_pubs >= 0)
            tag = "INTACT" if ok else "WARNING"
            print(f"  [{tag}] {row[1]:25s} active={row[2]} buffer={bp} real_pubs={real_pubs}")
        report["verification"] = verification

    # ── Write JSON artifact ───────────────────────────────────────────
    out_path = Path("/tmp/brand_cleanup_report.json")
    out_path.write_text(json.dumps(report, indent=2, default=str))
    print()
    print(f"  Report artifact: {out_path}")

    # ── Operator summary ──────────────────────────────────────────────
    print()
    print("=" * 75)
    print("  OPERATOR SUMMARY")
    print("=" * 75)
    live = [b for b in report["live_brands"] if b["is_active"]]
    print(f"  LIVE:        {len(live)}  {[b['slug'] for b in live]}")
    archived_now = [r for r in report["archive_operations"] if r["action"] == "ARCHIVED"]
    already_archived = [r for r in report["archive_operations"] if r["action"] == "NO_CHANGE"]
    would_archive = [r for r in report["archive_operations"] if r["action"] == "WILL_ARCHIVE"]
    if apply:
        print(f"  ARCHIVED:    {len(archived_now)} this run, {len(already_archived)} already archived")
    else:
        print(f"  WILL ARCHIVE: {len(would_archive)} (dry-run)")
    safe = [s for s in report["delete_candidate_snapshots"] if s["classification"] == "SAFE_TO_DELETE"]
    should_arch = [s for s in report["delete_candidate_snapshots"] if s["classification"] == "SHOULD_ARCHIVE_INSTEAD"]
    blocked = [s for s in report["delete_candidate_snapshots"] if s["classification"] == "BLOCKED_FROM_DELETE"]
    print(f"  SAFE_TO_DELETE:        {len(safe)}  {[s['slug'] for s in safe]}")
    print(f"  SHOULD_ARCHIVE_INSTEAD: {len(should_arch)}  {[s['slug'] for s in should_arch]}")
    print(f"  BLOCKED_FROM_DELETE:   {len(blocked)}  {[s['slug'] for s in blocked]}")
    print(f"  DELETES_PERFORMED:     {len(report['deletes_performed'])}")
    print("=" * 75)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually apply archive operations (dry-run by default)",
    )
    parser.add_argument(
        "--delete-safe",
        action="store_true",
        help="Hard-delete brands classified SAFE_TO_DELETE (requires --apply)",
    )
    args = parser.parse_args()
    main(apply=args.apply, delete_safe=args.delete_safe)
