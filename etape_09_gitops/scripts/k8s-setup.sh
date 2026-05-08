#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# k8s-setup.sh — Déploiement complet sur le cluster kind
# Étape 07 : Kubernetes
#
# Ce script :
#   1. Crée le cluster kind (si absent)
#   2. Installe metrics-server (requis pour le HPA)
#   3. Build les images Docker locales
#   4. Charge les images dans le cluster kind
#   5. Crée les ConfigMaps depuis data/ et eval/
#   6. Applique tous les manifestes K8s
#   7. Attend que l'agent soit prêt
#
# Usage : bash scripts/k8s-setup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

CLUSTER_NAME="traiteur"
NAMESPACE="traiteur"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
step() { echo -e "\n${YELLOW}──${NC} Étape $*"; }
fail() { echo -e "${RED}✗${NC} $*"; exit 1; }

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  Déploiement Traiteur Dupont sur Kubernetes (kind)"
echo "════════════════════════════════════════════════════════════"

# ── Prérequis ─────────────────────────────────────────────────────────────────
step "0/7 : Vérification des prérequis..."
command -v kind    > /dev/null || fail "kind non trouvé. Installez : https://kind.sigs.k8s.io/docs/user/quick-start/"
command -v kubectl > /dev/null || fail "kubectl non trouvé. Installez : https://kubernetes.io/docs/tasks/tools/"
command -v docker  > /dev/null || fail "docker non trouvé"
ok "kind, kubectl, docker disponibles"

# ── Cluster kind ──────────────────────────────────────────────────────────────
step "1/7 : Création du cluster kind '${CLUSTER_NAME}'..."
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    ok "Cluster '${CLUSTER_NAME}' déjà existant — réutilisé"
else
    kind create cluster --config kind-config.yaml
    ok "Cluster '${CLUSTER_NAME}' créé"
fi

# Vérifier la connexion
kubectl cluster-info --context "kind-${CLUSTER_NAME}" > /dev/null
ok "Connexion au cluster OK"

# ── metrics-server (requis pour HPA) ─────────────────────────────────────────
step "2/7 : Installation de metrics-server (requis pour le HPA)..."
METRICS_RUNNING=$(kubectl get deployment metrics-server -n kube-system \
    --ignore-not-found -o jsonpath='{.metadata.name}' 2>/dev/null || echo "")

if [ -z "$METRICS_RUNNING" ]; then
    kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
    # Patch obligatoire pour kind : les kubelets utilisent des certificats auto-signés
    kubectl patch deployment metrics-server -n kube-system --type=json \
        -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
    ok "metrics-server installé et patché pour kind"
else
    ok "metrics-server déjà présent"
fi

# ── Build des images ──────────────────────────────────────────────────────────
step "3/7 : Build des images Docker locales..."
docker build -t traiteur-agent:latest ./services/agent --quiet && ok "traiteur-agent"
docker build -t traiteur-stt:latest   ./services/stt   --quiet && ok "traiteur-stt"
docker build -t traiteur-tts:latest   ./services/tts   --quiet && ok "traiteur-tts"
docker build -t traiteur-ui:latest    ./ui             --quiet && ok "traiteur-ui"

# ── Chargement dans kind ──────────────────────────────────────────────────────
step "4/7 : Chargement des images dans le cluster kind..."
# kind load copie l'image Docker dans le cluster (évite de la re-télécharger)
# Les pods utilisent ensuite imagePullPolicy: Never
kind load docker-image traiteur-agent:latest --name "${CLUSTER_NAME}" && ok "traiteur-agent chargé"
kind load docker-image traiteur-stt:latest   --name "${CLUSTER_NAME}" && ok "traiteur-stt chargé"
kind load docker-image traiteur-tts:latest   --name "${CLUSTER_NAME}" && ok "traiteur-tts chargé"
kind load docker-image traiteur-ui:latest    --name "${CLUSTER_NAME}" && ok "traiteur-ui chargé"

# ── Namespace et ConfigMap app ────────────────────────────────────────────────
step "5/7 : Application du namespace et des ConfigMaps..."
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-configmap.yaml

# ConfigMaps depuis les fichiers de données (dry-run + apply = idempotent)
kubectl create configmap traiteur-data \
    --from-file=data/ -n "${NAMESPACE}" \
    --dry-run=client -o yaml | kubectl apply -f -
ok "ConfigMap traiteur-data (data/*.txt)"

kubectl create configmap traiteur-eval \
    --from-file=eval/ -n "${NAMESPACE}" \
    --dry-run=client -o yaml | kubectl apply -f -
ok "ConfigMap traiteur-eval (eval/*.json)"

# ── Déploiement de tous les services ─────────────────────────────────────────
step "6/7 : Application de tous les manifestes K8s..."
# kubectl apply -f k8s/ applique tous les fichiers .yaml du dossier
kubectl apply -f k8s/
ok "Tous les manifestes appliqués"

# ── Attente ───────────────────────────────────────────────────────────────────
step "7/7 : Attente du démarrage des services..."
echo "  Ollama (peut prendre 2-3 minutes)..."
kubectl rollout status deployment/ollama -n "${NAMESPACE}" --timeout=300s
ok "Ollama prêt"

echo "  STT blue + green..."
kubectl rollout status deployment/stt-blue  -n "${NAMESPACE}" --timeout=300s
kubectl rollout status deployment/stt-green -n "${NAMESPACE}" --timeout=300s
ok "STT prêt"

echo "  TTS..."
kubectl rollout status deployment/tts -n "${NAMESPACE}" --timeout=120s
ok "TTS prêt"

echo "  Agent (ChromaDB rebuild au démarrage, ~60-90s)..."
kubectl rollout status deployment/agent -n "${NAMESPACE}" --timeout=300s
ok "Agent prêt"

echo ""
echo "════════════════════════════════════════════════════════════"
echo -e "  ${GREEN}✓ Cluster prêt !${NC}"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "  UI          → http://localhost:3000"
echo "  Agent       → http://localhost:8000"
echo "  Prometheus  → http://localhost:9090"
echo "  Grafana     → http://localhost:3001"
echo ""
echo "Prochaine étape : make k8s-init-ollama"
echo ""
echo "Commandes utiles :"
echo "  kubectl get pods -n traiteur            # état des pods"
echo "  kubectl get hpa  -n traiteur            # état du HPA"
echo "  kubectl top pods -n traiteur            # consommation CPU/RAM"
