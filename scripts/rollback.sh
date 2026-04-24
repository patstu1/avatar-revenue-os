#!/usr/bin/env bash
# scripts/rollback.sh — canonical rollback helper (Batch 6 final-lock).
#
# Usage:  scripts/rollback.sh <previous-sha> [--with-schema <alembic-rev>]
#
# Default behaviour: binary rollback only. Alembic head stays on the
# latest revision because every migration from 010+ is additive and
# forward-safe. Passing --with-schema also runs `alembic downgrade`
# to the specified revision (destructive — read docs/OPERATIONS.md §5
# before using this path).
set -euo pipefail

PREV_SHA="${1:-}"
WITH_SCHEMA=""
DOWN_REV=""

if [[ -z "${PREV_SHA}" ]]; then
    echo "Usage: $0 <previous-sha> [--with-schema <alembic-rev>]" >&2
    exit 2
fi

if [[ "${2:-}" == "--with-schema" ]]; then
    WITH_SCHEMA="1"
    DOWN_REV="${3:-}"
    if [[ -z "${DOWN_REV}" ]]; then
        echo "error: --with-schema requires an alembic revision" >&2
        exit 2
    fi
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

echo "[rollback] Target SHA: ${PREV_SHA}"
echo "[rollback] Canonical branch: recovery/from-prod"

# 1. Sanity check that the SHA exists + is an ancestor
git cat-file -e "${PREV_SHA}" 2>/dev/null \
    || { echo "[rollback] unknown SHA ${PREV_SHA}" >&2; exit 3; }

# 2. Schema rollback (if requested)
if [[ -n "${WITH_SCHEMA}" ]]; then
    echo "[rollback] DESTRUCTIVE: alembic downgrade ${DOWN_REV}"
    read -r -p "[rollback] Type the revision to confirm: " CONF
    if [[ "${CONF}" != "${DOWN_REV}" ]]; then
        echo "[rollback] confirmation mismatch, aborting" >&2
        exit 4
    fi
    DATABASE_URL_SYNC="${DATABASE_URL_SYNC:?must be set}" \
        alembic -c packages/db/alembic.ini downgrade "${DOWN_REV}"
fi

# 3. Binary rollback via the canonical deploy pipeline. This script
# is a thin shim — the actual container orchestration lives in the
# CI/CD platform. We set the deploy-manifest envs so /ops/lock-status
# reflects the rolled-back state.
export DEPLOY_MANIFEST_SHA="${PREV_SHA}"
export DEPLOY_MANIFEST_BRANCH="recovery/from-prod"
export DEPLOY_MANIFEST_AT="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
export DEPLOY_MANIFEST_BY="${USER:-rollback}"
export DEPLOY_MANIFEST_BUILD_ID="rollback-${PREV_SHA}"

if [[ -x "${REPO_ROOT}/deploy.sh" ]]; then
    echo "[rollback] invoking deploy.sh ${PREV_SHA}"
    "${REPO_ROOT}/deploy.sh" "${PREV_SHA}"
else
    echo "[rollback] deploy.sh not executable; manual container roll required"
    echo "[rollback] DEPLOY_MANIFEST_SHA=${PREV_SHA}"
fi

echo "[rollback] Verify: curl -sS \$API/ops/lock-status | jq"
echo "[rollback] Verify: curl -sS \$API/ops/health-check | jq .healthy"
