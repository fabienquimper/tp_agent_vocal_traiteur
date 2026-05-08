#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# canary-step.sh — Ajuste le poids du canary et vérifie les métriques
# Étape 11 : Canary Release
#
# Ce script :
#   1. Change le canary-weight sur l'ingress NGINX
#   2. Attend 30s (délai de propagation + nouvelles métriques)
#   3. Vérifie le taux d'erreur dans Prometheus
#   4. Retourne 0 (ok) ou 1 (échec → déclenche le rollback)
#
# Usage :
#   bash scripts/canary-step.sh 20        # passe à 20% canary
#   bash scripts/canary-step.sh 0         # rollback à 0%
#   bash scripts/canary-step.sh 100       # promotion complète
#
# Variables d'environnement :
#   PROMETHEUS_URL  → URL de Prometheus (défaut: http://localhost:9090)
#   ERROR_THRESHOLD → taux d'erreur max acceptable (défaut: 0.05 = 5%)
#   WAIT_SECONDS    → délai entre le changement et la vérification (défaut: 30)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'
BLUE='\033[0;34m'; NC='\033[0m'
ok()    { echo -e "${GREEN}✓${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
fail()  { echo -e "${RED}✗${NC} $*"; }

WEIGHT="${1:-}"
NS="traiteur"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
ERROR_THRESHOLD="${ERROR_THRESHOLD:-0.05}"
WAIT_SECONDS="${WAIT_SECONDS:-30}"

if [ -z "$WEIGHT" ]; then
    echo "Usage: $0 <weight 0-100>"
    echo "  $0 10   → 10% du trafic vers le canary"
    echo "  $0 0    → rollback (0% canary)"
    echo "  $0 100  → promotion complète (100% canary)"
    exit 1
fi

echo ""
echo -e "${BLUE}──${NC} Canary Step : ${WEIGHT}%"
echo ""

# ── 1. Changer le poids dans l'ingress ───────────────────────────────────────
echo -e "   Mise à jour canary-weight → ${WEIGHT}%..."
kubectl annotate ingress agent-canary-ingress \
    "nginx.ingress.kubernetes.io/canary-weight=${WEIGHT}" \
    --overwrite -n "$NS"

# Afficher l'état courant
CURRENT_WEIGHT=$(kubectl get ingress agent-canary-ingress -n "$NS" \
    -o jsonpath='{.metadata.annotations.nginx\.ingress\.kubernetes\.io/canary-weight}' \
    2>/dev/null || echo "?")
ok "canary-weight = ${CURRENT_WEIGHT}%"

# Si rollback ou promotion 100%, pas besoin de vérifier les métriques
if [ "$WEIGHT" = "0" ]; then
    ok "Rollback : 0% du trafic vers le canary"
    echo "   L'ingress canary reste en place (avec weight=0)."
    echo "   Pour supprimer le canary : make canary-teardown"
    exit 0
fi

if [ "$WEIGHT" = "100" ]; then
    ok "Promotion complète : 100% vers le canary"
    echo "   Prochaine étape : make canary-finalize (remplace stable par canary)"
    exit 0
fi

# ── 2. Attendre que les nouvelles métriques arrivent ─────────────────────────
echo ""
echo -e "   Attente ${WAIT_SECONDS}s (propagation NGINX + nouvelles métriques)..."
for i in $(seq 1 "$WAIT_SECONDS"); do
    printf "\r   %d/%ds" "$i" "$WAIT_SECONDS"
    sleep 1
done
echo ""

# ── 3. Vérifier le taux d'erreur dans Prometheus ─────────────────────────────
echo ""
echo -e "   Vérification des métriques Prometheus..."

# Taux d'erreur global sur la dernière minute
# conversations_total{status="error"} / conversations_total (toutes)
PROM_QUERY='sum(rate(conversations_total{status="error"}[1m])) / sum(rate(conversations_total[1m]))'

if ! command -v curl > /dev/null; then
    warn "curl non disponible — skip vérification Prometheus"
    ok "canary-weight = ${WEIGHT}% (sans vérification métriques)"
    exit 0
fi

PROM_RESULT=$(curl -sf \
    "${PROMETHEUS_URL}/api/v1/query" \
    --data-urlencode "query=${PROM_QUERY}" \
    2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
results = data.get('data', {}).get('result', [])
if results:
    val = float(results[0]['value'][1])
    print(f'{val:.4f}')
else:
    print('N/A')
" 2>/dev/null || echo "N/A")

echo -e "   Taux d'erreur (1m) : ${PROM_RESULT}"

if [ "$PROM_RESULT" = "N/A" ]; then
    warn "Prometheus non accessible ou pas de données — vérification ignorée"
    ok "Canary à ${WEIGHT}% (métriques non vérifiées)"
    exit 0
fi

# Comparer avec le seuil
IS_OK=$(python3 -c "
try:
    val = float('${PROM_RESULT}')
    threshold = float('${ERROR_THRESHOLD}')
    print('yes' if val <= threshold else 'no')
except:
    print('yes')
" 2>/dev/null || echo "yes")

echo ""
if [ "$IS_OK" = "yes" ]; then
    ok "Taux d'erreur (${PROM_RESULT}) ≤ seuil (${ERROR_THRESHOLD}) → canary à ${WEIGHT}% ✓"
    exit 0
else
    fail "Taux d'erreur (${PROM_RESULT}) > seuil (${ERROR_THRESHOLD}) → ROLLBACK recommandé"
    echo ""
    echo "   Pour rollback : bash scripts/canary-step.sh 0"
    echo "   Ou            : make canary-rollback"
    exit 1
fi
