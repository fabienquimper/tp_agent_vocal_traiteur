#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# canary-loadgen.sh — Générateur de charge + observateur du split trafic
# Étape 11 : Canary Release
#
# Envoie N requêtes à l'ingress NGINX et observe :
#   - Combien ont été servies par le stable (env: production)
#   - Combien ont été servies par le canary  (env: canary)
#   - Comparaison avec le poids configuré
#
# Usage :
#   bash scripts/canary-loadgen.sh                  # 50 requêtes
#   bash scripts/canary-loadgen.sh --count 200      # 200 requêtes
#   bash scripts/canary-loadgen.sh --continuous     # boucle infinie (Ctrl+C pour arrêter)
#
# Prérequis :
#   - Ingress NGINX actif (make canary-setup)
#   - Agent accessible sur localhost:8081 (via ingress)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()    { echo -e "${GREEN}✓${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }

INGRESS_URL="${INGRESS_URL:-http://localhost:8081}"
COUNT=50
CONTINUOUS=false

# Parsing des arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --count) COUNT="$2"; shift 2 ;;
        --continuous) CONTINUOUS=true; shift ;;
        *) shift ;;
    esac
done

# Vérifier que l'ingress est accessible
if ! curl -sf "${INGRESS_URL}/health" > /dev/null 2>&1; then
    echo -e "${RED}✗${NC} Ingress non accessible sur ${INGRESS_URL}"
    echo "   Démarrer le canary : make canary-setup"
    exit 1
fi

# Récupérer le poids canary configuré
CONFIGURED_WEIGHT=$(kubectl get ingress agent-canary-ingress -n traiteur \
    -o jsonpath='{.metadata.annotations.nginx\.ingress\.kubernetes\.io/canary-weight}' \
    2>/dev/null || echo "?")

run_loadgen() {
    local count="$1"
    local stable_count=0
    local canary_count=0
    local error_count=0

    echo ""
    echo -e "${CYAN}Envoi de ${count} requêtes vers ${INGRESS_URL}/health${NC}"
    echo -e "Poids canary configuré : ${CONFIGURED_WEIGHT}%"
    echo ""

    for i in $(seq 1 "$count"); do
        RESP=$(curl -sf "${INGRESS_URL}/health" 2>/dev/null || echo '{"status":"error"}')
        ENV=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('env','?'))" 2>/dev/null || echo "?")

        case "$ENV" in
            production) stable_count=$((stable_count + 1)) ;;
            canary)     canary_count=$((canary_count + 1)) ;;
            *)          error_count=$((error_count + 1)) ;;
        esac

        # Barre de progression
        printf "\r   %d/%d | stable=%d | canary=%d | errors=%d" \
            "$i" "$count" "$stable_count" "$canary_count" "$error_count"
    done

    echo ""
    echo ""

    # Calcul des pourcentages
    local total=$((stable_count + canary_count + error_count))
    local canary_pct=0
    local stable_pct=0
    if [ "$total" -gt 0 ]; then
        canary_pct=$(python3 -c "print(f'{${canary_count}/${total}*100:.1f}')" 2>/dev/null || echo "?")
        stable_pct=$(python3 -c "print(f'{${stable_count}/${total}*100:.1f}')" 2>/dev/null || echo "?")
    fi

    echo "  ┌──────────────────────────────────────────────────┐"
    echo "  │  Résultat (${total} requêtes)                        │"
    echo "  │                                                  │"
    printf "  │  Stable (env=production) : %3d req  (%5s%%)   │\n" "$stable_count" "$stable_pct"
    printf "  │  Canary (env=canary)      : %3d req  (%5s%%)   │\n" "$canary_count" "$canary_pct"
    [ "$error_count" -gt 0 ] && printf "  │  Erreurs                  : %3d req           │\n" "$error_count"
    echo "  │                                                  │"
    printf "  │  Poids configuré : %3s%%                         │\n" "$CONFIGURED_WEIGHT"
    echo "  └──────────────────────────────────────────────────┘"
    echo ""

    # Validation : la distribution observée doit être proche du poids configuré
    if [ "$CONFIGURED_WEIGHT" != "?" ] && [ "$canary_count" -gt 0 ]; then
        EXPECTED_CANARY=$(python3 -c "
import math
expected = ${count} * ${CONFIGURED_WEIGHT} / 100
margin = max(5, expected * 0.5)  # ±50% de marge (aléatoire sur petit nombre)
actual = ${canary_count}
ok = abs(actual - expected) <= margin
print('ok' if ok else 'warn')
" 2>/dev/null || echo "ok")

        if [ "$EXPECTED_CANARY" = "ok" ]; then
            ok "Distribution cohérente avec le poids configuré (${CONFIGURED_WEIGHT}%)"
        else
            warn "Distribution inattendue — le poids configuré est ${CONFIGURED_WEIGHT}% mais ${canary_pct}% observé"
            warn "(normal sur petit nombre de requêtes — augmenter --count pour plus de précision)"
        fi
    fi
}

if [ "$CONTINUOUS" = true ]; then
    echo -e "${CYAN}Mode continu — Ctrl+C pour arrêter${NC}"
    while true; do
        run_loadgen 20
        sleep 5
        CONFIGURED_WEIGHT=$(kubectl get ingress agent-canary-ingress -n traiteur \
            -o jsonpath='{.metadata.annotations.nginx\.ingress\.kubernetes\.io/canary-weight}' \
            2>/dev/null || echo "?")
    done
else
    run_loadgen "$COUNT"
fi
