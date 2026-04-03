#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# loki-demo.sh — Démonstration des 3 piliers de l'observabilité
# Étape 16 : Loki + Logs
#
# Ce script démontre :
#   1. La collecte automatique des logs par Promtail
#   2. La recherche de logs dans Loki via LogQL
#   3. La corrélation logs ↔ traces ↔ métriques dans Grafana
#
# Les 3 piliers en pratique :
#   Un incident arrive → tu ouvres Grafana
#   1. MÉTRIQUES  : "La disponibilité a chuté à 85% à 14h32"
#   2. TRACES     : "La p95 latence a spiké → trace abc123 montre que c'est le LLM"
#   3. LOGS       : "Les logs agent à 14h32 montrent : OllamaError: timeout after 30s"
#
# Usage :
#   bash scripts/loki-demo.sh              → démo complète
#   bash scripts/loki-demo.sh --query      → requêtes LogQL seules
#   bash scripts/loki-demo.sh --check      → vérifier que Loki collecte des logs
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

LOKI_URL="${LOKI_URL:-http://localhost:3100}"
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3001}"
AGENT_URL="${AGENT_URL:-http://localhost:8000}"
NAMESPACE="${NAMESPACE:-traiteur}"
MODE="${1:-}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'
BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }

# ── Requête LogQL vers l'API Loki ─────────────────────────────────────────────
loki_query() {
  local query="$1"
  local limit="${2:-20}"
  local since="${3:-1h}"

  curl -s "${LOKI_URL}/loki/api/v1/query_range" \
    --data-urlencode "query=${query}" \
    --data-urlencode "limit=${limit}" \
    --data-urlencode "start=$(date -d "-${since}" +%s)000000000" \
    --data-urlencode "end=$(date +%s)000000000" \
    2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
streams = data.get('data', {}).get('result', [])
count = sum(len(s.get('values', [])) for s in streams)
print(f'Résultats : {count} lignes de log')
for stream in streams[:3]:
    labels = stream.get('stream', {})
    print(f'  Labels: {labels}')
    for ts, line in stream.get('values', [])[:5]:
        # Afficher les 120 premiers caractères
        print(f'  {line[:120]}')
    if len(stream.get('values', [])) > 5:
        print(f'  ... ({len(stream[\"values\"])-5} de plus)')
" 2>/dev/null || echo "  (Loki inaccessible sur ${LOKI_URL})"
}

# ── Vérifier que Loki collecte des logs ───────────────────────────────────────
check_loki() {
  echo ""
  info "Vérification de Loki..."

  # Tester la santé
  if curl -s --fail "${LOKI_URL}/ready" >/dev/null 2>&1; then
    success "Loki actif sur ${LOKI_URL}"
  else
    warn "Loki inaccessible. Vérifier : kubectl get pods -n ${NAMESPACE} -l app=loki"
    return 1
  fi

  # Lister les labels disponibles
  echo ""
  info "Labels disponibles dans Loki :"
  curl -s "${LOKI_URL}/loki/api/v1/labels" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
labels = data.get('data', [])
print('  ' + ', '.join(labels[:20]))
" 2>/dev/null || echo "  (aucun label encore)"

  # Lister les apps indexées
  echo ""
  info "Applications dont les logs sont collectés :"
  curl -s "${LOKI_URL}/loki/api/v1/label/app/values" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
apps = data.get('data', [])
for app in apps:
    print(f'  app={app}')
" 2>/dev/null || echo "  (Promtail n'a pas encore envoyé de logs)"
}

# ── Requêtes LogQL de démonstration ──────────────────────────────────────────
demo_queries() {
  echo ""
  echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}  LogQL — Langage de requête Loki${NC}"
  echo -e "${BOLD}  (comme PromQL mais pour les logs)${NC}"
  echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

  echo ""
  echo -e "${BOLD}  Requête 1 : Tous les logs de l'agent${NC}"
  echo "  LogQL : {app=\"agent\", namespace=\"${NAMESPACE}\"}"
  loki_query "{app=\"agent\", namespace=\"${NAMESPACE}\"}" 10 30m

  echo ""
  echo -e "${BOLD}  Requête 2 : Logs d'erreur uniquement${NC}"
  echo "  LogQL : {app=\"agent\"} |= \"error\""
  loki_query "{app=\"agent\", namespace=\"${NAMESPACE}\"} |= \"error\"" 10 30m

  echo ""
  echo -e "${BOLD}  Requête 3 : Logs LLM (appels Ollama)${NC}"
  echo "  LogQL : {app=\"agent\"} |= \"ollama\""
  loki_query "{app=\"agent\", namespace=\"${NAMESPACE}\"} |= \"ollama\"" 10 30m

  echo ""
  echo -e "${BOLD}  Requête 4 : Logs RAG rebuild${NC}"
  echo "  LogQL : {app=\"agent\"} |= \"rag\""
  loki_query "{app=\"agent\", namespace=\"${NAMESPACE}\"} |= \"rag\"" 5 1h

  echo ""
  echo -e "${BOLD}  Requête 5 : Taux d'erreur (LogQL agrégé)${NC}"
  echo "  LogQL : sum(rate({app=\"agent\"} |= \"error\" [5m]))"
  echo "  → Cette requête retourne un nombre (comme PromQL)"
  echo "  → Utilisable dans un panel Grafana"

  echo ""
  echo -e "${BOLD}  Syntaxe LogQL de base :${NC}"
  echo "  {app=\"agent\"}              → sélection par label (obligatoire)"
  echo "  {app=\"agent\"} |= \"error\"  → filtre par contenu (contient)"
  echo "  {app=\"agent\"} != \"debug\"  → filtre négatif"
  echo "  {app=\"agent\"} |~ \"RAG.*\"  → regex"
  echo "  {app=\"agent\"} | json      → parser les logs JSON"
  echo "  {app=\"agent\"} | json | level=\"error\" → filtrer sur champ JSON"
}

# ── Démo corrélation logs ↔ traces ────────────────────────────────────────────
demo_correlation() {
  echo ""
  echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}  Corrélation Logs ↔ Traces ↔ Métriques${NC}"
  echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  echo "  Dans Grafana, les 3 piliers sont corrélés :"
  echo ""
  echo "  1. MÉTRIQUE : taux d'erreur spike à 14h32"
  echo "     → Grafana : panel Prometheus → cliquer sur le point du spike"
  echo ""
  echo "  2. TRACE : cliquer sur 'Explore in Jaeger'"
  echo "     → Voir quelle opération est lente (langgraph.invoke ? rag.search ?)"
  echo "     → La trace contient un trace_id (ex: abc123def456)"
  echo ""
  echo "  3. LOG : rechercher ce trace_id dans Loki"
  echo '     LogQL : {app="agent"} |= "abc123def456"'
  echo "     → Voir exactement quelle erreur Python a été levée"
  echo "     → Avec le stack trace complet"
  echo ""
  echo -e "  ${BOLD}Derived Fields (configuration dans grafana-datasources ConfigMap) :${NC}"
  echo "  Quand Loki trouve 'trace_id' dans un log JSON,"
  echo "  Grafana ajoute un lien cliquable → directement dans Jaeger."
  echo "  → Plus besoin de copier-coller le trace_id !"
  echo ""

  # Envoyer quelques requêtes pour générer des traces + logs corrélés
  info "Génération de trafic (logs + traces corrélés)..."
  for i in 1 2 3; do
    curl -s -X POST "${AGENT_URL}/api/text" \
      -H "Content-Type: application/json" \
      -d '{"text": "Quel est votre menu du jour ?", "skip_tts": true}' \
      >/dev/null 2>&1 || true
    sleep 1
  done
  success "Requêtes envoyées. Les logs apparaîtront dans Loki dans ~30s."

  echo ""
  echo "  Explorer dans Grafana :"
  echo "    1. ${GRAFANA_URL} → Explore"
  echo "    2. Datasource : Loki"
  echo '    3. Label filters : app = agent'
  echo "    4. Chercher les logs des requêtes qu'on vient d'envoyer"
  echo "    5. Cliquer sur un log avec trace_id → lien vers Jaeger"
}

# ── Grafana Explore guide ─────────────────────────────────────────────────────
grafana_guide() {
  echo ""
  echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}  Guide Grafana Explore — Les 3 piliers en 5 minutes${NC}"
  echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  echo "  Ouvrir : ${GRAFANA_URL}/explore"
  echo ""
  echo "  ── Pilier 1 : Métriques (Prometheus) ──────────────────────────────"
  echo "  Datasource : Prometheus"
  echo "  Query : conversations_total"
  echo "  → Voir le volume de conversations par statut"
  echo ""
  echo "  ── Pilier 2 : Traces (Jaeger) ──────────────────────────────────────"
  echo "  Datasource : Jaeger"
  echo "  Service : traiteur-agent"
  echo "  → Voir les spans de chaque requête"
  echo "  → Identifier les goulots d'étranglement"
  echo ""
  echo "  ── Pilier 3 : Logs (Loki) ──────────────────────────────────────────"
  echo '  Datasource : Loki'
  echo '  Label filter : app = agent'
  echo '  → Voir tous les logs en temps réel'
  echo '  → Filtrer : |= "error" pour les erreurs seulement'
  echo ""
  echo "  ── Corrélation (la magie) ───────────────────────────────────────────"
  echo '  Dans un log avec trace_id → cliquer sur "TraceID"'
  echo "  → Grafana ouvre la trace dans Jaeger automatiquement"
  echo "  Inverse : dans Jaeger → 'Logs for this span' → Loki"
  echo ""
  echo "  ── Split view (voir 2 piliers côte à côte) ──────────────────────────"
  echo "  Grafana Explore → icône 'Split' en haut à droite"
  echo "  Gauche : Prometheus (métriques)"
  echo "  Droite : Loki (logs) avec le même time range"
  echo ""
}

# ── Main ──────────────────────────────────────────────────────────────────────
case "$MODE" in
  --query)    demo_queries ;;
  --check)    check_loki ;;
  --grafana)  grafana_guide ;;
  *)
    echo ""
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}  Démo : Les 3 piliers de l'observabilité${NC}"
    echo -e "${BOLD}  Métriques (Prometheus) + Traces (Jaeger) + Logs (Loki)${NC}"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    check_loki
    demo_queries
    demo_correlation
    grafana_guide
    ;;
esac
