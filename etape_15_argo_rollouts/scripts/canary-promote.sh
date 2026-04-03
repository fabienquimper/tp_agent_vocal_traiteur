#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# canary-promote.sh — Promotion automatique progressive du canary
# Étape 11 : Canary Release
#
# Ce script reproduit le comportement de Flagger en mode simplifié :
#
#   Phase 1  : 10% canary  → vérification métriques
#   Phase 2  : 20% canary  → vérification métriques
#   Phase 3  : 40% canary  → vérification métriques
#   Phase 4  : 80% canary  → vérification métriques
#   Phase 5  : 100% canary → promotion finale
#       ↓
#   make canary-finalize   → remplace l'image stable par l'image canary
#
# À CHAQUE ÉTAPE :
#   Si taux_erreur > seuil → rollback automatique à 0% + alerte
#   Si taux_erreur ≤ seuil → passage à l'étape suivante
#
# Usage :
#   bash scripts/canary-promote.sh                     # promotion complète
#   bash scripts/canary-promote.sh --steps 10,25,50    # étapes personnalisées
#   WAIT_SECONDS=60 bash scripts/canary-promote.sh     # délai plus long
#
# Variables :
#   WAIT_SECONDS     → délai entre chaque étape (défaut: 30)
#   ERROR_THRESHOLD  → taux d'erreur max (défaut: 0.05 = 5%)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()    { echo -e "${GREEN}✓${NC} $*"; }
step()  { echo -e "\n${BLUE}══${NC} ${CYAN}$*${NC}"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
fail()  { echo -e "${RED}✗${NC} $*"; }

cd "$(dirname "$0")/.."

NS="traiteur"
WAIT_SECONDS="${WAIT_SECONDS:-30}"
ERROR_THRESHOLD="${ERROR_THRESHOLD:-0.05}"

# Étapes de progression
CUSTOM_STEPS="${1:-}"
if [[ "$CUSTOM_STEPS" == --steps* ]]; then
    IFS=',' read -ra STEPS <<< "${CUSTOM_STEPS#--steps }"
else
    STEPS=(10 20 40 80 100)
fi

echo ""
echo "════════════════════════════════════════════════════════"
echo "  Promotion Canary Automatique — Traiteur Dupont"
echo "  Étapes : ${STEPS[*]}%"
echo "  Délai/étape : ${WAIT_SECONDS}s"
echo "  Seuil erreur : ${ERROR_THRESHOLD} ($(echo "$ERROR_THRESHOLD * 100" | python3 -c 'import sys; print(f"{float(input()):.0f}")' 2>/dev/null || echo "?")%)"
echo "════════════════════════════════════════════════════════"

# ── Vérifier que le canary est déployé ───────────────────────────────────────
if ! kubectl get deployment agent-canary -n "$NS" > /dev/null 2>&1; then
    fail "Deployment 'agent-canary' introuvable."
    echo "   Démarrer le canary : make canary-setup"
    exit 1
fi

CANARY_READY=$(kubectl get deployment agent-canary -n "$NS" \
    -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
if [ "${CANARY_READY:-0}" = "0" ]; then
    warn "Le pod canary n'est pas encore Ready. Attente..."
    kubectl rollout status deployment/agent-canary -n "$NS" --timeout=300s
fi
ok "Pod canary Ready"

# ── Promotion progressive ─────────────────────────────────────────────────────
STEP_NUM=0
TOTAL=${#STEPS[@]}

for WEIGHT in "${STEPS[@]}"; do
    STEP_NUM=$((STEP_NUM + 1))
    step "Étape ${STEP_NUM}/${TOTAL} : ${WEIGHT}% → canary"

    # Changer le poids
    if bash scripts/canary-step.sh "$WEIGHT"; then
        if [ "$WEIGHT" = "100" ]; then
            echo ""
            ok "Canary à 100% — promotion complète !"
            echo ""
            echo "   Étape finale : remplacer le stable par le canary"
            echo "   make canary-finalize"
            break
        fi
    else
        # canary-step.sh a retourné une erreur → rollback automatique
        echo ""
        fail "Métriques dégradées à ${WEIGHT}% → ROLLBACK AUTOMATIQUE"
        echo ""
        warn "Rollback en cours..."
        bash scripts/canary-step.sh 0
        echo ""
        fail "Promotion ANNULÉE. Le trafic est revenu à 100% stable."
        echo ""
        echo "   Diagnostics :"
        echo "     Prometheus : http://localhost:9090"
        echo "     Jaeger     : http://localhost:16686"
        echo "     Logs canary : kubectl logs -n traiteur -l app=agent-canary --tail=50"
        echo ""
        echo "   Pour corriger et réessayer :"
        echo "     1. Corriger le bug dans le code"
        echo "     2. Rebuilder l'image : docker build -t traiteur-agent:latest services/agent"
        echo "     3. Recharger dans kind : kind load docker-image traiteur-agent:latest --name traiteur"
        echo "     4. Redéployer le canary : kubectl rollout restart deployment/agent-canary -n traiteur"
        echo "     5. Relancer : make canary-promote"
        exit 1
    fi
done

echo ""
echo "════════════════════════════════════════════════════════"
ok "Promotion réussie !"
echo ""
echo "  Historique de la promotion :"
for WEIGHT in "${STEPS[@]}"; do
    echo "    ${WEIGHT}% → OK"
done
echo ""
echo "  Prochaine étape :"
echo "    make canary-finalize  → met à jour le Deployment stable"
echo "                            (remplace l'image et scale canary à 0)"
echo "════════════════════════════════════════════════════════"
