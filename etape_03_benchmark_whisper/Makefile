# ─────────────────────────────────────────────────────────────────────────────
# Makefile – Traiteur Dupont – Agent Vocal IA
# Étape 03 : Benchmark Whisper + Blue/Green Deployment
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: help build up down logs init-ollama reload-docs test test-health \
        stt-status stt-switch-blue stt-switch-green \
        benchmark-stt benchmark-install \
        metrics grafana prometheus traffic clean clean-orders dev

AGENT_URL      = http://localhost:8000
PROMETHEUS_URL = http://localhost:9090
GRAFANA_URL    = http://localhost:3001
STT_BLUE_URL   = http://localhost:8011
STT_GREEN_URL  = http://localhost:8012
STT_ROUTER_URL = http://localhost:8001

# Détection GPU
HAS_GPU := $(shell nvidia-container-cli info > /dev/null 2>&1 && echo "yes" || echo "no")
ifeq ($(HAS_GPU),yes)
  GPU_FLAGS = -f docker-compose.yml -f docker-compose.gpu.yml
  GPU_MSG   = GPU NVIDIA detecte
else
  GPU_FLAGS =
  GPU_MSG   = mode CPU
endif

COMPOSE = docker compose $(GPU_FLAGS)

## help : Affiche cette aide
help:
	@grep -E '^## ' Makefile | sed 's/## //'

## ─── Construction ────────────────────────────────────────────────────────────

## build : Construit toutes les images (dont stt-blue, stt-green, stt-router)
build:
	$(COMPOSE) build

## build-nocache : Reconstruit sans cache
build-nocache:
	$(COMPOSE) build --no-cache

## ─── Cycle de vie ────────────────────────────────────────────────────────────

## up : Démarre tous les services (Blue/Green + monitoring)
up:
	@echo "Mode : $(GPU_MSG)"
	$(COMPOSE) up -d
	@echo ""
	@echo "✓ Services démarrés"
	@echo "  UI          → http://localhost:3000"
	@echo "  Agent       → http://localhost:8000"
	@echo "  STT Router  → http://localhost:8001  (actif: BLUE/base par défaut)"
	@echo "  STT Blue    → http://localhost:8011  (Whisper base — accès direct benchmark)"
	@echo "  STT Green   → http://localhost:8012  (Whisper small — accès direct benchmark)"
	@echo "  TTS         → http://localhost:8002"
	@echo "  Ollama      → http://localhost:11434"
	@echo "  Prometheus  → http://localhost:9090"
	@echo "  Grafana     → http://localhost:3001"
	@echo ""
	@echo "Prochaine étape : make init-ollama"

## down : Arrête tous les services
down:
	$(COMPOSE) down

## restart : Redémarre tous les services
restart:
	$(COMPOSE) restart

## logs : Affiche les logs en temps réel
logs:
	$(COMPOSE) logs -f

## logs-agent : Logs de l'agent uniquement
logs-agent:
	$(COMPOSE) logs -f agent

## logs-router : Logs du STT router (nginx)
logs-router:
	$(COMPOSE) logs -f stt-router

## ─── Initialisation ──────────────────────────────────────────────────────────

## init-ollama : Télécharge le modèle LLM Mistral dans Ollama
init-ollama:
	@echo "Téléchargement du modèle Mistral (peut prendre plusieurs minutes)..."
	@docker exec traiteur_ollama ollama pull mistral
	@echo "✓ Modèle Mistral prêt"

## init-all : Build + up + init-ollama (démarrage complet depuis zéro)
init-all: build up
	@echo "Attente du démarrage d'Ollama..."
	@sleep 15
	$(MAKE) init-ollama
	@echo ""
	@echo "✓ Installation complète"
	@echo "  Ouvrez http://localhost:3000 (interface)"
	@echo "  Ouvrez http://localhost:3001 (Grafana)"
	@echo ""
	@echo "  Pour lancer le benchmark :"
	@echo "    make benchmark-stt"

## ─── Blue/Green Deployment ───────────────────────────────────────────────────
##
## Principe Blue/Green :
##   blue  = production actuelle (Whisper base)  — démarré avec stt-router pointant ici
##   green = candidat au déploiement (Whisper small) — testé via benchmark d'abord
##
##   Le switch est instantané (< 100ms) grâce à nginx -s reload.
##   Les requêtes en cours sur blue sont terminées proprement.
##   Toutes les nouvelles requêtes vont sur green.

## stt-status : Affiche quel modèle STT est actif (blue ou green)
stt-status:
	@echo "=== Statut du STT Router ==="
	@echo -n "Router (actif)  : " && curl -sf $(STT_ROUTER_URL)/health && echo ""
	@echo -n "STT Blue        : " && curl -sf $(STT_BLUE_URL)/health && echo ""
	@echo -n "STT Green       : " && curl -sf $(STT_GREEN_URL)/health && echo ""
	@echo ""
	@echo "Le modèle 'actif' dans Router = le modèle que l'agent utilise."

## stt-switch-green : Bascule vers stt-green (Whisper small) — ZÉRO DOWNTIME
stt-switch-green:
	@echo "=== Blue → Green (Whisper base → small) ==="
	@echo "Étape 1/3 : Vérification de stt-green..."
	@curl -sf $(STT_GREEN_URL)/health || (echo "❌ stt-green n'est pas prêt!" && exit 1)
	@echo "✓ stt-green est healthy"
	@echo ""
	@echo "Étape 2/3 : Mise à jour de la config nginx..."
	@docker exec traiteur_stt_router \
		cp /etc/nginx/upstreams/green.conf /etc/nginx/upstream.conf
	@echo ""
	@echo "Étape 3/3 : Rechargement nginx (graceful — aucune requête perdue)..."
	@docker exec traiteur_stt_router nginx -s reload
	@echo ""
	@echo "✓ Switch effectué !"
	@echo -n "  Actif maintenant : " && curl -sf $(STT_ROUTER_URL)/health && echo ""
	@echo ""
	@echo "  → Les nouvelles requêtes de l'agent utilisent maintenant Whisper small."
	@echo "  → Les requêtes en cours sur Whisper base ont été terminées proprement."
	@echo "  → Vérifiez l'impact dans Grafana : http://localhost:3001"
	@echo "     Panel 'STT — Latence Whisper P50/P95' — la latence augmente légèrement."

## stt-switch-blue : Revient à stt-blue (Whisper base) — rollback ZÉRO DOWNTIME
stt-switch-blue:
	@echo "=== Green → Blue (rollback Whisper small → base) ==="
	@echo "Étape 1/3 : Vérification de stt-blue..."
	@curl -sf $(STT_BLUE_URL)/health || (echo "❌ stt-blue n'est pas prêt!" && exit 1)
	@echo "✓ stt-blue est healthy"
	@echo ""
	@echo "Étape 2/3 : Mise à jour de la config nginx..."
	@docker exec traiteur_stt_router \
		cp /etc/nginx/upstreams/blue.conf /etc/nginx/upstream.conf
	@echo ""
	@echo "Étape 3/3 : Rechargement nginx (graceful)..."
	@docker exec traiteur_stt_router nginx -s reload
	@echo ""
	@echo "✓ Rollback effectué !"
	@echo -n "  Actif maintenant : " && curl -sf $(STT_ROUTER_URL)/health && echo ""

## ─── Benchmark STT ───────────────────────────────────────────────────────────

## benchmark-install : Installe les dépendances Python pour le benchmark
benchmark-install:
	@echo "Installation des dépendances benchmark..."
	pip install -r requirements-benchmark.txt -q
	@echo "✓ Dépendances installées (httpx, jiwer)"

## benchmark-stt : Lance le benchmark WER + latence (Whisper base vs small)
benchmark-stt:
	@echo "=== Benchmark STT — Whisper base vs small ==="
	@echo "Vérification des dépendances..."
	@python3 -c "import httpx, jiwer" 2>/dev/null || \
		(echo "Dépendances manquantes. Exécutez : make benchmark-install" && exit 1)
	@echo "✓ Dépendances OK"
	@echo ""
	python3 scripts/benchmark_stt.py

## benchmark-quick : Benchmark rapide sur les 5 premières phrases seulement
benchmark-quick:
	@echo "=== Benchmark rapide (5 phrases) ==="
	@python3 -c "import httpx, jiwer" 2>/dev/null || \
		(echo "Dépendances manquantes. Exécutez : make benchmark-install" && exit 1)
	@python3 -c "\
import json, sys; \
data = json.load(open('eval/phrases_test.json')); \
json.dump(data[:5], open('/tmp/phrases_quick.json', 'w'), ensure_ascii=False); \
print('5 phrases préparées')"
	@EVAL_FILE_OVERRIDE=/tmp/phrases_quick.json python3 scripts/benchmark_stt.py

## ─── Documents & RAG ─────────────────────────────────────────────────────────

## reload-docs : Re-indexe les fichiers du dossier data/ dans ChromaDB
reload-docs:
	@curl -s -X POST $(AGENT_URL)/api/reload-documents | python3 -m json.tool

## ─── Observabilité ───────────────────────────────────────────────────────────

## metrics : Affiche les métriques STT de l'agent
metrics:
	@echo "=== Métriques STT (mesurées côté agent via stt-router) ==="
	@curl -s $(AGENT_URL)/metrics | grep -v "^#" | grep -E "(stt|conversation)"

## traffic : Génère du trafic de test pour alimenter les métriques Grafana
traffic:
	@echo "=== Génération de trafic (10 requêtes) ==="
	@for i in 1 2 3 4 5; do \
		curl -s -X POST $(AGENT_URL)/api/text \
			-H "Content-Type: application/json" \
			-d '{"text": "Quels sont vos horaires le samedi ?", "skip_tts": true}' > /dev/null; \
		curl -s -X POST $(AGENT_URL)/api/text \
			-H "Content-Type: application/json" \
			-d '{"text": "Quelle est la formule buffet complet ?", "skip_tts": true}' > /dev/null; \
		echo -n "."; \
	done
	@echo ""
	@echo "✓ Trafic envoyé – vérifiez dans Grafana ($(GRAFANA_URL))"

## grafana : Ouvre le dashboard Grafana
grafana:
	@echo "Grafana → $(GRAFANA_URL) (admin / admin)"
	@xdg-open $(GRAFANA_URL) 2>/dev/null || open $(GRAFANA_URL) 2>/dev/null || true

## prometheus : Ouvre l'UI Prometheus
prometheus:
	@echo "Prometheus → $(PROMETHEUS_URL)"
	@xdg-open $(PROMETHEUS_URL) 2>/dev/null || open $(PROMETHEUS_URL) 2>/dev/null || true

## ─── Tests ───────────────────────────────────────────────────────────────────

## test : Lance un test conversationnel rapide
test:
	@echo "=== Test : Question sur les horaires ==="
	@curl -s -X POST $(AGENT_URL)/api/text \
		-H "Content-Type: application/json" \
		-d '{"text": "Quels sont vos horaires le samedi ?", "skip_tts": true}' \
		| python3 -m json.tool
	@echo ""
	@echo "=== STT actif ==="
	@curl -sf $(STT_ROUTER_URL)/health

## test-health : Vérifie l'état de santé de tous les services
test-health:
	@echo "=== Santé des services ==="
	@echo -n "Ollama      : " && curl -sf http://localhost:11434/api/tags > /dev/null && echo "✓ OK" || echo "✗ KO"
	@echo -n "STT Router  : " && curl -sf $(STT_ROUTER_URL)/health > /dev/null && echo "✓ OK" || echo "✗ KO"
	@echo -n "STT Blue    : " && curl -sf $(STT_BLUE_URL)/health > /dev/null && echo "✓ OK" || echo "✗ KO"
	@echo -n "STT Green   : " && curl -sf $(STT_GREEN_URL)/health > /dev/null && echo "✓ OK" || echo "✗ KO"
	@echo -n "TTS         : " && curl -sf http://localhost:8002/health > /dev/null && echo "✓ OK" || echo "✗ KO"
	@echo -n "Agent       : " && curl -sf http://localhost:8000/health > /dev/null && echo "✓ OK" || echo "✗ KO"
	@echo -n "Prometheus  : " && curl -sf http://localhost:9090/-/healthy > /dev/null && echo "✓ OK" || echo "✗ KO"
	@echo -n "Grafana     : " && curl -sf http://localhost:3001/api/health > /dev/null && echo "✓ OK" || echo "✗ KO"
	@echo -n "UI          : " && curl -sf http://localhost:3000 > /dev/null && echo "✓ OK" || echo "✗ KO"

## ─── Nettoyage ───────────────────────────────────────────────────────────────

## clean : Arrête les services et supprime les volumes
clean:
	$(COMPOSE) down -v
	@echo "✓ Conteneurs et volumes supprimés"

## clean-orders : Supprime les fichiers Excel de commandes
clean-orders:
	rm -f orders/*.xlsx
	@echo "✓ Fichiers de commandes supprimés"

## ─── Développement ───────────────────────────────────────────────────────────

## dev : Lance l'agent en mode développement avec hot-reload (hors Docker)
dev:
	@echo "Démarrage en mode développement..."
	cd services/agent && \
		OLLAMA_BASE_URL=http://localhost:11434 \
		STT_SERVICE_URL=http://localhost:8001 \
		TTS_SERVICE_URL=http://localhost:8002 \
		DATA_DIR=../../data \
		ORDERS_DIR=../../orders \
		CHROMA_DIR=./chroma_dev \
		uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
