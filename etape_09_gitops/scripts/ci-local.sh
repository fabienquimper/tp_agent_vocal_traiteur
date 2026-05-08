#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# ci-local.sh — Simule le pipeline CI en local
# Étape 08 : CI/CD
#
# Ce script reproduit exactement les 4 jobs du pipeline GitHub Actions :
#   1. lint         → ruff check + format
#   2. unit-tests   → pytest test_unit.py
#   3. docker-build → docker build des 4 images
#   4. security     → trivy scan (si trivy est installé, sinon skippé)
#
# Utilité :
#   → Vérifier en local avant de pousser sur GitHub
#   → Comprendre ce que fait le CI sans lire le YAML
#   → Diagnostiquer un échec CI sans attendre les runners
#
# Usage :
#   bash scripts/ci-local.sh          # tous les jobs
#   bash scripts/ci-local.sh lint     # job lint uniquement
#   bash scripts/ci-local.sh unit     # tests unitaires uniquement
#   bash scripts/ci-local.sh build    # build Docker uniquement
#   bash scripts/ci-local.sh security # scan Trivy uniquement
#
# Prérequis : python3, pip, docker
# Optionnel  : ruff (pip install ruff), trivy (https://aquasecurity.github.io/trivy)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Couleurs ─────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
step() { echo -e "\n${BLUE}══${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
fail() { echo -e "${RED}✗${NC} $*"; exit 1; }

# ── Fonctions par job ─────────────────────────────────────────────────────────

job_lint() {
    step "Job 1/4 : Lint (ruff)"

    if ! command -v ruff > /dev/null 2>&1; then
        warn "ruff non installé — installation..."
        pip install ruff==0.4.4 -q
    fi

    echo "  Vérification syntaxe + imports..."
    ruff check services/agent/app/ tests/test_unit.py && ok "ruff check OK"

    echo "  Vérification formatage..."
    ruff format --check services/agent/app/ tests/test_unit.py && ok "ruff format OK"
}

job_unit_tests() {
    step "Job 2/4 : Tests unitaires"

    # Vérifier les dépendances Python de l'agent
    echo "  Vérification des dépendances Python..."
    if ! python3 -c "import pydantic_settings, fastapi" 2>/dev/null; then
        warn "Dépendances agent manquantes — installation depuis services/agent/requirements.txt..."
        pip install -r services/agent/requirements.txt -q
    fi

    # Installer pytest si absent
    if ! python3 -c "import pytest" 2>/dev/null; then
        pip install pytest pytest-asyncio -q
    fi

    echo "  Exécution de tests/test_unit.py..."
    python3 -m pytest tests/test_unit.py -v --tb=short
    ok "Tests unitaires OK"
}

job_docker_build() {
    step "Job 3/4 : Docker Build"

    if ! command -v docker > /dev/null 2>&1; then
        fail "docker non trouvé — requis pour ce job"
    fi

    echo "  Build traiteur-agent..."
    docker build -t traiteur-agent:ci services/agent --quiet && ok "traiteur-agent:ci"

    echo "  Build traiteur-stt..."
    docker build -t traiteur-stt:ci services/stt --quiet && ok "traiteur-stt:ci"

    echo "  Build traiteur-tts..."
    docker build -t traiteur-tts:ci services/tts --quiet && ok "traiteur-tts:ci"

    echo "  Build traiteur-ui..."
    docker build -t traiteur-ui:ci ui --quiet && ok "traiteur-ui:ci"

    echo "  Build mock-ollama..."
    docker build -t mock-ollama:ci mock-ollama --quiet && ok "mock-ollama:ci"
}

job_security() {
    step "Job 4/4 : Security Scan (Trivy)"

    if ! command -v trivy > /dev/null 2>&1; then
        warn "trivy non installé — job skippé"
        warn "Pour installer trivy : https://aquasecurity.github.io/trivy/latest/getting-started/installation/"
        return 0
    fi

    echo "  Scan traiteur-agent:ci (CRITICAL + HIGH CVE)..."
    trivy image \
        --severity CRITICAL,HIGH \
        --ignore-unfixed \
        --exit-code 1 \
        traiteur-agent:ci \
        && ok "traiteur-agent: aucune CVE critique/haute non corrigée"

    echo "  Scan filesystem services/agent (dépendances Python)..."
    trivy fs \
        --severity CRITICAL,HIGH \
        --exit-code 1 \
        services/agent \
        && ok "Dépendances Python: aucune CVE critique/haute"
}

# ── Main ─────────────────────────────────────────────────────────────────────

# S'assurer d'être dans le bon dossier
cd "$(dirname "$0")/.."

echo ""
echo "════════════════════════════════════════════════"
echo "  CI Local — Traiteur Dupont (étape 08)"
echo "════════════════════════════════════════════════"

JOB="${1:-all}"
START=$(date +%s)

case "$JOB" in
    lint)     job_lint ;;
    unit)     job_unit_tests ;;
    build)    job_docker_build ;;
    security) job_security ;;
    all)
        job_lint
        job_unit_tests
        job_docker_build
        job_security
        ;;
    *)
        echo "Usage: $0 [lint|unit|build|security|all]"
        exit 1
        ;;
esac

END=$(date +%s)
ELAPSED=$((END - START))

echo ""
echo "════════════════════════════════════════════════"
ok "Pipeline CI local terminé en ${ELAPSED}s"
echo "════════════════════════════════════════════════"
