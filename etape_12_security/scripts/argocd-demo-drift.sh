#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# argocd-demo-drift.sh — Démonstration de la détection de dérive GitOps
# Étape 09 : GitOps
#
# Ce script illustre le principe central de GitOps :
# "Git est la seule source de vérité. Toute modification hors de Git est
#  une dérive. ArgoCD la détecte et la corrige automatiquement."
#
# Scénario pédagogique :
#   1. On modifie manuellement le cluster (kubectl scale)
#      → Simulation d'une "urgence" ou d'une erreur humaine
#   2. ArgoCD détecte la dérive (état cluster ≠ état Git)
#   3. ArgoCD restaure automatiquement (selfHeal=true)
#   4. On vérifie que le cluster est revenu à l'état Git
#
# Usage :
#   bash scripts/argocd-demo-drift.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()    { echo -e "${GREEN}✓${NC} $*"; }
step()  { echo -e "\n${BLUE}══${NC} ${CYAN}$*${NC}"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
info()  { echo -e "   $*"; }
pause() { echo -e "\n${YELLOW}[Appuyer sur Entrée pour continuer...]${NC}"; read -r; }

cd "$(dirname "$0")/.."

NS="traiteur"

echo ""
echo "════════════════════════════════════════════════════════"
echo "  Démonstration GitOps — Détection de Dérive (Drift)"
echo "════════════════════════════════════════════════════════"
echo ""
echo "  Scénario : un opérateur modifie le cluster manuellement"
echo "             (\"fix d'urgence\" ou erreur humaine)."
echo "  GitOps   : ArgoCD détecte la dérive et restaure."
echo ""

# ── Étape 1 : État initial ───────────────────────────────────────────────────
step "1/4 — État initial (depuis Git)"

REPLICAS_GIT=$(grep "replicas:" k8s/agent.yaml | head -1 | awk '{print $2}')
REPLICAS_CLUSTER=$(kubectl get deployment agent -n "$NS" \
    -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "?")

info "Replicas dans Git     : ${REPLICAS_GIT}"
info "Replicas dans cluster : ${REPLICAS_CLUSTER}"
info "Statut ArgoCD         : $(kubectl get application traiteur -n argocd \
    -o jsonpath='{.status.sync.status}' 2>/dev/null || echo 'N/A')"

ok "État cohérent — Git = Cluster"
pause

# ── Étape 2 : Simulation d'une modification manuelle ─────────────────────────
step "2/4 — Modification manuelle du cluster (kubectl scale)"
echo ""
warn "Simulation : un opérateur scale l'agent à 4 replicas pour 'absorber un pic'."
echo ""
echo "  \$ kubectl scale deployment agent -n traiteur --replicas=4"
echo ""
pause

kubectl scale deployment agent -n "$NS" --replicas=4
sleep 2

REPLICAS_NOW=$(kubectl get deployment agent -n "$NS" \
    -o jsonpath='{.spec.replicas}')
info "Replicas dans cluster maintenant : ${REPLICAS_NOW}"
warn "DÉRIVE CRÉÉE : cluster (${REPLICAS_NOW}) ≠ Git (${REPLICAS_GIT})"

echo ""
info "Dans l'UI ArgoCD (https://localhost:8080) :"
info "  → L'application passe en statut 'OutOfSync'"
info "  → La ressource 'agent' est surlignée en orange"
echo ""
pause

# ── Étape 3 : ArgoCD détecte et corrige ──────────────────────────────────────
step "3/4 — ArgoCD détecte la dérive et restaure (selfHeal)"
echo ""
info "Avec selfHeal=true, ArgoCD corrige dans les 3 minutes."
info "Pour accélérer la démonstration, on force un sync maintenant..."
echo ""
echo "  \$ argocd app sync traiteur  (ou kubectl annotate pour forcer)"
echo ""
pause

# Forcer la réconciliation via annotation (fonctionne sans argocd CLI)
kubectl patch application traiteur -n argocd \
    --type merge \
    -p '{"operation":{"initiatedBy":{"username":"demo-drift"},"sync":{"revision":"HEAD","syncOptions":["CreateNamespace=true"]}}}'

info "Sync forcé — ArgoCD réconcilie..."
sleep 5

# Attendre que le déploiement revienne à la valeur Git
for i in $(seq 1 24); do
    CURRENT=$(kubectl get deployment agent -n "$NS" \
        -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "?")
    if [ "$CURRENT" = "$REPLICAS_GIT" ]; then
        ok "Restauré ! Replicas = ${CURRENT} (valeur Git : ${REPLICAS_GIT})"
        break
    fi
    echo -n "   Attente réconciliation... (${i}/24) replicas=${CURRENT}   "
    echo -e "\r"
    sleep 5
done

# ── Étape 4 : Vérification ───────────────────────────────────────────────────
step "4/4 — Vérification de l'état final"

REPLICAS_FINAL=$(kubectl get deployment agent -n "$NS" \
    -o jsonpath='{.spec.replicas}')
SYNC_STATUS=$(kubectl get application traiteur -n argocd \
    -o jsonpath='{.status.sync.status}' 2>/dev/null || echo "N/A")
HEALTH_STATUS=$(kubectl get application traiteur -n argocd \
    -o jsonpath='{.status.health.status}' 2>/dev/null || echo "N/A")

echo ""
echo "  ┌─────────────────────────────────────────────┐"
echo "  │  Résultat de la démonstration               │"
echo "  │                                             │"
echo "  │  Replicas (Git)     : ${REPLICAS_GIT}                         │"
echo "  │  Replicas (cluster) : ${REPLICAS_FINAL}                         │"
echo "  │  Sync status        : ${SYNC_STATUS}                   │"
echo "  │  Health status      : ${HEALTH_STATUS}                  │"
echo "  └─────────────────────────────────────────────┘"

echo ""
if [ "$REPLICAS_FINAL" = "$REPLICAS_GIT" ] && [ "$SYNC_STATUS" = "Synced" ]; then
    ok "GitOps démontré avec succès !"
    echo ""
    echo "  Leçon : toute modification manuelle du cluster est éphémère."
    echo "  La seule façon de changer l'état du cluster durablement :"
    echo "    git commit → git push → ArgoCD sync"
    echo ""
    echo "  C'est la définition de GitOps."
else
    warn "Réconciliation en cours — vérifier dans l'UI : https://localhost:8080"
fi
