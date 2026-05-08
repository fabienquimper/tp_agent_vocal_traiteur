#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# promote.sh — Promouvoir staging → production
# Étape 06 : Staging vs Production
#
# Workflow :
#   1. Vérifie que staging est sain (health check)
#   2. Lance les tests smoke + quality gate contre staging
#   3. Si tout est vert → copie data-staging/ → data/
#   4. Déclenche un rebuild de l'index production (avec quality gate)
#   5. Attend la fin du rebuild et vérifie le résultat
#
# Usage :
#   bash scripts/promote.sh
#   make promote
#
# Variables d'environnement :
#   STAGING_URL    = http://localhost:8100
#   PRODUCTION_URL = http://localhost:8000
#   SKIP_TESTS     = 1 (désactive les tests — déconseillé en production)
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

STAGING_URL="${STAGING_URL:-http://localhost:8100}"
PRODUCTION_URL="${PRODUCTION_URL:-http://localhost:8000}"
SKIP_TESTS="${SKIP_TESTS:-0}"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}!${NC} $*"; }
fail() { echo -e "${RED}✗${NC} $*"; exit 1; }

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  Promotion Staging → Production"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "  Staging    : $STAGING_URL"
echo "  Production : $PRODUCTION_URL"
echo ""

# ── Étape 1 : Health checks ───────────────────────────────────────────────────
echo "── Étape 1/5 : Vérification des environnements..."

STAGING_STATUS=$(curl -sf "$STAGING_URL/health" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "unreachable")
if [ "$STAGING_STATUS" != "ok" ]; then
    fail "Staging non disponible ($STAGING_STATUS). Lancez : make staging-up"
fi
ok "Staging est opérationnel"

PROD_STATUS=$(curl -sf "$PRODUCTION_URL/health" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "unreachable")
if [ "$PROD_STATUS" != "ok" ]; then
    fail "Production non disponible ($PROD_STATUS). Lancez : make up"
fi
ok "Production est opérationnelle"

# ── Étape 2 : Vérification que staging utilise bien les données staging ───────
echo ""
echo "── Étape 2/5 : Vérification des données staging..."

STAGING_CHECK=$(curl -sf "$STAGING_URL/api/rag/search?q=Assiette+Démo+Staging&k=1" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['hits'])" 2>/dev/null || echo "0")

if [ "$STAGING_CHECK" = "0" ]; then
    warn "Les données staging ne semblent pas indexées."
    warn "Lancez : make staging-rebuild && make staging-watch"
    fail "Abandon : promotion annulée (index staging vide ou incorrect)"
fi
ok "Données staging détectées dans l'index ($STAGING_CHECK chunk(s))"

# ── Étape 3 : Tests automatisés sur staging ───────────────────────────────────
echo ""
echo "── Étape 3/5 : Tests automatisés sur staging..."

if [ "$SKIP_TESTS" = "1" ]; then
    warn "SKIP_TESTS=1 : tests ignorés (déconseillé !)"
else
    python3 -c "import pytest, httpx" 2>/dev/null || {
        fail "Dépendances manquantes. Exécutez : make test-install"
    }

    echo "  Lancement des tests smoke + quality gate sur staging..."
    if ! AGENT_URL="$STAGING_URL" python3 -m pytest tests/test_smoke.py tests/test_rag_quality.py \
            -v --tb=short -q 2>&1; then
        fail "Tests staging échoués → promotion annulée. Corrigez les problèmes staging d'abord."
    fi
    ok "Tous les tests staging sont verts"
fi

# ── Étape 4 : Copie data-staging/ → data/ ────────────────────────────────────
echo ""
echo "── Étape 4/5 : Promotion des données staging → production..."

# Sauvegarde de sécurité
BACKUP_DIR="data-backup-$(date +%Y%m%d_%H%M%S)"
cp -r data/ "$BACKUP_DIR"
ok "Sauvegarde créée : $BACKUP_DIR/"

# Copie staging → production
cp -r data-staging/. data/
ok "data-staging/ → data/ copié"

# ── Étape 5 : Rebuild de l'index production avec quality gate ─────────────────
echo ""
echo "── Étape 5/5 : Rebuild de l'index production (quality gate incluse)..."

curl -sf -X POST "$PRODUCTION_URL/api/rag/rebuild" > /dev/null
ok "Rebuild production lancé"

echo "  Attente de la fin du rebuild..."
while true; do
    STATE=$(curl -sf "$PRODUCTION_URL/api/rag/status" \
        | python3 -c "import sys,json; print(json.load(sys.stdin)['state'])" 2>/dev/null || echo "unknown")
    if [ "$STATE" != "rebuilding" ]; then
        break
    fi
    echo -n "."
    sleep 3
done
echo ""

# Résultat final
STATUS_JSON=$(curl -sf "$PRODUCTION_URL/api/rag/status")
STATE=$(echo "$STATUS_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['state'])")

echo ""
echo "$STATUS_JSON" | python3 -m json.tool
echo ""

if [ "$STATE" = "done" ]; then
    ok "Rebuild production terminé avec succès"
    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo -e "  ${GREEN}✓ Promotion réussie !${NC}"
    echo "════════════════════════════════════════════════════════════"
    echo ""
    echo "  Sauvegarde ancienne production : $BACKUP_DIR/"
    echo "  Supprimez-la si tout est OK : rm -rf $BACKUP_DIR"
    echo ""
    echo "  Prochaine étape : make test"
elif [ "$STATE" = "quality_gate_failed" ]; then
    warn "Quality gate production FAILED → rollback des données..."
    cp -r "$BACKUP_DIR/." data/
    curl -sf -X POST "$PRODUCTION_URL/api/rag/rebuild" > /dev/null
    fail "Promotion annulée : quality gate production a échoué. Données restaurées depuis $BACKUP_DIR."
else
    warn "Rebuild production en état inattendu : $STATE"
    warn "Vérifiez les logs : make logs-agent"
    warn "Données de sauvegarde disponibles : $BACKUP_DIR/"
    fail "Promotion incomplète — vérification manuelle requise."
fi
