# ─────────────────────────────────────────────────────────────────────────────
# Makefile – Traiteur Dupont – Agent Vocal IA
# Étape 10 : OpenTelemetry — Traces distribuées avec Jaeger
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: help \
        lint lint-fix ci-local \
        test-unit \
        traces-ui traces-demo traces-disable traces-enable \
        argocd-setup argocd-status argocd-sync argocd-diff \
        argocd-rollback argocd-ui argocd-password argocd-demo-drift \
        k8s-up k8s-down k8s-status k8s-build k8s-load k8s-deploy \
        k8s-init-ollama k8s-configmaps k8s-reload-data \
        k8s-logs-agent k8s-exec-agent \
        k8s-hpa-status k8s-scale k8s-stress k8s-rolling-update \
        k8s-stt-switch-blue k8s-stt-switch-green k8s-stt-status \
        k8s-rag-rebuild k8s-rag-status \
        test test-install test-smoke test-rag test-api test-environments \
        staging-up staging-down staging-rebuild staging-test promote

AGENT_URL      = http://localhost:8000
GRAFANA_URL    = http://localhost:3001
PROMETHEUS_URL = http://localhost:9090
ARGOCD_URL     = https://localhost:8080
JAEGER_URL     = http://localhost:16686
NAMESPACE      = traiteur
CLUSTER        = traiteur
REPO_URL       ?= ""   # Passer via : make argocd-setup REPO_URL=https://github.com/...

## help : Affiche cette aide
help:
	@grep -E '^## ' Makefile | sed 's/## //'

## ─── CI/CD — Qualité et pipeline local ──────────────────────────────────────
##
## Workflow CI (ordre d'exécution dans GitHub Actions) :
##   make lint         → ruff check (syntaxe + imports)
##   make test-unit    → tests purs Python (sans Docker)
##   make ci-local     → simule les 4 jobs CI en local (lint+unit+build+security)

## lint : Vérifie la qualité du code (ruff — syntaxe, imports, style)
lint:
	@command -v ruff >/dev/null || pip install ruff==0.4.4 -q
	ruff check services/agent/app/ tests/test_unit.py
	ruff format --check services/agent/app/ tests/test_unit.py
	@echo "✓ Lint OK"

## lint-fix : Corrige automatiquement les erreurs de style
lint-fix:
	@command -v ruff >/dev/null || pip install ruff==0.4.4 -q
	ruff check --fix services/agent/app/ tests/test_unit.py
	ruff format services/agent/app/ tests/test_unit.py
	@echo "✓ Formatage appliqué"

## test-unit : Tests unitaires purs Python (sans Docker, < 30s)
test-unit:
	@python3 -c "import pytest" 2>/dev/null || pip install pytest -q
	python3 -m pytest tests/test_unit.py -v --tb=short
	@echo "✓ Unit tests OK"

## ci-local : Simule le pipeline CI complet en local
ci-local:
	@bash scripts/ci-local.sh

## ─── OpenTelemetry — Traces distribuées ─────────────────────────────────────
##
## Workflow (après make up ou make k8s-up) :
##   make traces-ui     → ouvre l'UI Jaeger dans le navigateur
##   make traces-demo   → envoie des requêtes test et indique où chercher
##   make traces-disable → désactive le tracing (OTEL_TRACES_ENABLED=false)
##   make traces-enable  → réactive le tracing

## traces-ui : Ouvre l'UI Jaeger
traces-ui:
	@echo "Jaeger UI : $(JAEGER_URL)"
	@echo "Service   : traiteur-agent"
	@xdg-open $(JAEGER_URL) 2>/dev/null || open $(JAEGER_URL) 2>/dev/null || true

## traces-demo : Envoie des requêtes test et guide l'exploration dans Jaeger
traces-demo:
	@bash scripts/traces-demo.sh

## traces-disable : Désactive le tracing OTel (sans redémarrer le service)
traces-disable:
	@echo "Pour désactiver les traces, ajouter OTEL_TRACES_ENABLED=false dans .env"
	@echo "puis relancer : make up"
	@echo "Ou : docker-compose restart agent avec OTEL_TRACES_ENABLED=false"

## traces-enable : Réactive le tracing OTel
traces-enable:
	@echo "Pour réactiver les traces, supprimer OTEL_TRACES_ENABLED=false du .env"
	@echo "puis relancer : make up"

## ─── GitOps — ArgoCD ─────────────────────────────────────────────────────────
##
## Workflow GitOps (après make k8s-up) :
##   make argocd-setup REPO_URL=https://github.com/...  → installe ArgoCD + crée l'Application
##   make argocd-status    → sync status + health
##   make argocd-diff      → différences Git ↔ cluster (avant un push)
##   make argocd-sync      → sync manuel (si auto-sync désactivé)
##   make argocd-demo-drift → démonstration de selfHeal en direct
##   make argocd-ui        → ouvre l'UI ArgoCD dans le navigateur
##
## Principe GitOps :
##   git commit + git push → ArgoCD détecte → sync automatique
##   kubectl edit          → ArgoCD détecte → restaure (selfHeal=true)

## argocd-setup : Installe ArgoCD et crée l'Application (REPO_URL requis)
argocd-setup:
	@bash scripts/argocd-setup.sh $(REPO_URL)

## argocd-status : Affiche l'état de l'Application ArgoCD (sync + health)
argocd-status:
	@echo "=== Application ArgoCD ==="
	@kubectl get application traiteur -n argocd \
	    -o custom-columns="NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status,REPO:.spec.source.repoURL" 2>/dev/null || echo "(Application non trouvée)"
	@echo ""
	@echo "=== Derniers événements ArgoCD ==="
	@kubectl get events -n argocd --sort-by='.lastTimestamp' | tail -10 || true

## argocd-diff : Montre les différences entre Git et le cluster
argocd-diff:
	@if command -v argocd > /dev/null; then \
	    argocd app diff traiteur --grpc-web; \
	else \
	    echo "argocd CLI requis. Utiliser l'UI : $(ARGOCD_URL)"; \
	fi

## argocd-sync : Déclenche un sync manuel
argocd-sync:
	@if command -v argocd > /dev/null; then \
	    argocd app sync traiteur --grpc-web; \
	else \
	    kubectl patch application traiteur -n argocd \
	        --type merge \
	        -p '{"operation":{"initiatedBy":{"username":"make"},"sync":{"revision":"HEAD"}}}'; \
	    echo "✓ Sync déclenché (sans argocd CLI)"; \
	fi

## argocd-rollback : Revient à la version précédente dans l'historique ArgoCD
argocd-rollback:
	@if command -v argocd > /dev/null; then \
	    echo "Historique des syncs :"; \
	    argocd app history traiteur --grpc-web; \
	    echo ""; \
	    read -rp "ID de la révision cible (ou Ctrl+C pour annuler) : " REV; \
	    argocd app rollback traiteur $$REV --grpc-web; \
	else \
	    echo "argocd CLI requis pour rollback. Utiliser l'UI : $(ARGOCD_URL)"; \
	fi

## argocd-password : Affiche le mot de passe admin ArgoCD
argocd-password:
	@echo "ArgoCD admin password :"
	@kubectl get secret argocd-initial-admin-secret \
	    -n argocd \
	    -o jsonpath="{.data.password}" | base64 -d
	@echo ""

## argocd-ui : Ouvre l'UI ArgoCD dans le navigateur
argocd-ui:
	@echo "ArgoCD UI : $(ARGOCD_URL)"
	@echo "Username  : admin"
	@echo "Password  : $$(kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d)"
	@xdg-open $(ARGOCD_URL) 2>/dev/null || open $(ARGOCD_URL) 2>/dev/null || true

## argocd-demo-drift : Démonstration de détection de dérive + selfHeal
argocd-demo-drift:
	@bash scripts/argocd-demo-drift.sh

## ─── Kubernetes — Cycle de vie ───────────────────────────────────────────────
##
## Workflow complet depuis zéro :
##   make k8s-up           → cluster + build + deploy (tout en une commande)
##   make k8s-init-ollama  → télécharge Mistral dans Ollama
##   make k8s-status       → vérifier que tout tourne
##   make test-smoke       → tests rapides

## k8s-up : Déploiement complet (cluster + build + deploy)
k8s-up:
	@bash scripts/k8s-setup.sh

## k8s-down : Supprime le cluster kind (et toutes les ressources)
k8s-down:
	kind delete cluster --name $(CLUSTER)
	@echo "✓ Cluster '$(CLUSTER)' supprimé"

## k8s-status : Affiche l'état de toutes les ressources K8s
k8s-status:
	@echo "=== Pods ==="
	@kubectl get pods -n $(NAMESPACE) -o wide
	@echo ""
	@echo "=== Services ==="
	@kubectl get services -n $(NAMESPACE)
	@echo ""
	@echo "=== HPA ==="
	@kubectl get hpa -n $(NAMESPACE)
	@echo ""
	@echo "=== PVC ==="
	@kubectl get pvc -n $(NAMESPACE)

## k8s-build : Build uniquement les images Docker locales
k8s-build:
	docker build -t traiteur-agent:latest ./services/agent
	docker build -t traiteur-stt:latest   ./services/stt
	docker build -t traiteur-tts:latest   ./services/tts
	docker build -t traiteur-ui:latest    ./ui
	@echo "✓ Images construites"

## k8s-load : Charge les images locales dans le cluster kind
k8s-load:
	kind load docker-image traiteur-agent:latest --name $(CLUSTER)
	kind load docker-image traiteur-stt:latest   --name $(CLUSTER)
	kind load docker-image traiteur-tts:latest   --name $(CLUSTER)
	kind load docker-image traiteur-ui:latest    --name $(CLUSTER)
	@echo "✓ Images chargées dans le cluster"

## k8s-configmaps : Recrée les ConfigMaps depuis data/ et eval/
k8s-configmaps:
	kubectl create configmap traiteur-data \
		--from-file=data/ -n $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	kubectl create configmap traiteur-eval \
		--from-file=eval/ -n $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	@echo "✓ ConfigMaps mises à jour"

## k8s-deploy : Applique tous les manifestes K8s
k8s-deploy:
	kubectl apply -f k8s/00-namespace.yaml
	kubectl apply -f k8s/01-configmap.yaml
	$(MAKE) k8s-configmaps
	kubectl apply -f k8s/
	@echo "✓ Manifestes appliqués"

## k8s-reload-data : Recharge les données (mise à jour ConfigMap + redémarre les pods)
k8s-reload-data:
	@echo "=== Rechargement des données dans K8s ==="
	$(MAKE) k8s-configmaps
	@echo "Redémarrage des pods agent (pour monter les nouvelles données)..."
	kubectl rollout restart deployment/agent -n $(NAMESPACE)
	kubectl rollout status deployment/agent -n $(NAMESPACE) --timeout=300s
	@echo "Rebuild du RAG..."
	curl -s -X POST $(AGENT_URL)/api/rag/rebuild | python3 -m json.tool

## ─── Kubernetes — Ollama ─────────────────────────────────────────────────────

## k8s-init-ollama : Télécharge Mistral dans Ollama (dans le cluster)
k8s-init-ollama:
	@echo "Téléchargement de Mistral dans Ollama (port 11434)..."
	@echo "Cela peut prendre plusieurs minutes selon votre connexion..."
	docker exec -it traiteur-control-plane \
		sh -c "kubectl exec -n $(NAMESPACE) deploy/ollama -- ollama pull mistral" \
		2>/dev/null || \
	ollama pull mistral --host http://localhost:11434 2>/dev/null || \
	curl -s http://localhost:11434/api/pull -d '{"name":"mistral"}' | tail -5
	@echo "✓ Mistral prêt"

## ─── Kubernetes — Logs ───────────────────────────────────────────────────────

## k8s-logs-agent : Logs de tous les pods agent
k8s-logs-agent:
	kubectl logs -n $(NAMESPACE) -l app=agent --all-containers --follow

## k8s-logs-pod : Logs d'un pod spécifique (ex: make k8s-logs-pod POD=agent-xxx)
k8s-logs-pod:
	@test -n "$(POD)" || (echo "Usage: make k8s-logs-pod POD=<pod-name>" && exit 1)
	kubectl logs -n $(NAMESPACE) $(POD) --follow

## k8s-exec-agent : Shell dans un pod agent (pour debug)
k8s-exec-agent:
	kubectl exec -it -n $(NAMESPACE) \
		$$(kubectl get pods -n $(NAMESPACE) -l app=agent -o name | head -1) \
		-- /bin/bash

## ─── Kubernetes — HPA et Scaling ─────────────────────────────────────────────
##
## HPA (Horizontal Pod Autoscaler) :
##   Le HPA surveille le CPU moyen de tous les pods agent.
##   Si CPU > 50% → scale out (max 5 pods)
##   Si CPU < 50% pendant 2min → scale in (min 2 pods)
##
## Pour voir le HPA en action :
##   1. make k8s-hpa-status   → affiche l'état actuel
##   2. make k8s-stress       → génère de la charge pendant 60s
##   3. make k8s-hpa-watch    → surveille le scaling en temps réel

## k8s-hpa-status : Affiche l'état du HPA et la consommation CPU des pods
k8s-hpa-status:
	@echo "=== HPA ==="
	@kubectl get hpa -n $(NAMESPACE)
	@echo ""
	@echo "=== CPU/RAM par pod ==="
	@kubectl top pods -n $(NAMESPACE) --containers 2>/dev/null || \
		echo "metrics-server pas encore prêt — réessayez dans 1 minute"

## k8s-hpa-watch : Surveille le HPA en temps réel (Ctrl+C pour arrêter)
k8s-hpa-watch:
	@echo "Surveillance HPA (Ctrl+C pour arrêter)..."
	@watch -n 5 "kubectl get hpa -n $(NAMESPACE) && echo '' && \
		kubectl get pods -n $(NAMESPACE) -l app=agent && echo '' && \
		kubectl top pods -n $(NAMESPACE) 2>/dev/null || true"

## k8s-scale : Scale manuel de l'agent (ex: make k8s-scale N=3)
k8s-scale:
	@test -n "$(N)" || (echo "Usage: make k8s-scale N=<nombre>" && exit 1)
	kubectl scale deployment/agent -n $(NAMESPACE) --replicas=$(N)
	@echo "Scale agent → $(N) replicas"
	@kubectl get pods -n $(NAMESPACE) -l app=agent

## k8s-stress : Génère de la charge pour déclencher le HPA (60 requêtes en parallèle)
k8s-stress:
	@echo "=== Génération de charge (60s) pour déclencher le HPA ==="
	@echo "Observez le scaling : make k8s-hpa-watch (dans un autre terminal)"
	@echo ""
	@START=$$(date +%s); \
	while [ $$(( $$(date +%s) - $$START )) -lt 60 ]; do \
		for i in 1 2 3 4 5; do \
			curl -s -X POST $(AGENT_URL)/api/text \
				-H "Content-Type: application/json" \
				-d '{"text": "Quel est le prix du bœuf bourguignon ?", "skip_tts": true}' \
				> /dev/null & \
		done; \
		wait; \
		echo -n "."; \
	done; \
	echo ""
	@echo "✓ Charge terminée — le HPA devrait scale down dans ~2 minutes"
	@kubectl get hpa -n $(NAMESPACE)

## ─── Kubernetes — Rolling Update ─────────────────────────────────────────────
##
## Rolling Update : mise à jour de l'agent sans interruption de service
##   K8s remplace les pods un par un. Les requêtes continuent d'être traitées
##   par les anciens pods jusqu'à ce que les nouveaux soient READY.

## k8s-rolling-update : Démo du rolling update (rebuild + redéploiement)
k8s-rolling-update:
	@echo "=== Rolling Update — Démo étape 07 ==="
	@echo ""
	@echo "Étape 1 : État actuel"
	@kubectl get pods -n $(NAMESPACE) -l app=agent
	@echo ""
	@echo "Étape 2 : Rebuild de l'image agent..."
	docker build -t traiteur-agent:latest ./services/agent --quiet
	kind load docker-image traiteur-agent:latest --name $(CLUSTER)
	@echo ""
	@echo "Étape 3 : Rolling update (make k8s-hpa-watch dans un autre terminal)"
	kubectl rollout restart deployment/agent -n $(NAMESPACE)
	@echo ""
	@echo "Étape 4 : Attente (les requêtes continuent pendant le rolling update)"
	kubectl rollout status deployment/agent -n $(NAMESPACE) --timeout=300s
	@echo ""
	@echo "✓ Rolling update terminé"
	kubectl get pods -n $(NAMESPACE) -l app=agent

## k8s-rollout-history : Historique des déploiements
k8s-rollout-history:
	kubectl rollout history deployment/agent -n $(NAMESPACE)

## k8s-rollout-undo : Annule le dernier déploiement (rollback)
k8s-rollout-undo:
	kubectl rollout undo deployment/agent -n $(NAMESPACE)
	@echo "✓ Rollback effectué"

## ─── Kubernetes — Blue/Green STT ─────────────────────────────────────────────
##
## En K8s, le switch B/G se fait via kubectl patch (plus élégant que nginx reload).
## Le Service K8s change de selector → trafic redirigé instantanément.

## k8s-stt-status : Affiche quel modèle STT est actif
k8s-stt-status:
	@echo "=== STT Router (selector actif) ==="
	@kubectl get service stt-router -n $(NAMESPACE) \
		-o jsonpath='color={.spec.selector.color}' && echo ""
	@echo ""
	@echo "=== Pods STT ==="
	@kubectl get pods -n $(NAMESPACE) -l app=stt

## k8s-stt-switch-green : Bascule vers stt-green (Whisper small)
k8s-stt-switch-green:
	bash scripts/k8s-stt-switch.sh green

## k8s-stt-switch-blue : Revient à stt-blue (Whisper base)
k8s-stt-switch-blue:
	bash scripts/k8s-stt-switch.sh blue

## ─── Kubernetes — RAG ────────────────────────────────────────────────────────

## k8s-rag-rebuild : Lance un rebuild RAG (quality gate incluse)
k8s-rag-rebuild:
	curl -s -X POST $(AGENT_URL)/api/rag/rebuild | python3 -m json.tool

## k8s-rag-status : État du RAG
k8s-rag-status:
	curl -s $(AGENT_URL)/api/rag/status | python3 -m json.tool

## k8s-rag-search : Recherche brute dans le RAG
k8s-rag-search:
	@test -n "$(Q)" || (echo "Usage: make k8s-rag-search Q=\"votre question\"" && exit 1)
	@curl -s "$(AGENT_URL)/api/rag/search?q=$(Q)&k=3" | python3 -m json.tool

## ─── Tests automatisés ───────────────────────────────────────────────────────

## test-install : Installe pytest + httpx
test-install:
	pip install -r requirements-test.txt -q
	@echo "✓ pytest + httpx installés"

## test-smoke : Tests rapides sans LLM (health, métriques, RAG)
test-smoke:
	@python3 -c "import pytest, httpx" 2>/dev/null || (echo "make test-install" && exit 1)
	python3 -m pytest tests/test_smoke.py -v --tb=short

## test-rag : Quality gate RAG (sans LLM, < 30s)
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

## test : Lance tous les tests
test:
	@python3 -c "import pytest, httpx" 2>/dev/null || (echo "make test-install" && exit 1)
	python3 -m pytest tests/ -v --tb=short

## ─── Observabilité ───────────────────────────────────────────────────────────

## metrics : Métriques Prometheus de l'agent
metrics:
	curl -s $(AGENT_URL)/metrics | grep -v "^#" | grep -E "(rag_|quality_gate|conversation)"

## grafana : Ouvre Grafana
grafana:
	@xdg-open $(GRAFANA_URL) 2>/dev/null || open $(GRAFANA_URL) 2>/dev/null || echo "→ $(GRAFANA_URL)"

## prometheus : Ouvre Prometheus
prometheus:
	@xdg-open $(PROMETHEUS_URL) 2>/dev/null || open $(PROMETHEUS_URL) 2>/dev/null || echo "→ $(PROMETHEUS_URL)"

## ─── Staging (hérité étape 06 — avec Docker Compose) ────────────────────────

## staging-up : Démarre le staging avec Docker Compose (si production K8s est down)
staging-up:
	docker compose -f docker-compose.yml -f docker-compose.staging.yml up -d agent-staging

## staging-down : Arrête le staging
staging-down:
	docker compose -f docker-compose.yml -f docker-compose.staging.yml stop agent-staging
	docker compose -f docker-compose.yml -f docker-compose.staging.yml rm -f agent-staging

## staging-rebuild : Rebuild RAG staging
staging-rebuild:
	curl -s -X POST http://localhost:8100/api/rag/rebuild | python3 -m json.tool

## staging-test : Tests sur staging
staging-test:
	AGENT_URL=http://localhost:8100 python3 -m pytest \
		tests/test_smoke.py tests/test_rag_quality.py -v --tb=short

## promote : Promeut staging → production
promote:
	bash scripts/promote.sh

## ─── Nettoyage ───────────────────────────────────────────────────────────────

## clean : Supprime le cluster kind
clean: k8s-down

## clean-orders : Supprime les fichiers Excel de commandes
clean-orders:
	rm -f orders/*.xlsx orders-staging/*.xlsx
