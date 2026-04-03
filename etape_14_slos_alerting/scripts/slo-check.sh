#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# slo-check.sh — Tableau de bord SLO en temps réel
# Étape 14 : SLOs & Alerting
#
# Ce script interroge l'API Prometheus pour afficher :
#   - Le SLI disponibilité (taux de succès conversations)
#   - Le SLI latence (P50/P95/P99)
#   - Le SLI RAG hit rate
#   - L'error budget consommé (estimation sur la dernière heure)
#   - Les alertes actuellement actives
#
# Usage :
#   bash scripts/slo-check.sh              # vérification ponctuelle
#   bash scripts/slo-check.sh --watch      # actualisation toutes les 10s
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
ALERTMANAGER_URL="${ALERTMANAGER_URL:-http://localhost:9093}"
WATCH="${1:-}"

# SLO cibles
SLO_AVAILABILITY=0.99
SLO_LATENCY_P95=8.0
SLO_RAG_HIT_RATE=0.80

# ── Couleurs ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
fail() { echo -e "${RED}✗${NC} $*"; }
info() { echo -e "${BLUE}·${NC} $*"; }

# ── Fonction : requête Prometheus ─────────────────────────────────────────────
prom_query() {
  local query="$1"
  local result
  result=$(curl -s --fail \
    "${PROMETHEUS_URL}/api/v1/query" \
    --data-urlencode "query=${query}" \
    2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
results = data.get('data', {}).get('result', [])
if results:
    print(results[0]['value'][1])
else:
    print('N/A')
" 2>/dev/null || echo "N/A")
  echo "$result"
}

# ── Fonction : comparer float ─────────────────────────────────────────────────
float_compare() {
  # float_compare VALUE OPERATOR THRESHOLD → 0 (true) ou 1 (false)
  python3 -c "import sys, operator; ops={'>=':operator.ge,'<=':operator.le,'>':operator.gt,'<':operator.lt,'==':operator.eq}; v=float(sys.argv[1]); t=float(sys.argv[3]); sys.exit(0 if ops.get(sys.argv[2], operator.ge)(v, t) else 1)" "$1" "$2" "$3" 2>/dev/null
}

# ── Affichage principal ───────────────────────────────────────────────────────
display_slos() {
  clear
  echo ""
  echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}  Tableau de bord SLO — Traiteur Dupont Agent Vocal${NC}"
  echo -e "${BOLD}  $(date '+%Y-%m-%d %H:%M:%S')${NC}"
  echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""

  # ── SLO 1 : Disponibilité ─────────────────────────────────────────────────
  echo -e "${BOLD}  SLO 1 : Disponibilité (cible ≥ ${SLO_AVAILABILITY})${NC}"

  AVAIL=$(prom_query 'sum(rate(conversations_total{status="success"}[5m])) / sum(rate(conversations_total[5m]))')

  if [[ "$AVAIL" == "N/A" ]]; then
    info "  Pas encore de données (envoyer des requêtes d'abord)"
  else
    AVAIL_PCT=$(python3 -c "print(f'{float(\"$AVAIL\") * 100:.2f}%')" 2>/dev/null || echo "$AVAIL")
    if float_compare "$AVAIL" ">=" "$SLO_AVAILABILITY" 2>/dev/null; then
      ok "  Disponibilité : ${AVAIL_PCT}  (SLO respecté)"
    else
      fail "  Disponibilité : ${AVAIL_PCT}  (SLO VIOLÉ — cible : $(python3 -c "print(f'{${SLO_AVAILABILITY}*100:.0f}%')"))"
    fi
  fi

  # ── Error Budget ─────────────────────────────────────────────────────────
  ERR_RATE=$(prom_query 'sum(rate(conversations_total{status="error"}[1h])) / sum(rate(conversations_total[1h]))')
  if [[ "$ERR_RATE" != "N/A" ]]; then
    BURN=$(python3 -c "
err = float('$ERR_RATE')
budget_per_hour = (1 - $SLO_AVAILABILITY) / (30 * 24)  # budget par heure sur 30 jours
burn_rate = err / budget_per_hour if budget_per_hour > 0 else 0
print(f'{burn_rate:.1f}')
" 2>/dev/null || echo "N/A")
    if [[ "$BURN" != "N/A" ]]; then
      BURN_F=$(python3 -c "print(float('$BURN'))" 2>/dev/null || echo "0")
      if float_compare "$BURN_F" "<" "3" 2>/dev/null; then
        ok "  Burn rate     : ${BURN}×  (normal)"
      elif float_compare "$BURN_F" "<" "14.4" 2>/dev/null; then
        warn "  Burn rate     : ${BURN}×  (élevé, surveiller)"
      else
        fail "  Burn rate     : ${BURN}×  (CRITIQUE — budget épuisé en < 2h)"
      fi
    fi
  fi

  echo ""

  # ── SLO 2 : Latence ───────────────────────────────────────────────────────
  echo -e "${BOLD}  SLO 2 : Latence (P95 cible < ${SLO_LATENCY_P95}s)${NC}"

  P50=$(prom_query 'histogram_quantile(0.50, sum(rate(conversation_duration_seconds_bucket[5m])) by (le))')
  P95=$(prom_query 'histogram_quantile(0.95, sum(rate(conversation_duration_seconds_bucket[5m])) by (le))')
  P99=$(prom_query 'histogram_quantile(0.99, sum(rate(conversation_duration_seconds_bucket[5m])) by (le))')

  if [[ "$P95" == "N/A" ]]; then
    info "  Pas encore de données"
  else
    fmt_s() { python3 -c "print(f'{float(\"$1\"):.2f}s')" 2>/dev/null || echo "$1s"; }
    echo "  P50 : $(fmt_s $P50)   P95 : $(fmt_s $P95)   P99 : $(fmt_s $P99)"
    if float_compare "$P95" "<" "$SLO_LATENCY_P95" 2>/dev/null; then
      ok "  Latence P95 respectée"
    else
      fail "  Latence P95 VIOLÉE ($(fmt_s $P95) > ${SLO_LATENCY_P95}s)"
    fi
  fi

  echo ""

  # ── SLO 3 : RAG Hit Rate ──────────────────────────────────────────────────
  echo -e "${BOLD}  SLO 3 : RAG Hit Rate (cible ≥ ${SLO_RAG_HIT_RATE})${NC}"

  RAG_HIT=$(prom_query 'sum(rate(rag_requests_total{result="hit"}[10m])) / sum(rate(rag_requests_total[10m]))')

  if [[ "$RAG_HIT" == "N/A" ]]; then
    info "  Pas encore de données"
  else
    RAG_PCT=$(python3 -c "print(f'{float(\"$RAG_HIT\") * 100:.1f}%')" 2>/dev/null || echo "$RAG_HIT")
    if float_compare "$RAG_HIT" ">=" "$SLO_RAG_HIT_RATE" 2>/dev/null; then
      ok "  Hit Rate : ${RAG_PCT}  (SLO respecté)"
    else
      fail "  Hit Rate : ${RAG_PCT}  (SLO dégradé — rebuild RAG ?)"
    fi
  fi

  echo ""

  # ── Alertes actives ───────────────────────────────────────────────────────
  echo -e "${BOLD}  Alertes actives (AlertManager)${NC}"

  ALERTS=$(curl -s "${ALERTMANAGER_URL}/api/v1/alerts" 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    alerts = data.get('data', [])
    active = [a for a in alerts if a.get('status', {}).get('state') == 'active']
    if not active:
        print('  (aucune alerte active)')
    for a in active:
        name = a.get('labels', {}).get('alertname', '?')
        sev  = a.get('labels', {}).get('severity', '?')
        print(f'  [{sev.upper():8s}] {name}')
except:
    print('  (AlertManager inaccessible)')
" 2>/dev/null || echo "  (AlertManager inaccessible)")

  echo "$ALERTS"

  echo ""
  echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo "  Prometheus : ${PROMETHEUS_URL}/alerts"
  echo "  AlertMgr   : ${ALERTMANAGER_URL}"
  if [[ -n "$WATCH" ]]; then
    echo "  Actualisation dans 10s… (Ctrl+C pour arrêter)"
  fi
}

# ── Boucle watch ─────────────────────────────────────────────────────────────
if [[ "$WATCH" == "--watch" ]]; then
  while true; do
    display_slos
    sleep 10
  done
else
  display_slos
fi
