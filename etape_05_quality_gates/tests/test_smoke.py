"""
Tests smoke — vérification des endpoints critiques
────────────────────────────────────────────────────
Ces tests ne nécessitent PAS Ollama. Ils vérifient que les services
répondent correctement (health, métriques, état RAG).

Durée : < 5 secondes

Lancement : make test-smoke
"""

import pytest
import httpx


def test_health(fast_client: httpx.Client):
    """L'agent doit répondre avec status=ok."""
    r = fast_client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["service"] == "agent"


def test_metrics_endpoint_accessible(fast_client: httpx.Client):
    """Le endpoint /metrics doit être accessible (scrape Prometheus)."""
    r = fast_client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]


def test_metrics_contains_rag_counters(fast_client: httpx.Client):
    """
    Les métriques RAG doivent être présentes dans /metrics.
    Si elles sont absentes, le dashboard Grafana sera vide.
    """
    r = fast_client.get("/metrics")
    body = r.text
    assert "rag_requests_total" in body, "Métrique rag_requests_total absente"
    assert "rag_active_chunks" in body, "Métrique rag_active_chunks absente"
    assert "rag_rebuild_in_progress" in body, "Métrique rag_rebuild_in_progress absente"


def test_metrics_contains_quality_gate(fast_client: httpx.Client):
    """
    Les métriques quality gate (étape 05) doivent être présentes.
    Prouve que l'agent a bien été mis à jour par rapport à l'étape 04.
    """
    r = fast_client.get("/metrics")
    body = r.text
    assert "rag_quality_gate_total" in body, "Métrique rag_quality_gate_total absente"
    assert "rag_quality_gate_hit_rate" in body, "Métrique rag_quality_gate_hit_rate absente"


def test_rag_status_schema(fast_client: httpx.Client):
    """
    GET /api/rag/status doit retourner un JSON avec les champs obligatoires.
    """
    r = fast_client.get("/api/rag/status")
    assert r.status_code == 200
    data = r.json()
    assert "state" in data, "Champ 'state' absent"
    assert "active_collection" in data, "Champ 'active_collection' absent"
    assert "chunks_active" in data, "Champ 'chunks_active' absent"
    assert data["state"] in {"idle", "rebuilding", "done", "error", "quality_gate_failed"}, \
        f"État inconnu : {data['state']}"


def test_rag_status_chunks_positive(fast_client: httpx.Client):
    """
    Le RAG doit avoir indexé des chunks au démarrage.
    Si chunks_active == 0, le RAG est vide → toutes les réponses seront dégradées.
    """
    r = fast_client.get("/api/rag/status")
    data = r.json()
    assert data["chunks_active"] > 0, (
        f"chunks_active = {data['chunks_active']} : le RAG est vide. "
        "Vérifiez que l'indexation initiale s'est bien passée (make logs-agent)."
    )


def test_rag_search_returns_results(fast_client: httpx.Client):
    """
    GET /api/rag/search doit retourner des chunks pour une requête connue.
    Test rapide sans LLM — vérifie juste que ChromaDB répond.
    """
    r = fast_client.get("/api/rag/search", params={"q": "horaires ouverture", "k": 3})
    assert r.status_code == 200
    data = r.json()
    assert "hits" in data
    assert "chunks" in data
    assert data["hits"] > 0, "Aucun chunk retourné pour 'horaires ouverture'"
    # Chaque chunk doit avoir content, source, score
    for chunk in data["chunks"]:
        assert "content" in chunk
        assert "score" in chunk
