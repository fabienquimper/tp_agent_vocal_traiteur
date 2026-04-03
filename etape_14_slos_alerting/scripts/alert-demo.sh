#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# alert-demo.sh — Démonstration : générer des erreurs pour déclencher les alertes
# Étape 14 : SLOs & Alerting
#
# Ce script :
#   1. Démarre un webhook receiver Python (port 5001) pour capturer les alertes
#   2. Génère des requêtes qui vont faire monter le taux d'erreur
#   3. Attend que les alertes se déclenchent
#   4. Affiche les notifications reçues par le webhook
#
# Architecture de la démo :
#   [Ce script] ──POST /api/text──▶ [Agent]
#   [Prometheus] ──évalue les règles──▶ [AlertManager] ──POST──▶ [Webhook :5001]
#                  (toutes les 15s)      (après for: 2m)
#
# Usage :
#   bash scripts/alert-demo.sh              # démo complète
#   bash scripts/alert-demo.sh --webhook    # démarre seulement le webhook receiver
#   bash scripts/alert-demo.sh --load       # envoie seulement la charge d'erreurs
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

AGENT_URL="${AGENT_URL:-http://localhost:8000}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
ALERTMANAGER_URL="${ALERTMANAGER_URL:-http://localhost:9093}"
MODE="${1:-}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'
BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }

# ── Étape 1 : Démarrer le webhook receiver ────────────────────────────────────
start_webhook_receiver() {
  info "Démarrage du webhook receiver sur le port 5001..."

  python3 - << 'PYEOF' &
import http.server
import json
import threading
import sys
from datetime import datetime

class WebhookHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8')
        self.send_response(200)
        self.end_headers()

        try:
            data = json.loads(body)
            path = self.path
            status = data.get('status', 'unknown')
            alerts = data.get('alerts', [])

            print(f"\n{'='*60}")
            print(f"  WEBHOOK REÇU — {datetime.now().strftime('%H:%M:%S')}")
            print(f"  Path     : {path}")
            print(f"  Status   : {status.upper()}")
            print(f"  Alertes  : {len(alerts)}")
            print(f"{'='*60}")

            for alert in alerts:
                name = alert.get('labels', {}).get('alertname', 'unknown')
                sev  = alert.get('labels', {}).get('severity', 'unknown')
                desc = alert.get('annotations', {}).get('description', '')
                state = alert.get('status', 'unknown')
                print(f"  [{sev.upper():8s}] {name}")
                if desc:
                    # Première ligne du description
                    first_line = desc.strip().split('\n')[0]
                    print(f"             {first_line}")
                print()

        except json.JSONDecodeError:
            print(f"Webhook reçu (non-JSON) : {body[:200]}")

    def log_message(self, format, *args):
        pass  # silence les logs HTTP

server = http.server.HTTPServer(('0.0.0.0', 5001), WebhookHandler)
print(f"Webhook receiver actif sur http://0.0.0.0:5001")
print(f"En attente d'alertes AlertManager...")
print()
server.serve_forever()
PYEOF

  WEBHOOK_PID=$!
  echo $WEBHOOK_PID > /tmp/alert-demo-webhook.pid
  sleep 1
  success "Webhook receiver démarré (PID=$WEBHOOK_PID)"
}

# ── Étape 2 : Vérifier que tout est accessible ────────────────────────────────
check_services() {
  info "Vérification des services..."

  if ! curl -s --fail "${AGENT_URL}/health" > /dev/null 2>&1; then
    warn "Agent inaccessible sur ${AGENT_URL}"
    warn "Démarrer l'agent : make up"
    exit 1
  fi
  success "Agent accessible"

  if ! curl -s --fail "${PROMETHEUS_URL}/-/ready" > /dev/null 2>&1; then
    warn "Prometheus inaccessible sur ${PROMETHEUS_URL}"
    warn "Vérifier que Prometheus tourne"
    exit 1
  fi
  success "Prometheus accessible"

  if ! curl -s --fail "${ALERTMANAGER_URL}/-/ready" > /dev/null 2>&1; then
    warn "AlertManager inaccessible sur ${ALERTMANAGER_URL}"
    warn "Démarrer AlertManager : docker compose up alertmanager -d"
    exit 1
  fi
  success "AlertManager accessible"
}

# ── Étape 3 : Envoyer des requêtes normales (baseline) ───────────────────────
baseline_load() {
  info "Envoi de 20 requêtes normales (baseline)..."
  for i in $(seq 1 20); do
    curl -s -X POST "${AGENT_URL}/api/text" \
      -H "Content-Type: application/json" \
      -d '{"text": "Bonjour, que proposez-vous comme menu ?", "skip_tts": true}' \
      > /dev/null 2>&1 || true
  done
  success "Baseline envoyé (20 requêtes)"
}

# ── Étape 4 : Déclencher un taux d'erreur élevé ──────────────────────────────
generate_errors() {
  local N="${1:-50}"
  warn "Génération de $N requêtes invalides pour déclencher les alertes..."
  warn "Les alertes se déclenchent après 'for: 2m' dans les règles Prometheus."
  echo ""

  # Requêtes qui vont échouer : payload invalide / JSON malformé
  # En réalité, on envoie des requêtes valides mais très rapides pour
  # saturer l'agent → il va générer des erreurs de timeout Ollama
  for i in $(seq 1 $N); do
    # Requête sans session_id sur un endpoint qui attend une session en cours
    curl -s -X POST "${AGENT_URL}/api/text" \
      -H "Content-Type: application/json" \
      -d "{\"text\": \"ERROR_TRIGGER_${i}\", \"skip_tts\": true, \"session_id\": \"invalid-session-${RANDOM}\"}" \
      > /dev/null 2>&1 || true

    if (( i % 10 == 0 )); then
      echo -n "  ${i}/${N} requêtes envoyées..."
      # Vérifier le taux d'erreur actuel
      ERR_RATE=$(curl -s "${PROMETHEUS_URL}/api/v1/query" \
        --data-urlencode 'query=sum(rate(conversations_total{status="error"}[1m])) / sum(rate(conversations_total[1m]))' \
        2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
results = data.get('data', {}).get('result', [])
if results:
    v = float(results[0]['value'][1])
    print(f' taux erreur = {v*100:.1f}%')
else:
    print(' (pas de données)')
" 2>/dev/null || echo "")
      echo "$ERR_RATE"
    fi
    sleep 0.1
  done
  echo ""
}

# ── Étape 5 : Observer les alertes Prometheus ─────────────────────────────────
watch_prometheus_alerts() {
  info "Surveiller les alertes dans Prometheus..."
  echo ""
  echo "  URL : ${PROMETHEUS_URL}/alerts"
  echo ""

  for attempt in $(seq 1 18); do  # 18 × 10s = 3 minutes max
    FIRING=$(curl -s "${PROMETHEUS_URL}/api/v1/alerts" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
alerts = data.get('data', {}).get('alerts', [])
firing = [a for a in alerts if a.get('state') == 'firing']
if firing:
    for a in firing:
        name = a.get('labels', {}).get('alertname', '?')
        sev  = a.get('labels', {}).get('severity', '?')
        print(f'{name} [{sev}]')
" 2>/dev/null || echo "")

    if [[ -n "$FIRING" ]]; then
      echo ""
      success "Alertes FIRING détectées :"
      echo "$FIRING" | while read -r line; do
        echo "    → $line"
      done
      return 0
    fi

    echo -n "  Tentative $attempt/18 — Prometheus évalue les règles… "

    # Vérifier si des alertes sont en état PENDING (before "for:" is met)
    PENDING=$(curl -s "${PROMETHEUS_URL}/api/v1/alerts" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
alerts = data.get('data', {}).get('alerts', [])
pending = [a for a in alerts if a.get('state') == 'pending']
print(f'{len(pending)} pending')
" 2>/dev/null || echo "")
    echo "$PENDING"
    sleep 10
  done

  warn "Timeout : aucune alerte FIRING après 3 minutes."
  warn "Vérifier : ${PROMETHEUS_URL}/rules"
}

# ── Nettoyage ─────────────────────────────────────────────────────────────────
cleanup() {
  if [[ -f /tmp/alert-demo-webhook.pid ]]; then
    WPID=$(cat /tmp/alert-demo-webhook.pid)
    kill "$WPID" 2>/dev/null || true
    rm -f /tmp/alert-demo-webhook.pid
    info "Webhook receiver arrêté"
  fi
}
trap cleanup EXIT

# ── Main ──────────────────────────────────────────────────────────────────────
case "$MODE" in
  --webhook)
    start_webhook_receiver
    echo "Webhook receiver en écoute. Appuyer sur Ctrl+C pour arrêter."
    wait
    ;;
  --load)
    baseline_load
    generate_errors 100
    ;;
  *)
    echo ""
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}  Démo SLO & Alerting — Traiteur Dupont${NC}"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "  Ce script va :"
    echo "    1. Démarrer un webhook receiver (port 5001)"
    echo "    2. Envoyer des requêtes pour créer un historique normal"
    echo "    3. Générer un taux d'erreur élevé"
    echo "    4. Attendre que Prometheus détecte la violation SLO"
    echo "    5. Observer les notifications AlertManager"
    echo ""
    echo "  Ouvrir dans un autre terminal :"
    echo "    ${PROMETHEUS_URL}/alerts   → état des règles"
    echo "    ${ALERTMANAGER_URL}        → alertes AlertManager"
    echo ""

    start_webhook_receiver
    check_services

    echo ""
    info "Étape 1 : Baseline normal (20 requêtes réussies)..."
    baseline_load

    echo ""
    info "Étape 2 : Génération d'erreurs (60 requêtes — burn rate élevé)..."
    warn "Les alertes avec 'for: 2m' nécessitent 2 minutes de violation continue."
    generate_errors 60

    echo ""
    info "Étape 3 : Surveillance des alertes Prometheus..."
    watch_prometheus_alerts

    echo ""
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "  Résoudre l'alerte (arrêter les erreurs) :"
    echo "    → Attendre 5 minutes sans erreurs → alerte resolved"
    echo "    → AlertManager re-notifie avec status=resolved"
    echo ""
    echo "  Silence manuel (maintenance planifiée) :"
    echo "    → ${ALERTMANAGER_URL} → Silence"
    echo "    → Durée : 2h, Matcher : alertname=~\"Traiteur.*\""
    echo ""
    info "Le webhook receiver continue d'écouter (Ctrl+C pour arrêter)."
    wait
    ;;
esac
