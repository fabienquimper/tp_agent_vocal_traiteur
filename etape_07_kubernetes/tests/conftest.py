"""
Configuration pytest — fixtures partagées
──────────────────────────────────────────
Ces tests sont des tests d'intégration : ils nécessitent que le stack Docker
soit démarré (`make up` + `make init-ollama`).

Variable d'environnement :
  AGENT_URL  : URL de base de l'agent (défaut : http://localhost:8000)

Lancement :
  make test           # tous les tests
  make test-smoke     # tests rapides sans Ollama
  make test-rag       # tests RAG quality uniquement
"""

import os
import pytest
import httpx

# URL de base — configurable via variable d'environnement
BASE_URL = os.environ.get("AGENT_URL", "http://localhost:8000")

# Timeout généreux pour les appels LLM (Mistral peut être lent)
LLM_TIMEOUT = 120.0
# Timeout court pour les endpoints sans LLM (health, metrics, RAG search)
FAST_TIMEOUT = 10.0


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def client() -> httpx.Client:
    """Client HTTP synchrone réutilisé pour toute la session de tests."""
    with httpx.Client(base_url=BASE_URL, timeout=LLM_TIMEOUT) as c:
        yield c


@pytest.fixture(scope="session")
def fast_client() -> httpx.Client:
    """Client HTTP avec timeout court — pour les endpoints sans LLM."""
    with httpx.Client(base_url=BASE_URL, timeout=FAST_TIMEOUT) as c:
        yield c
