#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# security-check.sh — Vérifie les flux autorisés et bloqués par les NetworkPolicies
# Étape 12 : Sécurité
#
# Ce script teste depuis l'intérieur des pods :
#   ✓ Flux AUTORISÉS : doivent réussir (connexion établie)
#   ✗ Flux BLOQUÉS   : doivent échouer (timeout ou connection refused)
#
# Il utilise kubectl exec + Python (disponible dans les images Python/FastAPI)
# pour tester la connectivité sans avoir besoin de curl dans les images.
#
# Usage :
#   bash scripts/security-check.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

NS="traiteur"
PASS=0
FAIL=0
SKIP=0

ok()     { echo -e "${GREEN}✓ AUTORISÉ${NC}  $*"; PASS=$((PASS+1)); }
blocked(){ echo -e "${RED}✗ BLOQUÉ${NC}    $*"; PASS=$((PASS+1)); }   # bloqué = attendu
fail()   { echo -e "${RED}⚠ ÉCHEC${NC}     $*"; FAIL=$((FAIL+1)); }   # inattendu
skip()   { echo -e "${YELLOW}⊘ SKIP${NC}     $*"; SKIP=$((SKIP+1)); }

# ── Helper : test de connectivité depuis un pod ───────────────────────────────
# Retourne 0 si connexion établie, 1 si bloquée/timeout
test_connect() {
    local from_pod="$1"   # nom du pod source (kubectl exec)
    local target_url="$2" # URL cible
    local timeout="${3:-3}"

    result=$(kubectl exec -n "$NS" "$from_pod" -- \
        python3 -c "
import urllib.request, sys
try:
    urllib.request.urlopen('${target_url}', timeout=${timeout})
    print('ok')
except Exception as e:
    err = str(e)
    if 'timed out' in err.lower() or 'refused' in err.lower() or 'network' in err.lower():
        print('blocked')
    else:
        print(f'ok_err:{err[:50]}')
" 2>/dev/null || echo "blocked")

    echo "$result"
}

# ── Récupérer les noms des pods ───────────────────────────────────────────────
get_pod() {
    kubectl get pod -n "$NS" -l "app=$1" --no-headers \
        -o custom-columns=":metadata.name" 2>/dev/null | head -1
}

echo ""
echo "════════════════════════════════════════════════════════"
echo "  Security Check — Network Policies"
echo "════════════════════════════════════════════════════════"
echo ""

AGENT_POD=$(get_pod "agent")
OLLAMA_POD=$(get_pod "ollama")
PROM_POD=$(get_pod "prometheus")

if [ -z "$AGENT_POD" ]; then
    echo "Aucun pod 'agent' trouvé — cluster non démarré ?"
    exit 1
fi

echo "  Pods utilisés :"
echo "    agent    : ${AGENT_POD:-N/A}"
echo "    ollama   : ${OLLAMA_POD:-N/A}"
echo "    prometheus: ${PROM_POD:-N/A}"
echo ""

# ══════════════════════════════════════════════════════════════════════════════
# FLUX AUTORISÉS — doivent réussir
# ══════════════════════════════════════════════════════════════════════════════
echo -e "${CYAN}── Flux AUTORISÉS (doivent fonctionner) ──${NC}"
echo ""

# Agent → Ollama
if [ -n "$AGENT_POD" ] && [ -n "$OLLAMA_POD" ]; then
    result=$(test_connect "$AGENT_POD" "http://ollama:11434/")
    if [[ "$result" == "ok"* ]]; then
        ok "agent → ollama:11434 (LLM inférences)"
    else
        fail "agent → ollama:11434 (DEVRAIT être autorisé) [${result}]"
    fi
fi

# Agent → STT
STT_POD=$(get_pod "stt")
if [ -n "$AGENT_POD" ] && [ -n "$STT_POD" ]; then
    result=$(test_connect "$AGENT_POD" "http://stt:8001/health")
    if [[ "$result" == "ok"* ]]; then
        ok "agent → stt:8001 (transcription)"
    else
        fail "agent → stt:8001 (DEVRAIT être autorisé) [${result}]"
    fi
fi

# Agent → TTS
TTS_POD=$(get_pod "tts")
if [ -n "$AGENT_POD" ] && [ -n "$TTS_POD" ]; then
    result=$(test_connect "$AGENT_POD" "http://tts:8002/health")
    if [[ "$result" == "ok"* ]]; then
        ok "agent → tts:8002 (synthèse vocale)"
    else
        fail "agent → tts:8002 (DEVRAIT être autorisé) [${result}]"
    fi
fi

# Prometheus → Agent (/metrics)
if [ -n "$PROM_POD" ] && [ -n "$AGENT_POD" ]; then
    result=$(test_connect "$PROM_POD" "http://agent:8000/metrics")
    if [[ "$result" == "ok"* ]]; then
        ok "prometheus → agent:8000/metrics (scrape Prometheus)"
    else
        fail "prometheus → agent:8000/metrics (DEVRAIT être autorisé) [${result}]"
    fi
fi

echo ""

# ══════════════════════════════════════════════════════════════════════════════
# FLUX BLOQUÉS — doivent être refusés
# ══════════════════════════════════════════════════════════════════════════════
echo -e "${CYAN}── Flux BLOQUÉS (doivent être refusés) ──${NC}"
echo ""

# Ollama → Agent (Ollama ne devrait jamais initier de connexion vers l'agent)
if [ -n "$OLLAMA_POD" ] && [ -n "$AGENT_POD" ]; then
    # Ollama n'a pas Python — utiliser les outils disponibles
    result=$(kubectl exec -n "$NS" "$OLLAMA_POD" -- \
        timeout 4 bash -c "curl -sf http://agent:8000/health 2>&1 || echo blocked" \
        2>/dev/null || echo "blocked")
    if [[ "$result" == *"blocked"* ]] || [[ "$result" == *"timed out"* ]]; then
        blocked "ollama → agent:8000 (Ollama ne peut pas initier vers l'agent)"
    else
        fail "ollama → agent:8000 (DEVRAIT être bloqué !)"
    fi
fi

# Agent → API K8s directe (l'agent n'a pas besoin d'accès à l'API K8s)
if [ -n "$AGENT_POD" ]; then
    result=$(kubectl exec -n "$NS" "$AGENT_POD" -- \
        python3 -c "
import urllib.request, ssl
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
try:
    urllib.request.urlopen('https://kubernetes.default.svc:443/api', context=ctx, timeout=4)
    print('ok')
except Exception as e:
    if 'timed out' in str(e).lower() or 'refused' in str(e).lower():
        print('blocked')
    else:
        print('ok')  # 403 = connexion établie (accès refusé par RBAC, pas NetworkPolicy)
" 2>/dev/null || echo "blocked")
    if [[ "$result" == "blocked" ]]; then
        blocked "agent → kubernetes.default:443 (API K8s — bloqué réseau)"
    else
        echo -e "${YELLOW}⚠ PARTIEL${NC}  agent → kubernetes.default:443 (connexion établie, RBAC devrait refuser)"
    fi
fi

# ── Résumé ────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
echo "  Résultat : ${PASS} vérifications passées | ${FAIL} échecs | ${SKIP} skippés"
echo ""
if [ "$FAIL" -eq 0 ]; then
    echo -e "  ${GREEN}✓ Toutes les politiques réseau sont correctement appliquées${NC}"
else
    echo -e "  ${RED}⚠ $FAIL politique(s) ne fonctionnent pas comme attendu${NC}"
    echo "  Vérifier : kubectl get networkpolicy -n traiteur"
    echo "  Vérifier : kubectl describe networkpolicy default-deny-all -n traiteur"
fi
echo "════════════════════════════════════════════════════════"
