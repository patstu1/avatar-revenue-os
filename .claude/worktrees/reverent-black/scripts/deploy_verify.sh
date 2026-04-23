#!/bin/bash
# Deploy verification — single command to check the health of a deployed instance.
# Usage: bash scripts/deploy_verify.sh
#
# Checks: git SHA, alembic version, container health, public health, worker summary.
# Exit 0 = all critical checks pass. Exit 1 = something is wrong.
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

PASS=0
FAIL=0
WARN=0

ok()   { PASS=$((PASS+1)); echo -e "  ${GREEN}✓${NC}  $1  ${CYAN}$2${NC}"; }
fail() { FAIL=$((FAIL+1)); echo -e "  ${RED}✗${NC}  $1  ${RED}$2${NC}"; }
warn() { WARN=$((WARN+1)); echo -e "  ${YELLOW}⚠${NC}  $1  ${YELLOW}$2${NC}"; }

echo ""
echo -e "${BOLD}Avatar Revenue OS — Deploy Verification${NC}"
echo -e "Time: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo ""

# ── 1. Git SHA ──────────────────────────────────────────────────────────
echo -e "${BOLD}${CYAN}--- Git State ---${NC}"
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
GIT_DIRTY=$(git status --porcelain 2>/dev/null | head -5)
ok "Git SHA" "$GIT_SHA ($GIT_BRANCH)"
if [ -n "$GIT_DIRTY" ]; then
    warn "Working tree" "has uncommitted changes"
else
    ok "Working tree" "clean"
fi

# ── 2. Alembic Migration Version ───────────────────────────────────────
echo -e "\n${BOLD}${CYAN}--- Database Migrations ---${NC}"
ALEMBIC_HEAD=$(docker compose exec -T postgres psql -U "${POSTGRES_USER:-avataros}" -d "${POSTGRES_DB:-avatar_revenue_os}" -t -c "SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1;" 2>/dev/null | tr -d ' \n' || echo "unreachable")
if [ "$ALEMBIC_HEAD" = "unreachable" ] || [ -z "$ALEMBIC_HEAD" ]; then
    fail "Alembic version" "could not read alembic_version table"
else
    ok "Alembic version" "$ALEMBIC_HEAD"
fi

# Check expected head
EXPECTED_HEAD="005_media_jobs_v2"
if [ "$ALEMBIC_HEAD" = "$EXPECTED_HEAD" ]; then
    ok "Migration at expected head" "$EXPECTED_HEAD"
else
    warn "Migration version mismatch" "expected=$EXPECTED_HEAD actual=$ALEMBIC_HEAD"
fi

# ── 3. Container Health ────────────────────────────────────────────────
echo -e "\n${BOLD}${CYAN}--- Container Health ---${NC}"
CONTAINERS="aro-postgres aro-redis aro-api aro-worker-generation aro-worker-publishing aro-worker-analytics aro-worker-outreach aro-worker-default aro-scheduler aro-web aro-caddy"
for CONTAINER in $CONTAINERS; do
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null || echo "not_found")
    RUNNING=$(docker inspect --format='{{.State.Status}}' "$CONTAINER" 2>/dev/null || echo "not_found")
    if [ "$STATUS" = "healthy" ]; then
        ok "$CONTAINER" "healthy"
    elif [ "$RUNNING" = "running" ] && [ "$STATUS" = "starting" ]; then
        warn "$CONTAINER" "starting (not yet healthy)"
    elif [ "$RUNNING" = "running" ]; then
        warn "$CONTAINER" "running (health=$STATUS)"
    elif [ "$STATUS" = "not_found" ]; then
        fail "$CONTAINER" "not found"
    else
        fail "$CONTAINER" "status=$RUNNING health=$STATUS"
    fi
done

# ── 4. Public Health Endpoint ──────────────────────────────────────────
echo -e "\n${BOLD}${CYAN}--- Public Health ---${NC}"
API_URL="${API_URL:-http://localhost:8000}"
for ENDPOINT in "/health" "/readyz" "/health/deep"; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${API_URL}${ENDPOINT}" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        ok "GET ${ENDPOINT}" "HTTP $HTTP_CODE"
    elif [ "$HTTP_CODE" = "000" ]; then
        fail "GET ${ENDPOINT}" "connection refused"
    else
        warn "GET ${ENDPOINT}" "HTTP $HTTP_CODE"
    fi
done

# ── 5. Worker Health Summary ──────────────────────────────────────────
echo -e "\n${BOLD}${CYAN}--- Worker Summary ---${NC}"
WORKER_CONTAINERS="aro-worker-generation aro-worker-publishing aro-worker-analytics aro-worker-outreach aro-worker-default"
for WC in $WORKER_CONTAINERS; do
    RESTARTS=$(docker inspect --format='{{.RestartCount}}' "$WC" 2>/dev/null || echo "?")
    MEM_USAGE=$(docker stats --no-stream --format "{{.MemUsage}}" "$WC" 2>/dev/null || echo "?")
    MEM_PCT=$(docker stats --no-stream --format "{{.MemPerc}}" "$WC" 2>/dev/null || echo "?")
    if [ "$RESTARTS" != "?" ] && [ "$RESTARTS" -gt 3 ] 2>/dev/null; then
        warn "$WC" "restarts=$RESTARTS mem=$MEM_USAGE ($MEM_PCT)"
    elif [ "$RESTARTS" != "?" ]; then
        ok "$WC" "restarts=$RESTARTS mem=$MEM_USAGE ($MEM_PCT)"
    else
        warn "$WC" "stats unavailable"
    fi
done

# ── Summary ───────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}--- Summary ---${NC}"
echo -e "  Passed:   ${GREEN}$PASS${NC}"
echo -e "  Warnings: ${YELLOW}$WARN${NC}"
echo -e "  Failed:   ${RED}$FAIL${NC}"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}${BOLD}RESULT: FAILED — $FAIL critical check(s) did not pass.${NC}"
    exit 1
elif [ "$WARN" -gt 0 ]; then
    echo -e "${YELLOW}${BOLD}RESULT: PASSED with $WARN warning(s).${NC}"
    exit 0
else
    echo -e "${GREEN}${BOLD}RESULT: ALL CHECKS PASSED.${NC}"
    exit 0
fi
