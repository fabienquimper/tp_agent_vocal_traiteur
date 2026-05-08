#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# security-setup.sh — Applique les politiques de sécurité K8s
# Étape 12 : Sécurité (Network Policies + RBAC)
#
# Ce script :
#   1. Installe kube-network-policies (support NetworkPolicy avec kindnet)
#   2. Applique les NetworkPolicies (Zero Trust)
#   3. Applique le RBAC (ServiceAccounts + Roles + Bindings)
#   4. Redémarre l'agent avec son nouveau ServiceAccount
#   5. Vérifie que les règles sont en place
#
# NOTE : kind utilise "kindnet" qui ne supporte pas les NetworkPolicies nativement.
#        kube-network-policies (kubernetes-sigs) est un controller userspace
#        qui implémente les NetworkPolicies au-dessus de kindnet.
#        En production : Calico, Cilium ou Antrea fournissent ce support nativement.
#
# Usage :
#   bash scripts/security-setup.sh
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

NS="traiteur"
CLUSTER="traiteur"
KNP_VERSION="v0.3.6"   # kube-network-policies

echo ""
echo "════════════════════════════════════════════════════════"
echo "  Security Setup — Traiteur Dupont (étape 12)"
echo "  Zero Trust : Network Policies + RBAC"
echo "════════════════════════════════════════════════════════"

# ── Pré-requis ────────────────────────────────────────────────────────────────
if ! kubectl cluster-info --context "kind-${CLUSTER}" > /dev/null 2>&1; then
    fail "Cluster kind '${CLUSTER}' non trouvé. Lancer d'abord : make k8s-up"
fi
ok "Cluster kind '${CLUSTER}' actif"

# ── Étape 1 : kube-network-policies (support NetworkPolicy avec kindnet) ──────
step "1/4 — Installation kube-network-policies"

if kubectl get daemonset kube-network-policies -n kube-system > /dev/null 2>&1; then
    ok "kube-network-policies déjà installé"
else
    info "Installation de kube-network-policies ${KNP_VERSION}..."
    info "(Ajoute le support des NetworkPolicies au CNI kindnet de kind)"
    kubectl apply -f \
        "https://raw.githubusercontent.com/kubernetes-sigs/kube-network-policies/refs/tags/${KNP_VERSION}/config/install.yaml"

    info "Attente que le DaemonSet soit prêt..."
    kubectl rollout status daemonset/kube-network-policies \
        -n kube-system --timeout=120s
    ok "kube-network-policies prêt"
fi

# ── Étape 2 : RBAC (avant NetworkPolicies pour que l'agent démarre correctement) ──
step "2/4 — Application du RBAC"

kubectl apply -f k8s/rbac/rbac.yaml
ok "ServiceAccounts, Roles, RoleBindings appliqués"

# Vérification
echo ""
info "ServiceAccounts créés :"
kubectl get serviceaccount -n "$NS" | grep -E "agent-sa|prometheus-sa" || true
echo ""
info "Roles créés :"
kubectl get role -n "$NS" || true

# ── Étape 3 : NetworkPolicies ─────────────────────────────────────────────────
step "3/4 — Application des NetworkPolicies (Zero Trust)"

kubectl apply -f k8s/security/network-policies.yaml
ok "NetworkPolicies appliquées"

# Afficher les policies créées
echo ""
info "NetworkPolicies actives :"
kubectl get networkpolicy -n "$NS" -o custom-columns="NAME:.metadata.name,POD-SELECTOR:.spec.podSelector.matchLabels"

# ── Étape 4 : Redémarrage de l'agent avec le nouveau SA ───────────────────────
step "4/4 — Redémarrage de l'agent (nouveau ServiceAccount)"

info "Redémarrage du Deployment agent (applique serviceAccountName: agent-sa)..."
kubectl apply -f k8s/agent.yaml
kubectl rollout restart deployment/agent -n "$NS"
kubectl rollout status deployment/agent -n "$NS" --timeout=300s
ok "Agent redémarré avec serviceAccountName=agent-sa"

# ── Résumé ────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
ok "Politiques de sécurité appliquées !"
echo ""
echo "  Vérifications :"
echo "    make security-check   → teste les flux autorisés et bloqués"
echo "    make rbac-audit       → vérifie les permissions du SA agent"
echo ""
echo "  Ressources créées :"
echo "    NetworkPolicies → $(kubectl get networkpolicy -n $NS --no-headers 2>/dev/null | wc -l) policies dans namespace traiteur"
echo "    ServiceAccounts → agent-sa, prometheus-sa"
echo "    Roles           → agent-role, prometheus-role"
echo "════════════════════════════════════════════════════════"
