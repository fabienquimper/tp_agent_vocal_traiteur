# ─────────────────────────────────────────────────────────────────────────────
# Makefile – Traiteur Dupont – Agent Vocal IA
# Étape 02 : Observabilité (Prometheus + Grafana)
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: help build up down logs init-ollama reload-docs test test-health \
        metrics grafana prometheus clean clean-orders dev

AGENT_URL      = http://localhost:8000
PROMETHEUS_URL = http://localhost:9090
GRAFANA_URL    = http://localhost:3001

# Détection GPU : nvidia-container-cli doit charger les libs avec succès
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

## build : Construit toutes les images Docker
build:
	$(COMPOSE) build

## build-nocache : Reconstruit sans cache (utile après mise à jour des deps)
build-nocache:
	$(COMPOSE) build --no-cache

## ─── Cycle de vie ────────────────────────────────────────────────────────────

## up : Démarre tous les services (dont Prometheus et Grafana)
up:
	@echo "Mode : $(GPU_MSG)"
	$(COMPOSE) up -d
	@echo ""
	@echo "✓ Services démarrés"
	@echo "  UI         → http://localhost:3000"
	@echo "  Agent      → http://localhost:8000"
	@echo "  STT        → http://localhost:8001"
	@echo "  TTS        → http://localhost:8002"
	@echo "  Ollama     → http://localhost:11434"
	@echo "  Prometheus → http://localhost:9090   (métriques)"
	@echo "  Grafana    → http://localhost:3001   (dashboard)"
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
	@echo "  Ouvrez http://localhost:3001 (Grafana — dashboard auto-provisionné)"

## ─── Documents & RAG ─────────────────────────────────────────────────────────

## reload-docs : Re-indexe les fichiers du dossier data/ dans ChromaDB
reload-docs:
	@curl -s -X POST $(AGENT_URL)/api/reload-documents | python3 -m json.tool

## ─── Observabilité ───────────────────────────────────────────────────────────

## metrics : Affiche les métriques Prometheus brutes de l'agent
metrics:
	@echo "=== Métriques Prometheus ($(AGENT_URL)/metrics) ==="
	@curl -s $(AGENT_URL)/metrics | grep -v "^#" | grep -E "(stt|tts|llm|rag|conversation|orders|sessions|payments)"

## metrics-all : Affiche TOUTES les métriques (avec commentaires)
metrics-all:
	@curl -s $(AGENT_URL)/metrics

## prometheus : Ouvre l'UI Prometheus dans le navigateur
prometheus:
	@echo "Prometheus → $(PROMETHEUS_URL)"
	@echo "Exemples de requêtes PromQL :"
	@echo "  histogram_quantile(0.95, rate(conversation_duration_seconds_bucket[5m]))"
	@echo "  rate(conversations_total[5m])"
	@echo "  sessions_active"
	@xdg-open $(PROMETHEUS_URL) 2>/dev/null || open $(PROMETHEUS_URL) 2>/dev/null || true

## grafana : Ouvre le dashboard Grafana dans le navigateur
grafana:
	@echo "Grafana → $(GRAFANA_URL)"
	@echo "Login : admin / admin (ou GRAFANA_PASSWORD)"
	@echo "Dashboard : 'Agent Vocal Traiteur — Pipeline IA' (dossier Traiteur Dupont)"
	@xdg-open $(GRAFANA_URL) 2>/dev/null || open $(GRAFANA_URL) 2>/dev/null || true

## traffic : Génère du trafic de test pour alimenter les métriques Grafana
traffic:
	@echo "=== Génération de trafic (10 requêtes) ==="
	@for i in 1 2 3 4 5; do \
		curl -s -X POST $(AGENT_URL)/api/text \
			-H "Content-Type: application/json" \
			-d '{"text": "Quels sont vos horaires le samedi ?", "skip_tts": true}' > /dev/null; \
		curl -s -X POST $(AGENT_URL)/api/text \
			-H "Content-Type: application/json" \
			-d '{"text": "Bonjour, quelle est la formule buffet complet ?", "skip_tts": true}' > /dev/null; \
		echo -n "."; \
	done
	@echo ""
	@echo "✓ Trafic envoyé – vérifiez les métriques dans Grafana ($(GRAFANA_URL))"

## ─── Tests ───────────────────────────────────────────────────────────────────

## test : Lance un test conversationnel rapide (smoke test)
test:
	@echo "=== Test : Question sur les horaires ==="
	@curl -s -X POST $(AGENT_URL)/api/text \
		-H "Content-Type: application/json" \
		-d '{"text": "Quels sont vos horaires le samedi ?", "skip_tts": true}' \
		| python3 -m json.tool
	@echo ""
	@echo "=== Test : Commande simple (≤6 unités) ==="
	@curl -s -X POST $(AGENT_URL)/api/text \
		-H "Content-Type: application/json" \
		-d '{"text": "Je voudrais commander 2 quiches lorraines et 1 tarte aux pommes", "skip_tts": true}' \
		| python3 -m json.tool
	@echo ""
	@echo "=== Test : Métriques disponibles après les requêtes ==="
	@curl -s $(AGENT_URL)/metrics | grep -E "^(stt|llm|rag|tts|conversation|orders)" | head -30

## test-health : Vérifie l'état de santé de tous les services
test-health:
	@echo "=== Santé des services ==="
	@echo -n "Ollama     : " && curl -sf http://localhost:11434/api/tags > /dev/null && echo "✓ OK" || echo "✗ KO"
	@echo -n "STT        : " && curl -sf http://localhost:8001/health > /dev/null && echo "✓ OK" || echo "✗ KO"
	@echo -n "TTS        : " && curl -sf http://localhost:8002/health > /dev/null && echo "✓ OK" || echo "✗ KO"
	@echo -n "Agent      : " && curl -sf http://localhost:8000/health > /dev/null && echo "✓ OK" || echo "✗ KO"
	@echo -n "Metrics    : " && curl -sf http://localhost:8000/metrics > /dev/null && echo "✓ OK" || echo "✗ KO"
	@echo -n "Prometheus : " && curl -sf http://localhost:9090/-/healthy > /dev/null && echo "✓ OK" || echo "✗ KO"
	@echo -n "Grafana    : " && curl -sf http://localhost:3001/api/health > /dev/null && echo "✓ OK" || echo "✗ KO"
	@echo -n "UI         : " && curl -sf http://localhost:3000 > /dev/null && echo "✓ OK" || echo "✗ KO"

## ─── Nettoyage ───────────────────────────────────────────────────────────────

## clean : Arrête les services et supprime les volumes (ATTENTION : supprime ChromaDB + données Prometheus/Grafana)
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
	@echo "Assurez-vous qu'Ollama, STT et TTS tournent dans Docker :"
	@echo "  $(COMPOSE) up -d ollama stt tts"
	cd services/agent && \
		OLLAMA_BASE_URL=http://localhost:11434 \
		STT_SERVICE_URL=http://localhost:8001 \
		TTS_SERVICE_URL=http://localhost:8002 \
		DATA_DIR=../../data \
		ORDERS_DIR=../../orders \
		CHROMA_DIR=./chroma_dev \
		uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
