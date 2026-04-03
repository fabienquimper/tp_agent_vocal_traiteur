#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# k8s-stt-switch.sh — Blue/Green switch STT en Kubernetes
#
# Mécanisme K8s vs nginx (étape 03) :
#   Nginx   : copie un fichier de config + reload nginx (dans le conteneur)
#   K8s     : patch le selector du Service → K8s redirige le trafic instantanément
#
# Le Service K8s maintient une liste de "endpoints" (pods qui matchent le selector).
# Quand on change le selector, K8s met à jour la liste d'endpoints en < 1s.
# Toutes les nouvelles connexions vont vers les pods du nouveau color.
# Les connexions en cours sur l'ancien color se terminent normalement.
#
# Usage :
#   bash scripts/k8s-stt-switch.sh blue
#   bash scripts/k8s-stt-switch.sh green
#   make k8s-stt-switch-green
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

COLOR="${1:-}"
NAMESPACE="traiteur"

if [ "$COLOR" != "blue" ] && [ "$COLOR" != "green" ]; then
    echo "Usage: $0 [blue|green]"
    echo ""
    echo "  blue  = Whisper base  (plus rapide)"
    echo "  green = Whisper small (plus précis)"
    exit 1
fi

MODEL=$([ "$COLOR" = "blue" ] && echo "base" || echo "small")

echo "=== STT Blue/Green switch : → $COLOR (Whisper $MODEL) ==="
echo ""

# Vérifier que le pod cible est READY
echo "Vérification que stt-${COLOR} est Ready..."
READY=$(kubectl get deployment "stt-${COLOR}" -n "${NAMESPACE}" \
    -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
if [ "${READY:-0}" = "0" ]; then
    echo "✗ stt-${COLOR} n'est pas prêt (readyReplicas=0)"
    echo "  État : $(kubectl get deployment "stt-${COLOR}" -n "${NAMESPACE}" \
        -o jsonpath='{.status.conditions[?(@.type=="Available")].message}')"
    exit 1
fi
echo "✓ stt-${COLOR} est Ready ($READY replica(s))"
echo ""

# Le patch K8s — change le selector du Service
echo "Patch du Service stt-router → sélectionne les pods color=$COLOR..."
kubectl patch service stt-router -n "${NAMESPACE}" \
    -p "{\"spec\":{\"selector\":{\"app\":\"stt\",\"color\":\"${COLOR}\"}}}"

# Mise à jour de l'annotation (informative)
kubectl annotate service stt-router -n "${NAMESPACE}" \
    "traiteur/active-color=${COLOR}" --overwrite > /dev/null

echo ""
echo "✓ Switch effectué !"
echo ""
echo "Sélecteur actif :"
kubectl get service stt-router -n "${NAMESPACE}" \
    -o jsonpath='  app={.spec.selector.app}, color={.spec.selector.color}' && echo ""
echo ""
echo "Vérification (endpoint actif) :"
kubectl get endpoints stt-router -n "${NAMESPACE}"
