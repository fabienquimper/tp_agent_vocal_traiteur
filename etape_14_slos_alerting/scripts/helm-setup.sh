#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# helm-setup.sh — Installation Helm + déploiement du chart Traiteur
# Étape 13 : Helm
#
# Ce script remplace k8s-setup.sh pour les étapes Helm.
# Différence clé :
#   Avant (kubectl apply) : appliquer 15+ fichiers YAML séparément
#   Après (helm install)  : une commande installe TOUT le chart
#
# Usage :
#   bash scripts/helm-setup.sh              # déploiement production (défauts)
#   bash scripts/helm-setup.sh staging      # déploiement staging
#   bash scripts/helm-setup.sh ci           # déploiement CI (sans Ollama)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ENV="${1:-production}"
CLUSTER="traiteur"
NAMESPACE="traiteur"
RELEASE="traiteur"
CHART_DIR="./chart"

# ── Couleurs ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }

# ══════════════════════════════════════════════════════════════════════════════
# Étape 1 — Vérifier / installer Helm
# ══════════════════════════════════════════════════════════════════════════════
info "Étape 1 : Vérification de Helm..."
if ! command -v helm &>/dev/null; then
  warn "Helm non trouvé. Installation..."
  # Installation officielle Helm (Linux/macOS)
  curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
  success "Helm installé : $(helm version --short)"
else
  success "Helm déjà installé : $(helm version --short)"
fi

# Optionnel : helm-diff (montre les diffs avant upgrade)
if ! helm plugin list 2>/dev/null | grep -q "diff"; then
  info "Installation du plugin helm-diff (optionnel)..."
  helm plugin install https://github.com/databus23/helm-diff 2>/dev/null || \
    warn "helm-diff non installé (optionnel)"
fi

# ══════════════════════════════════════════════════════════════════════════════
# Étape 2 — Vérifier le cluster kind
# ══════════════════════════════════════════════════════════════════════════════
info "Étape 2 : Vérification du cluster kind..."
if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER}$"; then
  info "Cluster '${CLUSTER}' non trouvé. Création..."
  kind create cluster --name "${CLUSTER}" --config kind-config.yaml
  success "Cluster '${CLUSTER}' créé"
else
  success "Cluster '${CLUSTER}' déjà actif"
fi

kubectl cluster-info --context "kind-${CLUSTER}" >/dev/null 2>&1

# ══════════════════════════════════════════════════════════════════════════════
# Étape 3 — Build + chargement des images Docker
# ══════════════════════════════════════════════════════════════════════════════
info "Étape 3 : Build des images Docker..."
docker build -t traiteur-agent:latest ./services/agent --quiet
docker build -t traiteur-stt:latest   ./services/stt   --quiet
docker build -t traiteur-tts:latest   ./services/tts   --quiet
docker build -t traiteur-ui:latest    ./ui              --quiet

if [[ "${ENV}" == "ci" ]]; then
  docker build -t mock-ollama:ci ./mock-ollama --quiet
  success "Images construites (CI : +mock-ollama)"
else
  success "Images construites"
fi

info "Chargement des images dans kind..."
kind load docker-image traiteur-agent:latest --name "${CLUSTER}"
kind load docker-image traiteur-stt:latest   --name "${CLUSTER}"
kind load docker-image traiteur-tts:latest   --name "${CLUSTER}"
kind load docker-image traiteur-ui:latest    --name "${CLUSTER}"

if [[ "${ENV}" == "ci" ]]; then
  kind load docker-image mock-ollama:ci --name "${CLUSTER}"
fi
success "Images chargées dans le cluster"

# ══════════════════════════════════════════════════════════════════════════════
# Étape 4 — Namespace
# ══════════════════════════════════════════════════════════════════════════════
info "Étape 4 : Namespace ${NAMESPACE}..."
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

# ══════════════════════════════════════════════════════════════════════════════
# Étape 5 — ConfigMaps de données (data/ et eval/)
# ══════════════════════════════════════════════════════════════════════════════
info "Étape 5 : ConfigMaps de données (data/ et eval/)..."
kubectl create configmap traiteur-data \
  --from-file=data/ -n "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -
kubectl create configmap traiteur-eval \
  --from-file=eval/ -n "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -
success "ConfigMaps de données créées"

# ══════════════════════════════════════════════════════════════════════════════
# Étape 6 — helm install / upgrade
#
# Pourquoi "upgrade --install" et pas "install" ?
#   upgrade --install = idempotent :
#     - 1er appel → install
#     - appels suivants → upgrade
#   C'est la commande à utiliser dans les pipelines CI/CD.
# ══════════════════════════════════════════════════════════════════════════════
info "Étape 6 : helm upgrade --install (env=${ENV})..."

VALUES_FLAGS="-f ${CHART_DIR}/values.yaml"
case "${ENV}" in
  staging)
    VALUES_FLAGS+=" -f ${CHART_DIR}/values.staging.yaml"
    info "Surcharge : values.staging.yaml"
    ;;
  ci)
    VALUES_FLAGS+=" -f ${CHART_DIR}/values.ci.yaml"
    info "Surcharge : values.ci.yaml"
    # Déployer le mock-ollama séparément (hors du chart Helm)
    kubectl apply -f k8s/ci/mock-ollama.yaml
    ;;
esac

# La commande magique Helm :
#   helm upgrade --install = installe si absent, upgrade si présent
#   --atomic = rollback auto si l'install échoue (ne laisse pas un état bancal)
#   --timeout = temps max pour que les pods soient READY
#   --wait = attend que tous les pods soient READY avant de retourner
helm upgrade --install "${RELEASE}" "${CHART_DIR}" \
  ${VALUES_FLAGS} \
  --namespace "${NAMESPACE}" \
  --atomic \
  --timeout 10m \
  --wait

success "Helm install/upgrade terminé"

# ══════════════════════════════════════════════════════════════════════════════
# Étape 7 — Vérification
# ══════════════════════════════════════════════════════════════════════════════
info "Étape 7 : Vérification de l'état des pods..."
kubectl get pods -n "${NAMESPACE}"
echo ""

# Afficher les releases Helm
echo "=== Releases Helm ==="
helm list -n "${NAMESPACE}"
echo ""

# ══════════════════════════════════════════════════════════════════════════════
# Résumé
# ══════════════════════════════════════════════════════════════════════════════
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
success "Déploiement Helm terminé (env=${ENV})"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Prochaines étapes :"
if [[ "${ENV}" != "ci" ]]; then
  echo "    make k8s-init-ollama   # télécharger Mistral (~4 GB)"
fi
echo "    make test-smoke        # tests de santé"
echo "    curl http://localhost:8000/health"
echo ""
echo "  Commandes Helm utiles :"
echo "    helm list -n ${NAMESPACE}                           # releases actives"
echo "    helm history ${RELEASE} -n ${NAMESPACE}             # historique"
echo "    helm get values ${RELEASE} -n ${NAMESPACE}          # valeurs actives"
echo "    helm rollback ${RELEASE} -n ${NAMESPACE}            # rollback"
echo ""
echo "  Changer l'env STT (sans redéploiement complet) :"
echo "    helm upgrade ${RELEASE} ${CHART_DIR} --set stt.activeColor=green"
echo ""
