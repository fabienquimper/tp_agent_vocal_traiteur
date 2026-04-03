# ─────────────────────────────────────────────────────────────────────────────
# Makefile – Traiteur Dupont – Agent Vocal IA
# Étape 06 : Staging vs Production
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: help build up down logs init-ollama \
        staging-up staging-down staging-rebuild staging-status \
        staging-watch staging-test staging-logs staging-search \
        promote promote-force \
        stt-status stt-switch-blue stt-switch-green \
        benchmark-stt benchmark-install \
        rag-rebuild rag-status rag-rollback rag-watch rag-search rag-demo \
        test test-install test-smoke test-api test-rag test-environments \
        metrics grafana prometheus traffic clean clean-orders dev dev-staging

AGENT_URL        = http://localhost:8000
STAGING_URL      = http://localhost:8100
PROMETHEUS_URL   = http://localhost:9090
GRAFANA_URL      = http://localhost:3001
STT_BLUE_URL     = http://localhost:8011
STT_GREEN_URL    = http://localhost:8012
STT_ROUTER_URL   = http://localhost:8001

# Détection GPU
HAS_GPU := $(shell nvidia-container-cli info > /dev/null 2>&1 && echo "yes" || echo "no")
ifeq ($(HAS_GPU),yes)
  GPU_FLAGS = -f docker-compose.yml -f docker-compose.gpu.yml
  GPU_MSG   = GPU NVIDIA detecte
else
  GPU_FLAGS =
  GPU_MSG   = mode CPU
endif

COMPOSE         = docker compose $(GPU_FLAGS)
COMPOSE_STAGING = docker compose $(GPU_FLAGS) -f docker-compose.yml -f docker-compose.staging.yml

## help : Affiche cette aide
help:
	@grep -E '^## ' Makefile | sed 's/## //'

## ─── Construction ────────────────────────────────────────────────────────────

## build : Construit toutes les images (production + staging)
build:
	$(COMPOSE_STAGING) build

## build-nocache : Reconstruit sans cache
build-nocache:
	$(COMPOSE_STAGING) build --no-cache

## ─── Production ──────────────────────────────────────────────────────────────

## up : Démarre l'environnement production
up:
	@echo "Mode : $(GPU_MSG)"
	$(COMPOSE) up -d
	@echo ""
	@echo "Production démarrée :"
	@echo "  UI         → http://localhost:3000"
	@echo "  Agent      → http://localhost:8000  (production)"
	@echo "  Grafana    → http://localhost:3001"
	@echo ""
	@echo "Pour démarrer staging en parallèle : make staging-up"

## down : Arrête production et staging
down:
	$(COMPOSE_STAGING) down

## restart : Redémarre les services production
restart:
	$(COMPOSE) restart

## logs : Logs de tous les services production
logs:
	$(COMPOSE) logs -f

## logs-agent : Logs de l'agent production
logs-agent:
	$(COMPOSE) logs -f agent

## ─── Staging ─────────────────────────────────────────────────────────────────
##
## Workflow staging → production :
##   1. make staging-up          → démarre agent-staging (port 8100)
##   2. make staging-rebuild     → indexe data-staging/ dans ChromaDB staging
##   3. make staging-test        → valide l'environnement staging
##   4. make promote             → promeut staging → production (avec tests)
##
## Architecture :
##   Production (port 8000) : data/           → utilisateurs réels
##   Staging    (port 8100) : data-staging/   → tests avant promotion
##   Partagé   : ollama, stt-router, tts      → pas de duplication des services lourds

## staging-up : Démarre l'agent staging (nécessite que production soit démarrée)
staging-up:
	@echo "=== Démarrage de staging ==="
	@curl -sf $(AGENT_URL)/health > /dev/null || \
		(echo "Production non disponible. Lancez d'abord : make up" && exit 1)
	$(COMPOSE_STAGING) up -d agent-staging
	@echo ""
	@echo "Staging démarré : http://localhost:8100"
	@echo "Prochaine étape : make staging-rebuild"

## staging-down : Arrête l'agent staging
staging-down:
	$(COMPOSE_STAGING) stop agent-staging
	$(COMPOSE_STAGING) rm -f agent-staging
	@echo "✓ Staging arrêté"

## staging-rebuild : Reconstruit l'index RAG staging (quality gate incluse)
staging-rebuild:
	@echo "=== Rebuild RAG staging ==="
	@curl -s -X POST $(STAGING_URL)/api/rag/rebuild | python3 -m json.tool
	@echo ""
	@echo "Suivez l'avancement : make staging-watch"

## staging-status : État du RAG staging (avec résultat quality gate)
staging-status:
	@echo "=== État RAG staging ==="
	@curl -s $(STAGING_URL)/api/rag/status | python3 -m json.tool

## staging-watch : Surveille le rebuild staging jusqu'à la fin
staging-watch:
	@echo "Surveillance du rebuild staging (Ctrl+C pour arrêter)..."
	@while true; do \
		echo ""; date "+%H:%M:%S"; \
		curl -s $(STAGING_URL)/api/rag/status | python3 -m json.tool; \
		STATE=$$(curl -s $(STAGING_URL)/api/rag/status \
			| python3 -c "import sys,json; print(json.load(sys.stdin)['state'])"); \
		if [ "$$STATE" != "rebuilding" ]; then \
			echo "Rebuild staging terminé : $$STATE"; break; \
		fi; \
		sleep 5; \
	done

## staging-logs : Logs de l'agent staging
staging-logs:
	$(COMPOSE_STAGING) logs -f agent-staging

## staging-test : Lance les tests automatisés contre staging
staging-test:
	@echo "=== Tests sur staging (port 8100) ==="
	@python3 -c "import pytest, httpx" 2>/dev/null || \
		(echo "Dépendances manquantes. Exécutez : make test-install" && exit 1)
	AGENT_URL=$(STAGING_URL) python3 -m pytest \
		tests/test_smoke.py \
		tests/test_rag_quality.py \
		tests/test_environments.py \
		-v --tb=short

## staging-search : Recherche sémantique brute dans l'index staging
staging-search:
	@test -n "$(Q)" || (echo "Usage: make staging-search Q=\"votre question\"" && exit 1)
	@curl -s "$(STAGING_URL)/api/rag/search?q=$(Q)&k=3" | python3 -m json.tool

## ─── Promotion ───────────────────────────────────────────────────────────────
##
## La promotion copie les données staging validées vers production,
## puis déclenche un rebuild production avec quality gate.
##
## Sécurités automatiques :
##   - Tests staging lancés avant la copie
##   - Sauvegarde data/ avant écrasement (data-backup-YYYYMMDD_HHMMSS/)
##   - Quality gate production vérifiée après rebuild
##   - Rollback automatique si quality gate production échoue

## promote : Promeut staging → production (workflow complet sécurisé)
promote:
	@echo "=== Promotion staging → production ==="
	@bash scripts/promote.sh

## promote-force : Promeut sans tests (DANGER — urgence uniquement)
promote-force:
	@echo "=== Promotion FORCÉE (sans tests) ==="
	SKIP_TESTS=1 bash scripts/promote.sh

## ─── Initialisation ──────────────────────────────────────────────────────────

## init-ollama : Télécharge le modèle LLM Mistral dans Ollama
init-ollama:
	@echo "Téléchargement de Mistral..."
	@docker exec traiteur_ollama ollama pull mistral
	@echo "✓ Modèle Mistral prêt"

## init-all : Build + up + Mistral (démarrage complet depuis zéro)
init-all: build up
	@echo "Attente du démarrage d'Ollama..."
	@sleep 15
	$(MAKE) init-ollama
	@echo ""
	@echo "✓ Production prête : http://localhost:8000"
	@echo ""
	@echo "Pour démarrer staging :"
	@echo "  make staging-up && make staging-rebuild"

## ─── Blue/Green STT (hérité étape 03) ───────────────────────────────────────

## stt-status : Affiche quel modèle STT est actif
stt-status:
	@echo -n "Router : " && curl -sf $(STT_ROUTER_URL)/health && echo ""
	@echo -n "Blue   : " && curl -sf $(STT_BLUE_URL)/health && echo ""
	@echo -n "Green  : " && curl -sf $(STT_GREEN_URL)/health && echo ""

## stt-switch-green : Bascule vers stt-green (Whisper small)
stt-switch-green:
	@docker exec traiteur_stt_router cp /etc/nginx/upstreams/green.conf /etc/nginx/upstream.conf
	@docker exec traiteur_stt_router nginx -s reload
	@echo "✓ Actif : green (Whisper small)"

## stt-switch-blue : Revient à stt-blue (Whisper base)
stt-switch-blue:
	@docker exec traiteur_stt_router cp /etc/nginx/upstreams/blue.conf /etc/nginx/upstream.conf
	@docker exec traiteur_stt_router nginx -s reload
	@echo "✓ Actif : blue (Whisper base)"

## ─── Benchmark STT (hérité étape 03) ────────────────────────────────────────

## benchmark-install : Installe httpx + jiwer pour le benchmark
benchmark-install:
	pip install -r requirements-benchmark.txt -q

## benchmark-stt : Lance le benchmark WER + latence
benchmark-stt:
	@python3 -c "import httpx, jiwer" 2>/dev/null || (echo "make benchmark-install" && exit 1)
	python3 scripts/benchmark_stt.py

## ─── RAG Production ──────────────────────────────────────────────────────────

## rag-rebuild : Rebuild RAG production (quality gate incluse)
rag-rebuild:
	@curl -s -X POST $(AGENT_URL)/api/rag/rebuild | python3 -m json.tool

## rag-status : État du RAG production
rag-status:
	@curl -s $(AGENT_URL)/api/rag/status | python3 -m json.tool

## rag-watch : Surveille le rebuild production
rag-watch:
	@while true; do \
		STATE=$$(curl -s $(AGENT_URL)/api/rag/status \
			| python3 -c "import sys,json; print(json.load(sys.stdin)['state'])"); \
		echo $$(date "+%H:%M:%S") "→" $$STATE; \
		if [ "$$STATE" != "rebuilding" ]; then break; fi; \
		sleep 5; \
	done

## rag-rollback : Revient à la collection RAG précédente
rag-rollback:
	@curl -s -X POST "$(AGENT_URL)/api/rag/rollback" | python3 -m json.tool

## rag-search : Recherche sémantique brute dans la production
rag-search:
	@test -n "$(Q)" || (echo "Usage: make rag-search Q=\"votre question\"" && exit 1)
	@curl -s "$(AGENT_URL)/api/rag/search?q=$(Q)&k=3" | python3 -m json.tool

## reload-docs : Alias → rag-rebuild
reload-docs: rag-rebuild

## rag-demo : Démonstration du workflow complet staging → production
rag-demo:
	@echo "════════════════════════════════════════════════════════════"
	@echo "  Démo Staging → Production — étape 06"
	@echo "════════════════════════════════════════════════════════════"
	@echo ""
	@echo "Étape 1 : Vérification des environnements"
	@echo -n "  Production : " && curl -sf $(AGENT_URL)/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'], '(env:', d.get('env','?'), ')')"
	@echo -n "  Staging    : " && curl -sf $(STAGING_URL)/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'], '(env:', d.get('env','?'), ')')"
	@echo ""
	@echo "Étape 2 : Isolation — recherche marqueur staging en production"
	@RESULT=$$(curl -s "$(AGENT_URL)/api/rag/search?q=Assiette+Demo+Staging&k=1" \
		| python3 -c "import sys,json; print(json.load(sys.stdin)['hits'])"); \
		if [ "$$RESULT" = "0" ]; then \
			echo "  ✓ Marqueur staging absent de production (isolation OK)"; \
		else \
			echo "  ✗ Marqueur staging trouvé en production !"; \
		fi
	@echo ""
	@echo "Étape 3 : Tests staging"
	@AGENT_URL=$(STAGING_URL) python3 -m pytest tests/test_smoke.py tests/test_rag_quality.py \
		-q --tb=line 2>&1 | tail -5
	@echo ""
	@echo "Pour lancer la promotion complète : make promote"

## ─── Tests automatisés ───────────────────────────────────────────────────────

## test-install : Installe pytest + httpx
test-install:
	pip install -r requirements-test.txt -q
	@echo "✓ pytest + httpx installés"

## test-smoke : Tests rapides sans LLM
test-smoke:
	@python3 -c "import pytest, httpx" 2>/dev/null || (echo "make test-install" && exit 1)
	python3 -m pytest tests/test_smoke.py -v --tb=short

## test-rag : Quality gate RAG (sans LLM)
test-rag:
	@python3 -c "import pytest, httpx" 2>/dev/null || (echo "make test-install" && exit 1)
	python3 -m pytest tests/test_rag_quality.py -v --tb=short

## test-api : Tests API complets (nécessite Ollama)
test-api:
	@python3 -c "import pytest, httpx" 2>/dev/null || (echo "make test-install" && exit 1)
	python3 -m pytest tests/test_api.py -v --tb=short

## test-environments : Tests d'isolation staging vs production
test-environments:
	@python3 -c "import pytest, httpx" 2>/dev/null || (echo "make test-install" && exit 1)
	python3 -m pytest tests/test_environments.py -v --tb=short

## test : Lance tous les tests production
test:
	@python3 -c "import pytest, httpx" 2>/dev/null || (echo "make test-install" && exit 1)
	python3 -m pytest tests/ -v --tb=short

## ─── Observabilité ───────────────────────────────────────────────────────────

## metrics : Métriques Prometheus (production)
metrics:
	@curl -s $(AGENT_URL)/metrics | grep -v "^#" | grep -E "(rag_|quality_gate)"

## traffic : Génère du trafic de test sur production
traffic:
	@for i in 1 2 3 4 5; do \
		curl -s -X POST $(AGENT_URL)/api/text \
			-H "Content-Type: application/json" \
			-d '{"text": "Quels sont vos horaires le samedi ?", "skip_tts": true}' > /dev/null; \
		curl -s -X POST $(AGENT_URL)/api/text \
			-H "Content-Type: application/json" \
			-d '{"text": "Quelle est la formule buffet complet ?", "skip_tts": true}' > /dev/null; \
		echo -n "."; \
	done
	@echo " ✓ Trafic envoyé"

## grafana : Ouvre Grafana
grafana:
	@xdg-open $(GRAFANA_URL) 2>/dev/null || open $(GRAFANA_URL) 2>/dev/null || echo "→ $(GRAFANA_URL)"

## prometheus : Ouvre Prometheus
prometheus:
	@xdg-open $(PROMETHEUS_URL) 2>/dev/null || open $(PROMETHEUS_URL) 2>/dev/null || echo "→ $(PROMETHEUS_URL)"

## ─── Nettoyage ───────────────────────────────────────────────────────────────

## clean : Arrête tout et supprime les volumes (production + staging)
clean:
	$(COMPOSE_STAGING) down -v
	@echo "✓ Conteneurs et volumes supprimés"

## clean-orders : Supprime les fichiers Excel de commandes
clean-orders:
	rm -f orders/*.xlsx orders-staging/*.xlsx
	@echo "✓ Fichiers de commandes supprimés"

## ─── Développement ───────────────────────────────────────────────────────────

## dev : Lance l'agent production en mode développement (hot-reload)
dev:
	cd services/agent && \
		OLLAMA_BASE_URL=http://localhost:11434 \
		STT_SERVICE_URL=http://localhost:8001 \
		TTS_SERVICE_URL=http://localhost:8002 \
		DATA_DIR=../../data \
		ORDERS_DIR=../../orders \
		CHROMA_DIR=./chroma_dev \
		EVAL_DIR=../../eval \
		APP_ENV=production \
		uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

## dev-staging : Lance l'agent staging en mode développement (port 8100)
dev-staging:
	cd services/agent && \
		OLLAMA_BASE_URL=http://localhost:11434 \
		STT_SERVICE_URL=http://localhost:8001 \
		TTS_SERVICE_URL=http://localhost:8002 \
		DATA_DIR=../../data-staging \
		ORDERS_DIR=../../orders-staging \
		CHROMA_DIR=./chroma_dev_staging \
		EVAL_DIR=../../eval \
		APP_ENV=staging \
		uvicorn app.main:app --reload --host 0.0.0.0 --port 8100
