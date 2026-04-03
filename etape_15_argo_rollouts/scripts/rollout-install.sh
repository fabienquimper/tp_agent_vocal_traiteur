#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# rollout-install.sh — Installation d'Argo Rollouts dans le cluster kind
# Étape 15 : Progressive Delivery automatisé
#
# Ce script installe :
#   1. Le contrôleur Argo Rollouts (dans le namespace argo-rollouts)
#   2. Les CRDs : Rollout, AnalysisTemplate, AnalysisRun, Experiment
#   3. Le plugin kubectl argo rollouts (facultatif mais très utile)
#
# Argo Rollouts vs ArgoCD (ne pas confondre) :
#   ArgoCD      → synchronise Git → cluster (GitOps, étape 09)
#   Argo Rollouts → gère les stratégies de déploiement (canary, blue/green)
#   Les deux peuvent fonctionner ensemble : ArgoCD déploie un Rollout,
#   Argo Rollouts gère la progression.
#
# Usage :
#   bash scripts/rollout-install.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ARGO_ROLLOUTS_VERSION="v1.7.2"
NAMESPACE="traiteur"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }

# ══════════════════════════════════════════════════════════════════════════════
# Étape 1 — Vérifier le cluster
# ══════════════════════════════════════════════════════════════════════════════
info "Étape 1 : Vérification du cluster kind..."
if ! kubectl cluster-info --context kind-traiteur >/dev/null 2>&1; then
  warn "Cluster 'traiteur' non trouvé. Lancer d'abord : make helm-install"
  exit 1
fi
success "Cluster kind-traiteur actif"

# ══════════════════════════════════════════════════════════════════════════════
# Étape 2 — Installer Argo Rollouts (contrôleur + CRDs)
# ══════════════════════════════════════════════════════════════════════════════
info "Étape 2 : Installation d'Argo Rollouts ${ARGO_ROLLOUTS_VERSION}..."

if kubectl get namespace argo-rollouts >/dev/null 2>&1; then
  warn "Argo Rollouts déjà installé (namespace argo-rollouts existe)"
  info "Pour réinstaller : kubectl delete namespace argo-rollouts"
else
  kubectl create namespace argo-rollouts

  # Manifeste officiel Argo Rollouts
  kubectl apply -n argo-rollouts \
    -f "https://github.com/argoproj/argo-rollouts/releases/download/${ARGO_ROLLOUTS_VERSION}/install.yaml"

  success "Argo Rollouts installé"
fi

# ══════════════════════════════════════════════════════════════════════════════
# Étape 3 — Attendre que le contrôleur soit READY
# ══════════════════════════════════════════════════════════════════════════════
info "Étape 3 : Attente du contrôleur Argo Rollouts..."
kubectl rollout status deployment/argo-rollouts \
  -n argo-rollouts \
  --timeout=120s
success "Contrôleur Argo Rollouts READY"

# ══════════════════════════════════════════════════════════════════════════════
# Étape 4 — Installer le plugin kubectl argo rollouts
# ══════════════════════════════════════════════════════════════════════════════
info "Étape 4 : Installation du plugin kubectl argo rollouts..."

if kubectl argo rollouts version >/dev/null 2>&1; then
  success "Plugin kubectl argo rollouts déjà installé : $(kubectl argo rollouts version --short)"
else
  OS=$(uname -s | tr '[:upper:]' '[:lower:]')
  ARCH=$(uname -m)
  [[ "$ARCH" == "x86_64" ]] && ARCH="amd64"
  [[ "$ARCH" == "aarch64" ]] && ARCH="arm64"

  PLUGIN_URL="https://github.com/argoproj/argo-rollouts/releases/download/${ARGO_ROLLOUTS_VERSION}/kubectl-argo-rollouts-${OS}-${ARCH}"

  if curl -fsSL "$PLUGIN_URL" -o /tmp/kubectl-argo-rollouts 2>/dev/null; then
    chmod +x /tmp/kubectl-argo-rollouts
    sudo mv /tmp/kubectl-argo-rollouts /usr/local/bin/kubectl-argo-rollouts 2>/dev/null || \
      mv /tmp/kubectl-argo-rollouts "$HOME/.local/bin/kubectl-argo-rollouts" 2>/dev/null || \
      warn "Impossible d'installer globalement. Copier manuellement : mv /tmp/kubectl-argo-rollouts /usr/local/bin/"
    success "Plugin installé"
  else
    warn "Plugin non disponible pour ${OS}/${ARCH}. Utiliser la commande kubectl alternative :"
    warn "  kubectl get rollout agent -n ${NAMESPACE} -o yaml"
  fi
fi

# ══════════════════════════════════════════════════════════════════════════════
# Étape 5 — Déployer l'AnalysisTemplate
# ══════════════════════════════════════════════════════════════════════════════
info "Étape 5 : Déploiement de l'AnalysisTemplate..."
kubectl apply -f argo-rollouts/analysis-template.yaml
success "AnalysisTemplate 'traiteur-availability' déployé"

# ══════════════════════════════════════════════════════════════════════════════
# Étape 6 — Activer le mode Rollout dans Helm
# ══════════════════════════════════════════════════════════════════════════════
info "Étape 6 : Activation du mode Rollout dans Helm..."
info "(Cela remplace le Deployment agent par un Rollout Argo)"

helm upgrade traiteur ./chart \
  --reuse-values \
  --set rollout.enabled=true \
  --namespace "${NAMESPACE}" \
  --wait --timeout 5m

success "Mode Rollout activé"

# ══════════════════════════════════════════════════════════════════════════════
# Résumé
# ══════════════════════════════════════════════════════════════════════════════
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
success "Argo Rollouts installé et configuré"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  État du rollout :"
if kubectl argo rollouts version >/dev/null 2>&1; then
  kubectl argo rollouts get rollout agent -n "${NAMESPACE}" 2>/dev/null || \
    kubectl get rollout agent -n "${NAMESPACE}" 2>/dev/null || true
fi
echo ""
echo "  Commandes utiles :"
echo "    make rollout-status           → état actuel du rollout"
echo "    make rollout-demo             → démo d'un déploiement progressif"
echo "    make rollout-break            → démo de rollback automatique"
echo ""
echo "  Commandes kubectl directes :"
echo "    kubectl argo rollouts get rollout agent -n ${NAMESPACE} --watch"
echo "    kubectl argo rollouts set image rollout/agent agent=traiteur-agent:v2 -n ${NAMESPACE}"
echo "    kubectl argo rollouts promote agent -n ${NAMESPACE}   # promotion manuelle"
echo "    kubectl argo rollouts abort agent -n ${NAMESPACE}     # rollback manuel"
echo ""
