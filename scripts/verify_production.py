#!/usr/bin/env python3
"""Production deployment verification script.

Standalone script (not pytest) that verifies a live deployment is healthy.

Usage:
    python scripts/verify_production.py [--api-url http://localhost:8000]

Exit codes:
    0 — all critical checks pass
    1 — one or more critical checks failed
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass

try:
    import httpx
except ImportError:
    print("ERROR: httpx is required. Install with: pip install httpx")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Terminal colors
# ---------------------------------------------------------------------------

class Color:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

    @classmethod
    def disable(cls):
        cls.GREEN = cls.RED = cls.YELLOW = cls.CYAN = cls.BOLD = cls.DIM = cls.RESET = ""


# Disable color if not a TTY
if not sys.stdout.isatty():
    Color.disable()

CHECK_MARK = "\u2713"
CROSS_MARK = "\u2717"
WARN_MARK = "\u26A0"


def ok(label: str, detail: str = ""):
    detail_str = f"  {Color.DIM}{detail}{Color.RESET}" if detail else ""
    print(f"  {Color.GREEN}{CHECK_MARK}{Color.RESET}  {label}{detail_str}")


def fail(label: str, detail: str = ""):
    detail_str = f"  {Color.DIM}{detail}{Color.RESET}" if detail else ""
    print(f"  {Color.RED}{CROSS_MARK}{Color.RESET}  {label}{detail_str}")


def warn(label: str, detail: str = ""):
    detail_str = f"  {Color.DIM}{detail}{Color.RESET}" if detail else ""
    print(f"  {Color.YELLOW}{WARN_MARK}{Color.RESET}  {label}{detail_str}")


def section(title: str):
    print(f"\n{Color.BOLD}{Color.CYAN}--- {title} ---{Color.RESET}")


# ---------------------------------------------------------------------------
# Check result tracking
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    name: str
    passed: bool
    critical: bool = True
    detail: str = ""


results: list[CheckResult] = []


def record(name: str, passed: bool, critical: bool = True, detail: str = ""):
    results.append(CheckResult(name=name, passed=passed, critical=critical, detail=detail))
    if passed:
        ok(name, detail)
    elif critical:
        fail(name, detail)
    else:
        warn(name, detail)


# ---------------------------------------------------------------------------
# Check implementations
# ---------------------------------------------------------------------------

def check_api_health(client: httpx.Client, base_url: str):
    """Check 1: Basic API health."""
    section("API Health")
    # Try multiple known health endpoint patterns
    paths = ["/health", "/healthz", "/api/v1/health", "/api/v1/healthz"]
    try:
        for path in paths:
            resp = client.get(f"{base_url}{path}", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                record("API liveness", True, detail=f"status={data.get('status', '?')} via {path}")
                return
        record("API liveness", False, detail=f"No health endpoint responded (tried {', '.join(paths)})")
    except Exception as e:
        record("API liveness", False, detail=str(e))


def check_deep_health(client: httpx.Client, base_url: str):
    """Check 2: Deep health — database, Redis, Celery broker, S3."""
    section("Deep Health")
    try:
        # Try multiple deep health endpoint patterns
        resp = None
        for path in ["/health/deep", "/readyz", "/api/v1/health/deep", "/api/v1/readyz"]:
            resp = client.get(f"{base_url}{path}", timeout=15)
            if resp.status_code == 200:
                break
        if not resp or resp.status_code != 200:
            record("Deep health endpoint", False, detail=f"HTTP {resp.status_code if resp else 'no response'}")
            return

        data = resp.json()
        overall = data.get("status", "unknown")
        record(
            "Deep health overall",
            overall in ("healthy", "ok", "ready"),
            detail=f"status={overall}",
        )

        checks = data.get("checks", {})

        # Handle both formats: {"database": true} and {"database": {"ok": true, "latency_ms": 5}}
        for component in ["database", "redis", "celery_broker"]:
            val = checks.get(component)
            if val is None:
                continue
            if isinstance(val, bool):
                record(component.replace("_", " ").title(), val)
            elif isinstance(val, dict):
                comp_ok = val.get("ok", False)
                comp_latency = val.get("latency_ms", "?")
                record(component.replace("_", " ").title(), comp_ok, detail=f"latency={comp_latency}ms")

        # S3
        s3_check = checks.get("s3")
        if s3_check is None:
            record("S3 storage", True, critical=False, detail="not in health response (skipped)")
        elif isinstance(s3_check, bool):
            record("S3 storage", s3_check, critical=False)
        elif isinstance(s3_check, dict):
            s3_error = s3_check.get("error", "")
            if s3_error == "not_configured":
                record("S3 storage", True, critical=False, detail="not configured (skipped)")
            else:
                s3_latency = s3_check.get("latency_ms", "?")
                record("S3 storage", s3_check.get("ok", False), critical=False, detail=f"latency={s3_latency}ms")

    except Exception as e:
        record("Deep health endpoint", False, detail=str(e))


def check_celery_workers(client: httpx.Client, base_url: str):
    """Check 4: Celery worker ping via subprocess."""
    section("Celery Workers")

    # Try subprocess celery inspect ping
    try:
        result = subprocess.run(
            ["celery", "-A", "workers.celery_app", "inspect", "ping", "--timeout", "5"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=os.environ.get("PROJECT_ROOT", "."),
        )
        if result.returncode == 0 and "pong" in result.stdout.lower():
            # Count responding workers
            pong_count = result.stdout.lower().count("pong")
            record("Celery workers", True, detail=f"{pong_count} worker(s) responding")
        elif result.returncode == 0:
            record("Celery workers", True, critical=False, detail="command succeeded but no pong detected")
        else:
            # Celery inspect might fail if broker is unreachable or no workers
            stderr_snippet = result.stderr[:200] if result.stderr else "no stderr"
            record("Celery workers", False, critical=False, detail=f"exit={result.returncode}: {stderr_snippet}")
    except FileNotFoundError:
        record("Celery workers", False, critical=False, detail="celery CLI not found in PATH")
    except subprocess.TimeoutExpired:
        record("Celery workers", False, critical=False, detail="ping timed out after 15s")
    except Exception as e:
        record("Celery workers", False, critical=False, detail=str(e))


def check_provider_connectivity(client: httpx.Client, base_url: str):
    """Check 5: Provider API key configuration."""
    section("Provider Connectivity")
    try:
        resp = None
        for path in ["/health/providers", "/api/v1/health/providers"]:
            resp = client.get(f"{base_url}{path}", timeout=10)
            if resp.status_code == 200:
                break
        if not resp or resp.status_code != 200:
            record("Provider status endpoint", False, critical=False, detail=f"HTTP {resp.status_code if resp else 'none'} (endpoint may not be deployed yet)")
            return

        data = resp.json()
        configured = data.get("configured", 0)
        total = data.get("total", 0)

        record(
            "Provider keys configured",
            configured > 0,
            critical=False,
            detail=f"{configured}/{total} providers have API keys",
        )

        # Report each provider
        providers = data.get("providers", {})
        configured_list = []
        missing_list = []
        for key, info in providers.items():
            name = info.get("name", key)
            if info.get("configured"):
                configured_list.append(name)
            else:
                missing_list.append(name)

        if configured_list:
            ok("Configured providers", ", ".join(configured_list[:10]))
            if len(configured_list) > 10:
                ok("", f"... and {len(configured_list) - 10} more")

        # Only list critical missing providers
        critical_providers = {"Anthropic (Claude)", "Stripe"}
        critical_missing = [p for p in missing_list if p in critical_providers]
        if critical_missing:
            warn("Missing critical providers", ", ".join(critical_missing))

    except Exception as e:
        record("Provider status", False, critical=False, detail=str(e))


def check_s3_storage():
    """Check 6: S3 upload/download/cleanup if env vars are set."""
    section("S3 Storage (Direct)")

    access_key = os.environ.get("AWS_ACCESS_KEY_ID") or os.environ.get("S3_ACCESS_KEY_ID", "")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY") or os.environ.get("S3_SECRET_ACCESS_KEY", "")
    bucket = os.environ.get("S3_BUCKET", "") or os.environ.get("AWS_S3_BUCKET", "")
    endpoint = os.environ.get("S3_ENDPOINT_URL", "") or os.environ.get("AWS_S3_ENDPOINT_URL", "")

    if not (access_key and secret_key and bucket):
        record("S3 direct test", True, critical=False, detail="S3 env vars not set (skipped)")
        return

    try:
        import boto3
        from botocore.config import Config

        s3_kwargs = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "config": Config(connect_timeout=5, read_timeout=10),
        }
        if endpoint:
            s3_kwargs["endpoint_url"] = endpoint

        s3 = boto3.client("s3", **s3_kwargs)

        # Upload test file
        test_key = f"_verify_production/{uuid.uuid4().hex[:8]}_test.txt"
        test_body = f"verify_production check at {time.time()}"

        s3.put_object(Bucket=bucket, Key=test_key, Body=test_body.encode())
        record("S3 upload", True, detail=f"key={test_key}")

        # Download and verify
        obj = s3.get_object(Bucket=bucket, Key=test_key)
        downloaded = obj["Body"].read().decode()
        content_matches = downloaded == test_body
        record("S3 download", content_matches, detail="content verified" if content_matches else "content mismatch")

        # Cleanup
        s3.delete_object(Bucket=bucket, Key=test_key)
        record("S3 cleanup", True, detail="test object deleted")

    except ImportError:
        record("S3 direct test", False, critical=False, detail="boto3 not installed")
    except Exception as e:
        record("S3 direct test", False, critical=False, detail=str(e))


def check_webhook_url():
    """Check 7: Verify WEBHOOK_BASE_URL is reachable."""
    section("Webhook URL")

    webhook_url = os.environ.get("WEBHOOK_BASE_URL", "")
    if not webhook_url:
        record("Webhook URL", True, critical=False, detail="WEBHOOK_BASE_URL not set (skipped)")
        return

    try:
        with httpx.Client(follow_redirects=True, timeout=10) as client:
            resp = client.get(webhook_url)
            reachable = resp.status_code < 500
            record(
                "Webhook URL reachable",
                reachable,
                critical=False,
                detail=f"HTTP {resp.status_code} from {webhook_url}",
            )
    except Exception as e:
        record("Webhook URL reachable", False, critical=False, detail=f"{webhook_url}: {e}")


def check_event_bus(client: httpx.Client, base_url: str):
    """Check 9: Event bus — verify the API is capable of handling events."""
    section("Event Bus")

    # We verify the event bus indirectly: if the health endpoint works
    # and the database is connected, the event bus can write events.
    # Direct event posting requires auth, so we just verify the system_events
    # table is accessible via the deep health check.
    try:
        resp = None
        for path in ["/health/deep", "/readyz"]:
            resp = client.get(f"{base_url}{path}", timeout=10)
            if resp.status_code == 200:
                break
        if resp and resp.status_code == 200:
            data = resp.json()
            db_val = data.get("checks", {}).get("database")
            db_ok = db_val if isinstance(db_val, bool) else (db_val.get("ok", False) if isinstance(db_val, dict) else False)
            record(
                "Event bus (DB backing)",
                db_ok,
                critical=False,
                detail="database connected, event_bus can write" if db_ok else "database unreachable",
            )
        else:
            record("Event bus", False, critical=False, detail=f"health/deep returned HTTP {resp.status_code}")
    except Exception as e:
        record("Event bus", False, critical=False, detail=str(e))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Verify a live Avatar Revenue OS deployment.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/verify_production.py
  python scripts/verify_production.py --api-url http://localhost:8000
  python scripts/verify_production.py --api-url https://api.mysite.com
        """,
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("API_URL", "http://localhost:8000"),
        help="Base URL for the API (default: $API_URL or http://localhost:8000)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )
    args = parser.parse_args()

    if args.no_color:
        Color.disable()

    base_url = args.api_url.rstrip("/")

    print(f"\n{Color.BOLD}Avatar Revenue OS - Production Verification{Color.RESET}")
    print(f"{Color.DIM}Target: {base_url}{Color.RESET}")
    print(f"{Color.DIM}Time:   {time.strftime('%Y-%m-%d %H:%M:%S %Z')}{Color.RESET}")

    # Create a shared HTTP client
    client = httpx.Client(follow_redirects=True, timeout=15)

    try:
        # Run all checks
        check_api_health(client, base_url)
        check_deep_health(client, base_url)
        check_celery_workers(client, base_url)
        check_provider_connectivity(client, base_url)
        check_s3_storage()
        check_webhook_url()
        check_event_bus(client, base_url)
    finally:
        client.close()

    # ---------------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------------

    section("Summary")

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed_critical = [r for r in results if not r.passed and r.critical]
    failed_non_critical = [r for r in results if not r.passed and not r.critical]

    print(f"\n  Total checks:     {total}")
    print(f"  {Color.GREEN}Passed:           {passed}{Color.RESET}")

    if failed_critical:
        print(f"  {Color.RED}Failed (critical): {len(failed_critical)}{Color.RESET}")
        for r in failed_critical:
            print(f"    {Color.RED}{CROSS_MARK} {r.name}: {r.detail}{Color.RESET}")

    if failed_non_critical:
        print(f"  {Color.YELLOW}Warnings:          {len(failed_non_critical)}{Color.RESET}")
        for r in failed_non_critical:
            print(f"    {Color.YELLOW}{WARN_MARK} {r.name}: {r.detail}{Color.RESET}")

    print()

    if failed_critical:
        print(f"{Color.RED}{Color.BOLD}RESULT: FAILED — {len(failed_critical)} critical check(s) did not pass.{Color.RESET}\n")
        sys.exit(1)
    elif failed_non_critical:
        print(f"{Color.YELLOW}{Color.BOLD}RESULT: PASSED with {len(failed_non_critical)} warning(s).{Color.RESET}\n")
        sys.exit(0)
    else:
        print(f"{Color.GREEN}{Color.BOLD}RESULT: ALL CHECKS PASSED.{Color.RESET}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
