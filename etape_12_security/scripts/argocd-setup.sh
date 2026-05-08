#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# argocd-setup.sh — Installation et configuration d'ArgoCD
# Étape 09 : GitOps
#
# Ce script :
#   1. Vérifie que le cluster kind est actif
#   2. Installe ArgoCD dans le namespace "argocd"
#   3. Expose ArgoCD UI via NodePort (accessible sur localhost:8080)
#   4. Crée l'AppProject + l'Application ArgoCD
#   5. Déclenche le premier sync
#   6. Affiche les credentials de connexion
#
# Usage :
#   bash scripts/argocd-setup.sh https://github.com/VOTRE_USER/tp_agent_vocal_traiteur.git
#
# Prérequis :
#   - kind cluster "traiteur" actif (make k8s-up)
#   - kubectl configuré sur le cluster traiteur
#   - Connexion internet (pour télécharger les manifestes ArgoCD)
#
# Optionnel :
#   - argocd CLI (https://argo-cd.readthedocs.io/en/stable/cli_installation/)
#     Si absent, le script utilise uniquement kubectl.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Couleurs ─────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'
ok()    { echo -e "${GREEN}✓${NC} $*"; }
step()  { echo -e "\n${BLUE}══${NC} ${CYAN}$*${NC}"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
fail()  { echo -e "${RED}✗${NC} $*"; exit 1; }
info()  { echo -e "   $*"; }

# S'assurer d'être dans le bon dossier (racine du projet)
cd "$(dirname "$0")/.."

REPO_URL="${1:-}"
ARGOCD_VERSION="v2.11.3"
ARGOCD_NAMESPACE="argocd"
APP_NAMESPACE="traiteur"
CLUSTER_NAME="traiteur"
ARGOCD_NODEPORT="30081"
ARGOCD_HOST_PORT="8080"

# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
echo "  ArgoCD Setup — Traiteur Dupont (étape 09 GitOps)"
echo "════════════════════════════════════════════════════════"

# ── Étape 1 : Vérifications ──────────────────────────────────────────────────
step "1/6 — Vérifications"

if ! kubectl cluster-info --context "kind-${CLUSTER_NAME}" > /dev/null 2>&1; then
    fail "Cluster kind '${CLUSTER_NAME}' non trouvé. Exécuter d'abord : make k8s-up"
fi
ok "Cluster kind '${CLUSTER_NAME}' actif"

if [ -z "$REPO_URL" ]; then
    echo ""
    warn "Aucune URL de dépôt fournie."
    info "Usage : bash scripts/argocd-setup.sh https://github.com/VOTRE_USER/tp_agent_vocal_traiteur.git"
    info ""
    info "Si votre dépôt est PRIVÉ, ajoutez vos credentials :"
    info "  argocd repo add <URL> --username <user> --password <token>"
    echo ""
    read -rp "   URL du dépôt Git (ou Entrée pour utiliser le mode local) : " REPO_URL
    REPO_URL="${REPO_URL:-}"
fi

if [ -z "$REPO_URL" ]; then
    warn "Mode local activé : argocd surveillera un dépôt git local dans le cluster."
    warn "Pour un rendu production-grade, utilisez un dépôt GitHub."
    USE_LOCAL_GIT=true
else
    USE_LOCAL_GIT=false
    ok "Dépôt Git : ${REPO_URL}"
fi

# ── Étape 2 : Installation ArgoCD ────────────────────────────────────────────
step "2/6 — Installation ArgoCD ${ARGOCD_VERSION}"

kubectl create namespace "${ARGOCD_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

# Vérifier si ArgoCD est déjà installé
if kubectl get deployment argocd-server -n "${ARGOCD_NAMESPACE}" > /dev/null 2>&1; then
    ok "ArgoCD déjà installé — skip"
else
    info "Téléchargement et installation des manifestes ArgoCD..."
    kubectl apply -n "${ARGOCD_NAMESPACE}" \
        -f "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"
    ok "Manifestes ArgoCD appliqués"
fi

info "Attente que ArgoCD soit prêt (peut prendre 2-3 minutes)..."
kubectl rollout status deployment/argocd-server \
    -n "${ARGOCD_NAMESPACE}" --timeout=300s
kubectl rollout status deployment/argocd-repo-server \
    -n "${ARGOCD_NAMESPACE}" --timeout=300s
ok "ArgoCD opérationnel"

# ── Étape 3 : Exposition de l'UI ArgoCD via NodePort ─────────────────────────
step "3/6 — Exposition ArgoCD UI (NodePort ${ARGOCD_NODEPORT} → localhost:${ARGOCD_HOST_PORT})"

# Patcher le service argocd-server pour le rendre accessible depuis l'hôte
kubectl patch service argocd-server \
    -n "${ARGOCD_NAMESPACE}" \
    -p "{\"spec\":{\"type\":\"NodePort\",\"ports\":[{\"name\":\"https\",\"port\":443,\"targetPort\":8080,\"nodePort\":${ARGOCD_NODEPORT},\"protocol\":\"TCP\"}]}}"

ok "ArgoCD UI : http://localhost:${ARGOCD_HOST_PORT} (HTTP via NodePort)"
info "Note : ArgoCD utilise HTTPS par défaut — le navigateur affichera un avertissement."
info "       Cliquer sur 'Continuer quand même' (certificat auto-signé)."

# ── Étape 4 : Récupération du mot de passe admin ─────────────────────────────
step "4/6 — Récupération des credentials"

# Le mot de passe initial est stocké dans un Secret K8s
ARGOCD_PASSWORD=$(kubectl get secret argocd-initial-admin-secret \
    -n "${ARGOCD_NAMESPACE}" \
    -o jsonpath="{.data.password}" | base64 -d)

echo ""
echo "  ┌──────────────────────────────────────────────────┐"
echo "  │  ArgoCD Credentials                              │"
echo "  │  URL      : https://localhost:${ARGOCD_HOST_PORT}              │"
echo "  │  Username : admin                                │"
echo "  │  Password : ${ARGOCD_PASSWORD}    │"
echo "  └──────────────────────────────────────────────────┘"
echo ""

# Login via argocd CLI si disponible
if command -v argocd > /dev/null 2>&1; then
    info "Login argocd CLI..."
    argocd login "localhost:${ARGOCD_HOST_PORT}" \
        --username admin \
        --password "${ARGOCD_PASSWORD}" \
        --insecure \
        --grpc-web || warn "Login CLI échoué — utiliser l'UI web"
    ok "argocd CLI connecté"
else
    warn "argocd CLI non installé — utiliser uniquement l'UI web."
    info "Installation : https://argo-cd.readthedocs.io/en/stable/cli_installation/"
fi

# ── Étape 5 : Création AppProject + Application ───────────────────────────────
step "5/6 — Création AppProject et Application ArgoCD"

# AppProject : définit les permissions
kubectl apply -f argocd/project.yaml
ok "AppProject 'traiteur' créé"

# Application : génération depuis le template + substitution REPO_URL
if [ "$USE_LOCAL_GIT" = false ]; then
    sed "s|REPO_URL|${REPO_URL}|g" argocd/application.yaml | kubectl apply -f -
    ok "Application ArgoCD 'traiteur' créée → surveille ${REPO_URL}/k8s/"
else
    # Mode local : utiliser argocd CLI avec un repo local monté
    # (avancé — se référer à la documentation pour le mode "local override")
    warn "Mode local non supporté automatiquement."
    info "Renseigner REPO_URL et relancer : bash scripts/argocd-setup.sh <URL>"
fi

# ── Étape 6 : Premier sync ────────────────────────────────────────────────────
step "6/6 — Déclenchement du premier sync"

if command -v argocd > /dev/null 2>&1 && [ "$USE_LOCAL_GIT" = false ]; then
    info "Sync en cours..."
    argocd app sync traiteur --grpc-web || true

    info "Attente de la convergence..."
    argocd app wait traiteur \
        --sync \
        --health \
        --timeout 300 \
        --grpc-web || warn "Timeout — vérifier avec : argocd app get traiteur"

    ok "Sync initial terminé"

    echo ""
    argocd app get traiteur --grpc-web
else
    info "Vérifier l'état du sync dans l'UI : https://localhost:${ARGOCD_HOST_PORT}"
    info "Ou : kubectl get application traiteur -n argocd"
fi

# ── Résumé ────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
ok "ArgoCD opérationnel !"
echo ""
echo "  Accès UI     : https://localhost:${ARGOCD_HOST_PORT}"
echo "  Username     : admin"
echo "  Password     : ${ARGOCD_PASSWORD}"
echo ""
echo "  Commandes utiles :"
echo "    make argocd-status   → état de l'Application"
echo "    make argocd-diff     → différences Git ↔ cluster"
echo "    make argocd-sync     → sync manuel"
echo "    make argocd-demo-drift → démonstration de détection de dérive"
echo "════════════════════════════════════════════════════════"
