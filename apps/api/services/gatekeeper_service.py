"""AI Gatekeeper service — recompute gates, persist reports, generate alerts."""
from __future__ import annotations

import os
import uuid
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.gatekeeper import (
    GatekeeperAlert,
    GatekeeperAuditLedger,
    GatekeeperCompletionReport,
    GatekeeperContradictionReport,
    GatekeeperDependencyReport,
    GatekeeperExecutionClosureReport,
    GatekeeperExpansionPermission,
    GatekeeperOperatorCommandReport,
    GatekeeperTestReport,
    GatekeeperTruthReport,
)
from packages.scoring.gatekeeper_engine import (
    SYSTEM_MODULES,
    detect_contradictions,
    evaluate_completion,
    evaluate_dependency_readiness,
    evaluate_execution_closure,
    evaluate_expansion_permission,
    evaluate_operator_command_quality,
    evaluate_test_sufficiency,
    evaluate_truth,
    generate_gatekeeper_alerts,
)
from packages.scoring.provider_registry_engine import (
    PROVIDER_INVENTORY,
    check_provider_credentials,
)

# ── Module-layer detection (filesystem probes) ─────────────────────────

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def _file_exists(*parts: str) -> bool:
    return os.path.isfile(os.path.join(_BASE, *parts))

def _dir_exists(*parts: str) -> bool:
    return os.path.isdir(os.path.join(_BASE, *parts))

def _probe_layers(module_name: str) -> dict[str, bool]:
    m = module_name.replace("-", "_")
    return {
        "has_model": (
            _file_exists("packages", "db", "models", f"{m}.py")
            or _file_exists("packages", "db", "models", f"{m.replace('phase_', 'phase')}.py")
        ),
        "has_migration": any(
            _file_exists("packages", "db", "alembic", "versions", f)
            for f in os.listdir(os.path.join(_BASE, "packages", "db", "alembic", "versions"))
            if m.replace("_", "") in f.replace("_", "") or module_name.replace("_", "") in f.replace("_", "")
        ) if _dir_exists("packages", "db", "alembic", "versions") else False,
        "has_engine": (
            _file_exists("packages", "scoring", f"{m}_engine.py")
            or _file_exists("packages", "scoring", f"{m}_engines.py")
            or _file_exists("packages", "scoring", f"{m}.py")
        ),
        "has_service": (
            _file_exists("apps", "api", "services", f"{m}_service.py")
            or _file_exists("apps", "api", "services", f"{m}.py")
        ),
        "has_api": (
            _file_exists("apps", "api", "routers", f"{m}.py")
        ),
        "has_frontend": (
            _dir_exists("apps", "web", "src", "app", "dashboard", m.replace("_", "-"))
            or _dir_exists("apps", "web", "src", "app", "dashboard", module_name.replace("_", "-"))
        ),
        "has_tests": (
            _file_exists("tests", "unit", f"test_{m}.py")
            or _file_exists("tests", "unit", f"test_{m}_engine.py")
            or _file_exists("tests", "unit", f"test_{m}_engines.py")
            or _file_exists("tests", "integration", f"test_{m}_flow.py")
        ),
        "has_docs": any(
            m.replace("_", "") in f.replace("_", "").replace("-", "")
            for f in os.listdir(os.path.join(_BASE, "docs"))
        ) if _dir_exists("docs") else False,
        "has_worker": (
            _dir_exists("workers", f"{m}_worker")
            or _file_exists("workers", f"{m}_worker", "tasks.py")
        ),
    }


# ── Truth status detection ────────────────────────────────────────────

def _detect_truth(module_name: str, layers: dict[str, bool]) -> tuple[str, str]:
    has_real_client = layers.get("has_engine", False) and layers.get("has_service", False)
    if all(layers.get(f"has_{l}", False) for l in ("model", "migration", "engine", "service", "api")):
        actual = "live" if has_real_client else "partial"
    elif layers.get("has_model") and layers.get("has_engine"):
        actual = "partial"
    elif layers.get("has_model"):
        actual = "stubbed"
    else:
        actual = "planned"
    claimed = "live" if layers.get("has_api") and layers.get("has_service") else actual
    return claimed, actual


# ── Recompute functions ───────────────────────────────────────────────

async def recompute_completion(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(delete(GatekeeperCompletionReport).where(GatekeeperCompletionReport.brand_id == brand_id))
    reports: list[dict] = []
    for mod in SYSTEM_MODULES:
        layers = _probe_layers(mod)
        r = evaluate_completion(mod, layers)
        db.add(GatekeeperCompletionReport(brand_id=brand_id, **{k: v for k, v in r.items() if k != "module_name"}, module_name=r["module_name"]))
        reports.append(r)
    await db.flush()
    return {"rows_processed": len(reports), "alerts_generated": sum(1 for r in reports if not r["gate_passed"]), "status": "completed"}


async def recompute_truth(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(delete(GatekeeperTruthReport).where(GatekeeperTruthReport.brand_id == brand_id))
    reports: list[dict] = []
    for mod in SYSTEM_MODULES:
        layers = _probe_layers(mod)
        claimed, actual = _detect_truth(mod, layers)
        r = evaluate_truth(mod, claimed, actual)
        db.add(GatekeeperTruthReport(brand_id=brand_id, module_name=r["module_name"],
            claimed_status=r["claimed_status"], actual_status=r["actual_status"],
            truth_mismatch=r["truth_mismatch"], mislabeled_as_live=r["mislabeled_as_live"],
            synthetic_without_label=r.get("synthetic_without_label", False),
            gate_passed=r["gate_passed"], severity=r["severity"], explanation=r.get("explanation")))
        reports.append(r)
    await db.flush()
    return {"rows_processed": len(reports), "alerts_generated": sum(1 for r in reports if not r["gate_passed"]), "status": "completed"}


async def recompute_execution_closure(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(delete(GatekeeperExecutionClosureReport).where(GatekeeperExecutionClosureReport.brand_id == brand_id))
    reports: list[dict] = []
    for mod in SYSTEM_MODULES:
        layers = _probe_layers(mod)
        has_exec = layers.get("has_service", False) and layers.get("has_api", False)
        has_down = layers.get("has_worker", False) or layers.get("has_frontend", False)
        has_block = layers.get("has_service", False)
        r = evaluate_execution_closure(mod, has_exec, has_down, has_block)
        db.add(GatekeeperExecutionClosureReport(brand_id=brand_id, module_name=r["module_name"],
            has_execution_path=r["has_execution_path"], has_downstream_action=r["has_downstream_action"],
            has_blocker_handling=r["has_blocker_handling"], dead_end_detected=r["dead_end_detected"],
            stale_blocker_detected=r["stale_blocker_detected"], orphaned_recommendation=r["orphaned_recommendation"],
            gate_passed=r["gate_passed"], severity=r["severity"], explanation=r.get("explanation")))
        reports.append(r)
    await db.flush()
    return {"rows_processed": len(reports), "alerts_generated": sum(1 for r in reports if not r["gate_passed"]), "status": "completed"}


async def recompute_tests(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(delete(GatekeeperTestReport).where(GatekeeperTestReport.brand_id == brand_id))
    reports: list[dict] = []
    test_dir = os.path.join(_BASE, "tests")
    for mod in SYSTEM_MODULES:
        m = mod.replace("-", "_")
        unit_count = sum(1 for f in os.listdir(os.path.join(test_dir, "unit")) if m in f.replace("-", "_")) if _dir_exists("tests", "unit") else 0
        integ_count = sum(1 for f in os.listdir(os.path.join(test_dir, "integration")) if m in f.replace("-", "_")) if _dir_exists("tests", "integration") else 0
        has_crit = unit_count > 0 or integ_count > 0
        r = evaluate_test_sufficiency(mod, unit_count, integ_count, has_crit, integ_count > 0)
        db.add(GatekeeperTestReport(brand_id=brand_id, module_name=r["module_name"],
            unit_test_count=r["unit_test_count"], integration_test_count=r["integration_test_count"],
            critical_paths_covered=r["critical_paths_covered"], high_risk_flows_tested=r["high_risk_flows_tested"],
            gate_passed=r["gate_passed"], severity=r["severity"], explanation=r.get("explanation")))
        reports.append(r)
    await db.flush()
    return {"rows_processed": len(reports), "alerts_generated": sum(1 for r in reports if not r["gate_passed"]), "status": "completed"}


async def recompute_dependencies(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(delete(GatekeeperDependencyReport).where(GatekeeperDependencyReport.brand_id == brand_id))
    reports: list[dict] = []
    dep_map = {
        "buffer_distribution": "buffer", "live_execution_phase2": "stripe",
        "creator_revenue": "stripe", "live_execution_phase1": "smtp",
    }
    for mod, pkey in dep_map.items():
        prov = next((p for p in PROVIDER_INVENTORY if p["provider_key"] == pkey), None)
        if prov:
            cred = check_provider_credentials(prov)
            r = evaluate_dependency_readiness(mod, pkey, cred["is_ready"], prov.get("integration_status") == "live")
            db.add(GatekeeperDependencyReport(brand_id=brand_id, module_name=r["module_name"],
                provider_key=r["provider_key"], dependency_met=r["dependency_met"],
                credential_present=r["credential_present"], integration_live=r["integration_live"],
                blocked_by_external=r["blocked_by_external"],
                gate_passed=r["gate_passed"], severity=r["severity"], explanation=r.get("explanation")))
            reports.append(r)
    await db.flush()
    return {"rows_processed": len(reports), "alerts_generated": sum(1 for r in reports if not r["gate_passed"]), "status": "completed"}


async def recompute_contradictions(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(delete(GatekeeperContradictionReport).where(GatekeeperContradictionReport.brand_id == brand_id))
    states: list[dict] = []
    for mod in SYSTEM_MODULES:
        layers = _probe_layers(mod)
        claimed, actual = _detect_truth(mod, layers)
        states.append({"module": mod, "status": actual, "claims": {"capability": mod, "role": "primary" if layers.get("has_api") else "support"}, "depends_on": None})
    contras = detect_contradictions(states)
    for c in contras:
        db.add(GatekeeperContradictionReport(brand_id=brand_id, module_a=c["module_a"],
            module_b=c["module_b"], contradiction_type=c["contradiction_type"],
            description=c["description"], severity=c["severity"], gate_passed=c["gate_passed"]))
    await db.flush()
    return {"rows_processed": len(contras), "alerts_generated": len(contras), "status": "completed"}


async def recompute_operator_commands(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(delete(GatekeeperOperatorCommandReport).where(GatekeeperOperatorCommandReport.brand_id == brand_id))
    sample_commands = [
        ("growth_commander", "Scale YouTube channel to 50k subs by Q3", True, True, True),
        ("copilot", "do something", False, False, False),
        ("scale_alerts", "Add 2 new TikTok accounts for fitness niche", True, True, False),
    ]
    reports: list[dict] = []
    for src, text, target, metric, deadline in sample_commands:
        r = evaluate_operator_command_quality(src, text, target, metric, deadline)
        db.add(GatekeeperOperatorCommandReport(brand_id=brand_id, command_source=r["command_source"],
            command_summary=r["command_summary"], is_actionable=r["is_actionable"],
            is_specific=r["is_specific"], has_measurable_outcome=r["has_measurable_outcome"],
            quality_score=r["quality_score"], gate_passed=r["gate_passed"],
            severity=r["severity"], explanation=r.get("explanation")))
        reports.append(r)
    await db.flush()
    return {"rows_processed": len(reports), "alerts_generated": sum(1 for r in reports if not r["gate_passed"]), "status": "completed"}


async def recompute_expansion_permissions(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(delete(GatekeeperExpansionPermission).where(GatekeeperExpansionPermission.brand_id == brand_id))
    completion_rows = list((await db.execute(select(GatekeeperCompletionReport).where(GatekeeperCompletionReport.brand_id == brand_id))).scalars().all())
    test_rows = list((await db.execute(select(GatekeeperTestReport).where(GatekeeperTestReport.brand_id == brand_id))).scalars().all())
    dep_rows = list((await db.execute(select(GatekeeperDependencyReport).where(GatekeeperDependencyReport.brand_id == brand_id))).scalars().all())
    all_complete = all(r.gate_passed for r in completion_rows) if completion_rows else False
    all_tests = all(r.gate_passed for r in test_rows) if test_rows else False
    all_deps = all(r.gate_passed for r in dep_rows) if dep_rows else True

    from packages.scoring.autonomous_readiness_engine import evaluate_autonomous_readiness
    ar = evaluate_autonomous_readiness()
    critical_gates_passing = ar["fully_autonomous"] or ar["conditions_passing"] >= 8

    targets = ["next_phase", "new_pack", "production_deploy", "fully_autonomous"]
    reports: list[dict] = []
    for t in targets:
        r = evaluate_expansion_permission(t, all_complete, True, all_tests, all_deps, critical_gates_passing)
        db.add(GatekeeperExpansionPermission(brand_id=brand_id, expansion_target=r["expansion_target"],
            prerequisites_met=r["prerequisites_met"], blockers_resolved=r["blockers_resolved"],
            test_coverage_sufficient=r["test_coverage_sufficient"], dependencies_ready=r["dependencies_ready"],
            permission_granted=r["permission_granted"], blocking_reasons=r["blocking_reasons"],
            severity=r["severity"], explanation=r.get("explanation")))
        reports.append(r)
    await db.flush()
    return {"rows_processed": len(reports), "alerts_generated": sum(1 for r in reports if not r["permission_granted"]), "status": "completed"}


async def recompute_alerts(db: AsyncSession, brand_id: uuid.UUID) -> int:
    await db.execute(update(GatekeeperAlert).where(GatekeeperAlert.brand_id == brand_id, GatekeeperAlert.is_active.is_(True)).values(is_active=False))
    comp = [{"gate_passed": r.gate_passed, "module_name": r.module_name, "severity": r.severity, "explanation": r.explanation, "missing_layers": r.missing_layers} for r in (await db.execute(select(GatekeeperCompletionReport).where(GatekeeperCompletionReport.brand_id == brand_id))).scalars().all()]
    truth = [{"gate_passed": r.gate_passed, "module_name": r.module_name, "severity": r.severity, "explanation": r.explanation} for r in (await db.execute(select(GatekeeperTruthReport).where(GatekeeperTruthReport.brand_id == brand_id))).scalars().all()]
    closure = [{"gate_passed": r.gate_passed, "module_name": r.module_name, "severity": r.severity, "explanation": r.explanation} for r in (await db.execute(select(GatekeeperExecutionClosureReport).where(GatekeeperExecutionClosureReport.brand_id == brand_id))).scalars().all()]
    tests = [{"gate_passed": r.gate_passed, "module_name": r.module_name, "severity": r.severity, "explanation": r.explanation} for r in (await db.execute(select(GatekeeperTestReport).where(GatekeeperTestReport.brand_id == brand_id))).scalars().all()]
    deps = [{"gate_passed": r.gate_passed, "module_name": r.module_name, "provider_key": r.provider_key, "severity": r.severity, "explanation": r.explanation} for r in (await db.execute(select(GatekeeperDependencyReport).where(GatekeeperDependencyReport.brand_id == brand_id))).scalars().all()]
    contras = [{"module_a": r.module_a, "module_b": r.module_b, "description": r.description, "severity": r.severity} for r in (await db.execute(select(GatekeeperContradictionReport).where(GatekeeperContradictionReport.brand_id == brand_id))).scalars().all()]
    alerts = generate_gatekeeper_alerts(comp, truth, closure, tests, deps, contras)
    for a in alerts:
        db.add(GatekeeperAlert(brand_id=brand_id, **a))

    from packages.db.models.scale_alerts import OperatorAlert
    critical_alerts = [a for a in alerts if a.get("severity") in ("critical", "high")]
    for ca in critical_alerts[:10]:
        db.add(OperatorAlert(
            brand_id=brand_id,
            alert_type=f"gatekeeper_{ca.get('gate_type', 'unknown')}",
            title=ca.get("title", "Gatekeeper alert")[:500],
            summary=ca.get("description", "")[:500],
            explanation=ca.get("description"),
            recommended_action=ca.get("operator_action", "Review gatekeeper dashboard"),
            confidence=0.9,
            urgency=90.0 if ca.get("severity") == "critical" else 70.0,
        ))

    await db.flush()
    return len(alerts)


# ── List functions ────────────────────────────────────────────────────

async def list_completion(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(GatekeeperCompletionReport).where(GatekeeperCompletionReport.brand_id == brand_id).order_by(GatekeeperCompletionReport.created_at.desc()))).scalars().all())

async def list_truth(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(GatekeeperTruthReport).where(GatekeeperTruthReport.brand_id == brand_id).order_by(GatekeeperTruthReport.created_at.desc()))).scalars().all())

async def list_execution_closure(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(GatekeeperExecutionClosureReport).where(GatekeeperExecutionClosureReport.brand_id == brand_id).order_by(GatekeeperExecutionClosureReport.created_at.desc()))).scalars().all())

async def list_tests(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(GatekeeperTestReport).where(GatekeeperTestReport.brand_id == brand_id).order_by(GatekeeperTestReport.created_at.desc()))).scalars().all())

async def list_dependencies(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(GatekeeperDependencyReport).where(GatekeeperDependencyReport.brand_id == brand_id).order_by(GatekeeperDependencyReport.created_at.desc()))).scalars().all())

async def list_contradictions(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(GatekeeperContradictionReport).where(GatekeeperContradictionReport.brand_id == brand_id).order_by(GatekeeperContradictionReport.created_at.desc()))).scalars().all())

async def list_operator_commands(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(GatekeeperOperatorCommandReport).where(GatekeeperOperatorCommandReport.brand_id == brand_id).order_by(GatekeeperOperatorCommandReport.created_at.desc()))).scalars().all())

async def list_expansion_permissions(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(GatekeeperExpansionPermission).where(GatekeeperExpansionPermission.brand_id == brand_id).order_by(GatekeeperExpansionPermission.created_at.desc()))).scalars().all())

async def list_alerts(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(GatekeeperAlert).where(GatekeeperAlert.brand_id == brand_id, GatekeeperAlert.is_active.is_(True)).order_by(GatekeeperAlert.created_at.desc()))).scalars().all())

async def list_audit_ledger(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(GatekeeperAuditLedger).where(GatekeeperAuditLedger.brand_id == brand_id).order_by(GatekeeperAuditLedger.created_at.desc()).limit(200))).scalars().all())
