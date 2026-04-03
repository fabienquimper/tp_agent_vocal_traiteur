# ─────────────────────────────────────────────────────────────────────────────
# Makefile – Traiteur Dupont – Agent Vocal IA
# Étape 05 : Quality Gates — Tests automatisés avant Atomic Swap
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: help build up down logs init-ollama reload-docs \
        stt-status stt-switch-blue stt-switch-green \
        benchmark-stt benchmark-install \
        rag-rebuild rag-status rag-rollback rag-watch rag-demo \
        test test-install test-smoke test-api test-rag \
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

## build : Construit toutes les images
build:
	$(COMPOSE) build

## build-nocache : Reconstruit sans cache
build-nocache:
	$(COMPOSE) build --no-cache

## ─── Cycle de vie ────────────────────────────────────────────────────────────

## up : Démarre tous les services
up:
	@echo "Mode : $(GPU_MSG)"
	$(COMPOSE) up -d
	@echo ""
	@echo "✓ Services démarrés"
	@echo "  UI          → http://localhost:3000"
	@echo "  Agent       → http://localhost:8000"
	@echo "  STT Router  → http://localhost:8001"
	@echo "  STT Blue    → http://localhost:8011"
	@echo "  STT Green   → http://localhost:8012"
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
	@echo "  Pour lancer les tests :"
	@echo "    make test-install && make test-smoke"

## ─── Blue/Green Deployment (hérité étape 03) ─────────────────────────────────

## stt-status : Affiche quel modèle STT est actif (blue ou green)
stt-status:
	@echo "=== Statut du STT Router ==="
	@echo -n "Router (actif)  : " && curl -sf $(STT_ROUTER_URL)/health && echo ""
	@echo -n "STT Blue        : " && curl -sf $(STT_BLUE_URL)/health && echo ""
	@echo -n "STT Green       : " && curl -sf $(STT_GREEN_URL)/health && echo ""

## stt-switch-green : Bascule vers stt-green (Whisper small) — ZÉRO DOWNTIME
stt-switch-green:
	@echo "=== Blue → Green (Whisper base → small) ==="
	@curl -sf $(STT_GREEN_URL)/health || (echo "❌ stt-green n'est pas prêt!" && exit 1)
	@docker exec traiteur_stt_router cp /etc/nginx/upstreams/green.conf /etc/nginx/upstream.conf
	@docker exec traiteur_stt_router nginx -s reload
	@echo "✓ Switch effectué !"
	@echo -n "  Actif maintenant : " && curl -sf $(STT_ROUTER_URL)/health && echo ""

## stt-switch-blue : Revient à stt-blue (Whisper base) — rollback ZÉRO DOWNTIME
stt-switch-blue:
	@echo "=== Green → Blue (rollback Whisper small → base) ==="
	@curl -sf $(STT_BLUE_URL)/health || (echo "❌ stt-blue n'est pas prêt!" && exit 1)
	@docker exec traiteur_stt_router cp /etc/nginx/upstreams/blue.conf /etc/nginx/upstream.conf
	@docker exec traiteur_stt_router nginx -s reload
	@echo "✓ Rollback effectué !"

## ─── Benchmark STT (hérité étape 03) ────────────────────────────────────────

## benchmark-install : Installe les dépendances Python pour le benchmark
benchmark-install:
	pip install -r requirements-benchmark.txt -q
	@echo "✓ Dépendances benchmark installées (httpx, jiwer)"

## benchmark-stt : Lance le benchmark WER + latence
benchmark-stt:
	@python3 -c "import httpx, jiwer" 2>/dev/null || \
		(echo "Dépendances manquantes. Exécutez : make benchmark-install" && exit 1)
	python3 scripts/benchmark_stt.py

## ─── Documents & RAG ─────────────────────────────────────────────────────────

## reload-docs : Alias → rag-rebuild (non-bloquant + quality gate depuis étape 05)
reload-docs: rag-rebuild

## ─── Hot RAG Reload + Quality Gate (étapes 04 & 05) ─────────────────────────
##
## Nouveauté étape 05 :
##   Avant le swap, une quality gate vérifie le hit rate du nouveau index.
##   Si hit_rate < 80% → swap annulé, état = "quality_gate_failed"
##   → L'ancien index reste actif, aucun downtime, aucune régression.

## rag-rebuild : Lance un rebuild RAG (quality gate incluse)
rag-rebuild:
	@echo "=== Lancement du rebuild RAG (non-bloquant + quality gate) ==="
	@curl -s -X POST $(AGENT_URL)/api/rag/rebuild | python3 -m json.tool
	@echo ""
	@echo "Le rebuild + quality gate tournent en arrière-plan."
	@echo "Utilisez 'make rag-status' pour suivre."

## rag-status : Affiche l'état courant du rebuild RAG + résultat quality gate
rag-status:
	@echo "=== État du RAG ==="
	@curl -s $(AGENT_URL)/api/rag/status | python3 -m json.tool

## rag-watch : Surveille l'avancement du rebuild toutes les 5s
rag-watch:
	@echo "Surveillance du rebuild RAG (Ctrl+C pour arrêter)..."
	@while true; do \
		echo ""; \
		date "+%H:%M:%S"; \
		curl -s $(AGENT_URL)/api/rag/status | python3 -m json.tool; \
		STATE=$$(curl -s $(AGENT_URL)/api/rag/status | python3 -c "import sys,json; print(json.load(sys.stdin)['state'])"); \
		if [ "$$STATE" != "rebuilding" ]; then \
			echo "Rebuild terminé ($$STATE)"; break; \
		fi; \
		sleep 5; \
	done

## rag-rollback : Revient à la collection RAG précédente (zéro downtime)
rag-rollback:
	@echo "=== Rollback RAG ==="
	@curl -s -X POST "$(AGENT_URL)/api/rag/rollback" | python3 -m json.tool

## rag-search : Recherche sémantique brute (sans LLM) — utile pour debug
rag-search:
	@echo "Utilisation : make rag-search Q=\"votre question\""
	@test -n "$(Q)" || (echo "Paramètre Q manquant. Ex: make rag-search Q=\"horaires samedi\"" && exit 1)
	@curl -s "$(AGENT_URL)/api/rag/search?q=$(Q)&k=3" | python3 -m json.tool

## rag-demo : Démonstration complète hot reload + quality gate
rag-demo:
	@echo "════════════════════════════════════════════════════════════"
	@echo "  Démo Hot RAG Reload + Quality Gate — étape 05"
	@echo "════════════════════════════════════════════════════════════"
	@echo ""
	@echo "Étape 1 : Question sur les promotions (avant reload)"
	@curl -s -X POST $(AGENT_URL)/api/text \
		-H "Content-Type: application/json" \
		-d '{"text": "Avez-vous des promotions en ce moment ?", "skip_tts": true}' \
		| python3 -c "import sys,json; d=json.load(sys.stdin); print('Réponse:', d['response_text'][:200])"
	@echo ""
	@echo "Étape 2 : État RAG actuel"
	@curl -s $(AGENT_URL)/api/rag/status | python3 -m json.tool
	@echo ""
	@echo "Étape 3 : Lancement du rebuild + quality gate (non-bloquant)"
	@curl -s -X POST $(AGENT_URL)/api/rag/rebuild | python3 -m json.tool
	@echo ""
	@echo "Étape 4 : Requêtes pendant le rebuild (elles fonctionnent !)"
	@curl -s -X POST $(AGENT_URL)/api/text \
		-H "Content-Type: application/json" \
		-d '{"text": "Quels sont vos horaires ?", "skip_tts": true}' \
		| python3 -c "import sys,json; d=json.load(sys.stdin); print('Réponse:', d['response_text'][:200])"
	@echo ""
	@echo "Étape 5 : Attente de la fin du rebuild..."
	@until [ "$$(curl -s $(AGENT_URL)/api/rag/status | python3 -c "import sys,json; print(json.load(sys.stdin)['state'])")" != "rebuilding" ]; do \
		echo -n "."; sleep 3; \
	done
	@echo " Done!"
	@echo ""
	@echo "Étape 6 : Résultat (avec quality gate)"
	@curl -s $(AGENT_URL)/api/rag/status | python3 -m json.tool
	@echo ""
	@echo "Étape 7 : Question sur les promotions (après reload)"
	@curl -s -X POST $(AGENT_URL)/api/text \
		-H "Content-Type: application/json" \
		-d '{"text": "Avez-vous des promotions en ce moment ?", "skip_tts": true}' \
		| python3 -c "import sys,json; d=json.load(sys.stdin); print('Réponse:', d['response_text'][:300])"

## ─── Tests automatisés (étape 05) ───────────────────────────────────────────
##
## Organisation des tests :
##   test-smoke  → < 5s, sans LLM  — health, métriques, RAG search
##   test-rag    → < 30s, sans LLM — quality gate complète sur 15 requêtes
##   test-api    → 1-3min, avec LLM — contrats API complets
##   test        → tous les tests

## test-install : Installe les dépendances Python pour les tests
test-install:
	@echo "Installation des dépendances de test..."
	pip install -r requirements-test.txt -q
	@echo "✓ pytest + httpx installés"

## test-smoke : Tests rapides sans LLM (health, métriques, RAG)
test-smoke:
	@echo "=== Tests smoke (sans LLM) ==="
	@python3 -c "import pytest, httpx" 2>/dev/null || \
		(echo "Dépendances manquantes. Exécutez : make test-install" && exit 1)
	python3 -m pytest tests/test_smoke.py -v --tb=short

## test-rag : Quality gate RAG — évalue le hit rate sur le jeu d'évaluation
test-rag:
	@echo "=== Tests quality gate RAG (sans LLM) ==="
	@python3 -c "import pytest, httpx" 2>/dev/null || \
		(echo "Dépendances manquantes. Exécutez : make test-install" && exit 1)
	python3 -m pytest tests/test_rag_quality.py -v --tb=short

## test-api : Tests d'intégration API complets (nécessite Ollama)
test-api:
	@echo "=== Tests API (nécessite Ollama + Mistral) ==="
	@python3 -c "import pytest, httpx" 2>/dev/null || \
		(echo "Dépendances manquantes. Exécutez : make test-install" && exit 1)
	python3 -m pytest tests/test_api.py -v --tb=short

## test : Lance tous les tests (smoke + rag + api)
test:
	@echo "=== Tous les tests ==="
	@python3 -c "import pytest, httpx" 2>/dev/null || \
		(echo "Dépendances manquantes. Exécutez : make test-install" && exit 1)
	python3 -m pytest tests/ -v --tb=short

## ─── Observabilité ───────────────────────────────────────────────────────────

## metrics : Affiche les métriques RAG + quality gate de l'agent
metrics:
	@echo "=== Métriques RAG + Quality Gate ==="
	@curl -s $(AGENT_URL)/metrics | grep -v "^#" | grep -E "(rag_|quality_gate)"

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
		EVAL_DIR=../../eval \
		uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
