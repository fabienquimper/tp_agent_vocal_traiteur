#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# canary-setup.sh — Installation NGINX Ingress + déploiement canary initial
# Étape 11 : Canary Release
#
# Ce script :
#   1. Installe NGINX Ingress Controller dans le cluster kind
#   2. Déploie agent-canary (la version candidate)
#   3. Configure l'ingress avec 10% de trafic vers le canary
#   4. Affiche les URLs d'accès
#
# Usage :
#   bash scripts/canary-setup.sh              # canary normal (même image, APP_ENV=canary)
#   bash scripts/canary-setup.sh --broken     # canary cassé (simule un bug LLM)
#
# Prérequis :
#   - Cluster kind "traiteur" actif avec le port 80 mappé (make k8s-up)
#   - Services agent, stt, tts, ollama déjà déployés
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()    { echo -e "${GREEN}✓${NC} $*"; }
step()  { echo -e "\n${BLUE}══${NC} ${CYAN}$*${NC}"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
info()  { echo -e "   $*"; }
fail()  { echo -e "${RED}✗${NC} $*"; exit 1; }

cd "$(dirname "$0")/.."

BROKEN="${1:-}"
NS="traiteur"
CLUSTER="traiteur"
INGRESS_HOST_PORT="8081"

echo ""
echo "════════════════════════════════════════════════════════"
echo "  Canary Setup — Traiteur Dupont (étape 11)"
[ "$BROKEN" = "--broken" ] && echo "  MODE : Canary cassé (démo rollback automatique)"
echo "════════════════════════════════════════════════════════"

# ── Étape 1 : NGINX Ingress Controller ───────────────────────────────────────
step "1/4 — NGINX Ingress Controller"

if kubectl get deployment ingress-nginx-controller -n ingress-nginx > /dev/null 2>&1; then
    ok "NGINX Ingress Controller déjà installé"
else
    info "Installation NGINX Ingress Controller (version kind)..."
    # Version kind-spécifique : NodePort sur le port 80 du nœud
    kubectl apply -f \
        https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.1/deploy/static/provider/kind/deploy.yaml

    info "Attente que NGINX Ingress Controller soit prêt..."
    kubectl rollout status deployment/ingress-nginx-controller \
        -n ingress-nginx --timeout=300s
    ok "NGINX Ingress Controller prêt"
fi

# ── Étape 2 : Déploiement du canary ──────────────────────────────────────────
step "2/4 — Déploiement agent-canary"

if [ "$BROKEN" = "--broken" ]; then
    warn "Mode 'broken canary' : OLLAMA_BASE_URL = http://nonexistent:11434"
    info "Le canary répondra aux /health mais échouera sur /api/text (LLM indisponible)"
    # Patch temporaire du YAML pour simuler un canary cassé
    sed 's|# - name: OLLAMA_BASE_URL|- name: OLLAMA_BASE_URL|;
         s|#   value: "http://nonexistent-ollama:11434"|  value: "http://nonexistent-ollama:11434"|' \
        k8s/agent-canary.yaml | kubectl apply -f -
else
    kubectl apply -f k8s/agent-canary.yaml
fi

ok "Deployment agent-canary appliqué"

info "Attente que le pod canary soit Ready (ChromaDB rebuild ~90s)..."
kubectl rollout status deployment/agent-canary -n "$NS" --timeout=300s
ok "Pod canary prêt"

# ── Étape 3 : Ingress avec split 10% → canary ────────────────────────────────
step "3/4 — Configuration de l'ingress (split 10/90)"

kubectl apply -f k8s/ingress.yaml
ok "Ingress stable + canary appliqués"

info "Vérification des ingress..."
kubectl get ingress -n "$NS"

# ── Étape 4 : Vérification ────────────────────────────────────────────────────
step "4/4 — Vérification"

info "Pods en cours d'exécution :"
kubectl get pods -n "$NS" -l "app in (agent, agent-canary)" -o wide

echo ""
echo "════════════════════════════════════════════════════════"
ok "Canary déployé !"
echo ""
echo "  Accès (via NGINX Ingress) :"
echo "    http://localhost:${INGRESS_HOST_PORT}/health    → varie: stable/canary"
echo "    http://localhost:${INGRESS_HOST_PORT}/api/text  → idem"
echo ""
echo "  Accès direct (toujours stable) :"
echo "    http://localhost:8000/health     → toujours stable (NodePort direct)"
echo ""
echo "  Répartition actuelle :"
echo "    90% → agent stable   (env: production)"
echo "    10% → agent-canary   (env: canary)"
echo ""
echo "  Commandes :"
echo "    make canary-status           → état du split trafic"
echo "    make canary-loadgen          → observer le split en direct"
echo "    make canary-step WEIGHT=20   → passer à 20% canary"
echo "    make canary-promote          → promotion automatique avec checks"
echo "    make canary-rollback         → rollback à 0%"
echo "════════════════════════════════════════════════════════"
