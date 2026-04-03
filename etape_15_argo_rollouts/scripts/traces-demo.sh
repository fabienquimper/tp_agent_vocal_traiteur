#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# traces-demo.sh — Démonstration des traces distribuées OpenTelemetry
# Étape 10 : Observabilité avancée
#
# Ce script :
#   1. Envoie plusieurs requêtes à l'agent (text + RAG search)
#   2. Attend que les spans soient exportés vers Jaeger (BatchSpanProcessor ~1s)
#   3. Affiche les résultats et indique où chercher dans l'UI Jaeger
#
# Usage :
#   bash scripts/traces-demo.sh            # target docker-compose (localhost:8000)
#   bash scripts/traces-demo.sh --k8s      # target kubernetes (port-forward requis)
#
# Prérequis :
#   - Stack démarrée (make up ou make k8s-up)
#   - Jaeger accessible (http://localhost:16686)
#   - curl + jq installés
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()    { echo -e "${GREEN}✓${NC} $*"; }
step()  { echo -e "\n${BLUE}══${NC} ${CYAN}$*${NC}"; }
info()  { echo -e "   $*"; }
pause() { echo -e "\n${YELLOW}[Appuyer sur Entrée pour continuer...]${NC}"; read -r; }

AGENT_URL="${AGENT_URL:-http://localhost:8000}"
JAEGER_URL="${JAEGER_URL:-http://localhost:16686}"

echo ""
echo "════════════════════════════════════════════════════════"
echo "  Démonstration OpenTelemetry — Traces distribuées"
echo "  Traiteur Dupont (étape 10)"
echo "════════════════════════════════════════════════════════"
echo ""
echo "  Agent  : ${AGENT_URL}"
echo "  Jaeger : ${JAEGER_URL}"

# ── Vérifications ─────────────────────────────────────────────────────────────
step "0/4 — Vérifications"

if ! curl -sf "${AGENT_URL}/health" > /dev/null; then
    echo -e "${YELLOW}⚠${NC}  Agent non accessible sur ${AGENT_URL}"
    echo "   Démarrer avec : make up  (ou make k8s-up)"
    exit 1
fi
ok "Agent accessible"

if ! curl -sf "${JAEGER_URL}/" > /dev/null; then
    echo -e "${YELLOW}⚠${NC}  Jaeger non accessible sur ${JAEGER_URL}"
    echo "   Vérifier que jaeger est démarré (docker-compose ps)"
    exit 1
fi
ok "Jaeger accessible"

# ── Requête 1 : RAG search (sans LLM) ─────────────────────────────────────────
step "1/4 — Requête RAG search (span: rag.similarity_search)"
echo ""
info "Cette requête crée un span 'rag.similarity_search' avec :"
info "  - rag.query      = 'horaires du traiteur'"
info "  - rag.k          = 3"
info "  - rag.hits       = nombre de chunks retournés"
info "  - rag.collection = nom de la collection ChromaDB active"
echo ""

RESULT=$(curl -sf "${AGENT_URL}/api/rag/search?q=horaires+du+traiteur&k=3" | jq -r '.hits' 2>/dev/null || echo "?")
ok "RAG search : ${RESULT} hits retournés"
pause

# ── Requête 2 : text (LangGraph complet) ──────────────────────────────────────
step "2/4 — Requête texte complète (spans: session.handle_step + langgraph.invoke)"
echo ""
info "Cette requête crée une chaîne de spans :"
info ""
info "  POST /api/text                    ← span parent (FastAPI auto-instrumentation)"
info "    └── langgraph.invoke            ← span créé manuellement dans main.py"
info "          └── HTTP POST ollama:...  ← span auto (HTTPXClientInstrumentor)"
echo ""

RESP=$(curl -sf -X POST "${AGENT_URL}/api/text" \
    -H "Content-Type: application/json" \
    -d '{"text": "Quels sont vos horaires ?", "skip_tts": true}' \
    | jq -r '.response_text' 2>/dev/null | cut -c1-80 || echo "(erreur)")
ok "Réponse : ${RESP}..."
pause

# ── Requête 3 : multiple RAG searches pour voir la latence ────────────────────
step "3/4 — Batch de requêtes (comparaison latence RAG)"
echo ""
info "Envoi de 5 requêtes RAG pour observer la distribution de latence dans Jaeger..."
echo ""

QUERIES=("menus disponibles" "prix plateau" "horaires samedi" "promotions" "conges")
for q in "${QUERIES[@]}"; do
    HITS=$(curl -sf "${AGENT_URL}/api/rag/search?q=${q// /+}&k=3" \
        | jq -r '.hits' 2>/dev/null || echo "?")
    ok "  '${q}' → ${HITS} hits"
    sleep 0.3   # laisser du temps entre les requêtes pour des spans distincts
done

info ""
info "Attente export vers Jaeger (BatchSpanProcessor, ~1s)..."
sleep 2
ok "Spans exportés"
pause

# ── Résumé : où chercher dans Jaeger ──────────────────────────────────────────
step "4/4 — Explorer les traces dans Jaeger"
echo ""
echo "  Ouvrir : ${JAEGER_URL}"
echo ""
echo "  Dans l'interface Jaeger :"
echo ""
echo "  1. Service : sélectionner 'traiteur-agent'"
echo "     → Affiche toutes les traces de l'agent"
echo ""
echo "  2. Chercher un span spécifique :"
echo "     Operation Name → 'rag.similarity_search'"
echo "     → Affiche toutes les recherches RAG avec leur durée"
echo ""
echo "  3. Cliquer sur une trace → Waterfall view :"
echo "     POST /api/text"
echo "       └── langgraph.invoke (Xs)"
echo "             └── HTTP POST http://ollama:11434/... (Ys)"
echo ""
echo "  4. Attributs sur le span 'rag.similarity_search' :"
echo "     rag.query, rag.k, rag.hits, rag.collection"
echo ""
echo "  5. Comparer les durées : RAG vs LLM"
echo "     → D'où vient la latence de la requête ?"
echo ""
echo "  Depuis Grafana (http://localhost:3001) :"
echo "     Explore → datasource: Jaeger → service: traiteur-agent"
echo ""

ok "Démonstration terminée !"
echo ""
echo "  Concepts illustrés :"
echo "    ✓ Auto-instrumentation FastAPI (spans HTTP entrants)"
echo "    ✓ Auto-instrumentation httpx (spans HTTP sortants)"
echo "    ✓ Span manuel (rag.similarity_search) avec attributs métier"
echo "    ✓ Waterfall view : causalité entre spans"
echo "    ✓ Corrélation Grafana ↔ Jaeger"
