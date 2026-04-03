#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# rollout-demo.sh — Démonstration d'un déploiement progressif Argo Rollouts
# Étape 15 : Progressive Delivery automatisé
#
# Scénarios disponibles :
#   bash scripts/rollout-demo.sh              → déploiement progressif réussi
#   bash scripts/rollout-demo.sh --break      → déploiement cassé → rollback auto
#   bash scripts/rollout-demo.sh --manual     → pause manuelle + promotion manuelle
#   bash scripts/rollout-demo.sh --status     → état actuel du rollout
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

NAMESPACE="${NAMESPACE:-traiteur}"
AGENT_URL="${AGENT_URL:-http://localhost:8000}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
MODE="${1:-}"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()    { echo -e "${RED}[FAIL]${NC} $*"; }

# ── Vérifier les prérequis ────────────────────────────────────────────────────
check_prereqs() {
  if ! kubectl get rollout agent -n "${NAMESPACE}" >/dev/null 2>&1; then
    warn "Rollout 'agent' non trouvé. Lancer d'abord :"
    warn "  bash scripts/rollout-install.sh"
    exit 1
  fi

  if ! kubectl get analysistemplate traiteur-availability -n "${NAMESPACE}" >/dev/null 2>&1; then
    warn "AnalysisTemplate 'traiteur-availability' non trouvé."
    warn "  kubectl apply -f argo-rollouts/analysis-template.yaml"
    exit 1
  fi
}

# ── Afficher l'état du rollout ────────────────────────────────────────────────
show_status() {
  echo ""
  echo -e "${BOLD}═══════════════════════════════════════════════════${NC}"
  echo -e "${BOLD}  État du Rollout — $(date '+%H:%M:%S')${NC}"
  echo -e "${BOLD}═══════════════════════════════════════════════════${NC}"

  if kubectl argo rollouts version >/dev/null 2>&1; then
    kubectl argo rollouts get rollout agent -n "${NAMESPACE}" 2>/dev/null || \
      kubectl get rollout agent -n "${NAMESPACE}" -o yaml | grep -A 30 "status:" | head -30
  else
    # Fallback sans plugin
    echo ""
    echo "  Rollout :"
    kubectl get rollout agent -n "${NAMESPACE}" \
      -o custom-columns="NAME:.metadata.name,DESIRED:.spec.replicas,READY:.status.readyReplicas,REVISION:.status.currentPodHash"
    echo ""
    echo "  ReplicaSets (stable vs canary) :"
    kubectl get replicaset -n "${NAMESPACE}" -l app=agent \
      -o custom-columns="NAME:.metadata.name,DESIRED:.spec.replicas,READY:.status.readyReplicas,IMAGE:.spec.template.spec.containers[0].image"
    echo ""
    echo "  AnalysisRuns actifs :"
    kubectl get analysisrun -n "${NAMESPACE}" 2>/dev/null | head -10 || echo "  (aucun)"
  fi
  echo ""
}

# ── Envoyer du trafic pour alimenter Prometheus ───────────────────────────────
generate_traffic() {
  local n="${1:-20}"
  local success_rate="${2:-100}"  # % de requêtes réussies
  info "Génération de ${n} requêtes (taux succès : ${success_rate}%)..."

  for i in $(seq 1 $n); do
    if (( RANDOM % 100 < success_rate )); then
      curl -s -X POST "${AGENT_URL}/api/text" \
        -H "Content-Type: application/json" \
        -d '{"text": "Que proposez-vous comme menu ?", "skip_tts": true}' \
        >/dev/null 2>&1 || true
    else
      # Requête qui va probablement échouer
      curl -s -X POST "${AGENT_URL}/api/text" \
        -H "Content-Type: application/json" \
        -d '{"text": "FORCE_ERROR_TRIGGER", "skip_tts": true, "session_id": "bad-session"}' \
        >/dev/null 2>&1 || true
    fi
    sleep 0.2
  done
}

# ─────────────────────────────────────────────────────────────────────────────
# Scénario 1 : Déploiement progressif réussi
# ─────────────────────────────────────────────────────────────────────────────
demo_success() {
  echo ""
  echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}  Démo : Déploiement progressif RÉUSSI${NC}"
  echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  echo "  Scénario :"
  echo "    1. Déclencher un nouveau rollout (changer une env var)"
  echo "    2. Observer la progression : 20% → analyse → 50% → analyse → 80% → 100%"
  echo "    3. L'analyse Prometheus valide chaque étape"
  echo "    4. Promotion automatique finale"
  echo ""

  info "Étape 1 : Vérification de l'état initial"
  show_status

  info "Étape 2 : Génération de trafic de base (pour Prometheus)"
  generate_traffic 30 100

  info "Étape 3 : Déclenchement du rollout"
  info "(Simulation : on change APP_ENV de 'production' à 'production-v2')"
  echo ""

  # Déclencher le rollout en changeant une annotation (simule un changement d'image)
  kubectl patch rollout agent -n "${NAMESPACE}" \
    --type=json \
    -p='[{"op": "replace", "path": "/spec/template/metadata/annotations", "value": {"rollout-trigger": "'$(date +%s)'"}}]' \
    2>/dev/null || \
  kubectl argo rollouts set image rollout/agent \
    agent=traiteur-agent:latest \
    -n "${NAMESPACE}" 2>/dev/null || \
  warn "Déclencher manuellement : kubectl argo rollouts restart agent -n ${NAMESPACE}"

  echo ""
  info "Étape 4 : Surveillance du rollout (durée estimée : ~6 minutes)"
  echo ""
  echo "  Commandes utiles dans un autre terminal :"
  echo "    kubectl argo rollouts get rollout agent -n ${NAMESPACE} --watch"
  echo "    kubectl get analysisrun -n ${NAMESPACE} --watch"
  echo "    make slo-watch"
  echo ""

  # Observer pendant max 8 minutes
  for step in 1 2 3 4 5 6 7 8; do
    sleep 60
    echo ""
    info "Minute ${step}/8 :"

    # Continuer à générer du trafic (pour que Prometheus ait des données)
    generate_traffic 10 100

    show_status

    # Vérifier si le rollout est terminé
    STATUS=$(kubectl get rollout agent -n "${NAMESPACE}" \
      -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")

    if [[ "$STATUS" == "Healthy" ]]; then
      success "Rollout terminé avec succès !"
      break
    elif [[ "$STATUS" == "Degraded" ]]; then
      fail "Rollout dégradé → rollback en cours..."
      break
    fi
  done

  echo ""
  show_status
  success "Démo terminée. Nouvelle version déployée progressivement."
}

# ─────────────────────────────────────────────────────────────────────────────
# Scénario 2 : Déploiement cassé → rollback automatique
# ─────────────────────────────────────────────────────────────────────────────
demo_break() {
  echo ""
  echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}  Démo : Déploiement cassé → ROLLBACK automatique${NC}"
  echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  echo "  Scénario :"
  echo "    1. Déclencher un rollout avec une image 'cassée'"
  echo "       (OLLAMA_BASE_URL pointant vers un service inexistant)"
  echo "    2. L'AnalysisRun détecte un taux d'erreur > 5%"
  echo "    3. Argo Rollouts annule automatiquement le rollout"
  echo "    4. Retour à 100% sur la version stable"
  echo ""

  info "Étape 1 : État initial (version stable)"
  show_status

  info "Étape 2 : Déploiement d'une version cassée..."
  warn "La nouvelle version pointe vers un Ollama inexistant → erreurs garanties"

  helm upgrade traiteur ./chart \
    --reuse-values \
    --set rollout.enabled=true \
    --set agent.env.appEnv=broken-v2 \
    --namespace "${NAMESPACE}" \
    --wait=false 2>/dev/null || \
  kubectl patch rollout agent -n "${NAMESPACE}" \
    --type=merge \
    -p='{"spec":{"template":{"spec":{"containers":[{"name":"agent","env":[{"name":"OLLAMA_BASE_URL","value":"http://nonexistent-ollama:11434"}]}]}}}}' \
    2>/dev/null || \
  warn "Impossible de patcher. Simuler manuellement l'erreur avec make alert-demo"

  echo ""
  info "Étape 3 : Génération de trafic (va générer des erreurs)"
  generate_traffic 30 20  # seulement 20% de succès → beaucoup d'erreurs

  echo ""
  info "Étape 4 : Surveillance — attendre le rollback automatique"
  echo ""

  for step in 1 2 3 4 5 6; do
    sleep 60
    echo ""
    info "Minute ${step}/6 :"
    generate_traffic 10 20  # continuer les erreurs

    show_status

    STATUS=$(kubectl get rollout agent -n "${NAMESPACE}" \
      -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")

    if [[ "$STATUS" == "Degraded" ]]; then
      warn "Rollout Degraded — rollback en cours..."
    elif [[ "$STATUS" == "Healthy" ]]; then
      success "Rollback terminé — version stable restaurée !"
      break
    fi
  done

  echo ""
  show_status
  success "Version stable restaurée automatiquement."
  info "C'est ça l'avantage d'Argo Rollouts : 0 intervention humaine pour le rollback."
}

# ─────────────────────────────────────────────────────────────────────────────
# Scénario 3 : Pause manuelle + promotion manuelle
# ─────────────────────────────────────────────────────────────────────────────
demo_manual() {
  echo ""
  echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}  Démo : Pause manuelle + promotion manuelle${NC}"
  echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  echo "  On peut aussi STOPPER automatiquement après chaque étape"
  echo "  et demander une validation humaine avant de continuer."
  echo ""
  echo "  Tip : ajouter '- pause: {}' dans les étapes du Rollout (sans duration)"
  echo "        → le rollout s'arrête et attend une commande 'promote'"
  echo ""

  show_status

  echo "  Commandes manuelles disponibles :"
  echo ""
  echo "    # Voir l'état détaillé"
  echo "    kubectl argo rollouts get rollout agent -n ${NAMESPACE}"
  echo ""
  echo "    # Promouvoir (avancer à l'étape suivante)"
  echo "    kubectl argo rollouts promote agent -n ${NAMESPACE}"
  echo ""
  echo "    # Annuler (rollback vers la version stable)"
  echo "    kubectl argo rollouts abort agent -n ${NAMESPACE}"
  echo ""
  echo "    # Retarder la pause actuelle (si une pause est en cours)"
  echo "    kubectl argo rollouts promote agent -n ${NAMESPACE} --full"
  echo ""
  echo "    # Voir les AnalysisRuns"
  echo "    kubectl get analysisrun -n ${NAMESPACE}"
  echo "    kubectl describe analysisrun <nom> -n ${NAMESPACE}"
}

# ── Main ──────────────────────────────────────────────────────────────────────
check_prereqs

case "$MODE" in
  --break)   demo_break ;;
  --manual)  demo_manual ;;
  --status)  show_status ;;
  *)         demo_success ;;
esac
