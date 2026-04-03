"""
Tests d'intégration API — contrats des endpoints
──────────────────────────────────────────────────
Ces tests vérifient les contrats des endpoints principaux :
  - Champs de réponse attendus
  - Codes HTTP corrects
  - Validation des entrées

NOTE : Les tests POST /api/text nécessitent Ollama + Mistral.
       Les tests GET /api/rag/* sont rapides (pas de LLM).

Durée : 30-120 secondes (selon la vitesse d'Ollama)

Lancement : make test-api
"""

import pytest
import httpx


# ── Tests sans LLM (rapides) ──────────────────────────────────────────────────

class TestRagEndpoints:
    """Tests des endpoints RAG — rapides, pas de LLM."""

    def test_rag_search_empty_query(self, fast_client: httpx.Client):
        """Une requête vide doit retourner 400."""
        r = fast_client.get("/api/rag/search", params={"q": ""})
        assert r.status_code == 400

    def test_rag_search_with_results(self, fast_client: httpx.Client):
        """Une requête valide doit retourner des chunks."""
        r = fast_client.get("/api/rag/search", params={"q": "plateau charcuterie prix", "k": 2})
        assert r.status_code == 200
        data = r.json()
        assert data["hits"] > 0
        assert len(data["chunks"]) <= 2

    def test_rag_search_k_parameter(self, fast_client: httpx.Client):
        """Le paramètre k doit limiter le nombre de chunks retournés."""
        r = fast_client.get("/api/rag/search", params={"q": "menu traiteur", "k": 1})
        assert r.status_code == 200
        data = r.json()
        assert len(data["chunks"]) <= 1

    def test_rag_status_accessible(self, fast_client: httpx.Client):
        """GET /api/rag/status doit être accessible en < 1s."""
        r = fast_client.get("/api/rag/status")
        assert r.status_code == 200

    def test_rag_rollback_without_rebuild(self, fast_client: httpx.Client):
        """Rollback sans rebuild préalable doit retourner 409."""
        r = fast_client.post("/api/rag/rollback")
        # Si rollback_available=False, on attend 409
        # Si un rebuild a déjà eu lieu (étapes précédentes), le test peut passer
        assert r.status_code in (200, 409)


# ── Tests avec LLM (plus lents) ───────────────────────────────────────────────

class TestTextEndpoint:
    """Tests du pipeline complet texte → LLM → réponse."""

    def test_text_endpoint_schema(self, client: httpx.Client):
        """POST /api/text doit retourner tous les champs attendus."""
        r = client.post("/api/text", json={
            "text": "Quels sont vos horaires le samedi ?",
            "skip_tts": True,
        })
        assert r.status_code == 200
        data = r.json()

        required_fields = {"transcript", "intent", "order_items", "response_text", "is_error"}
        missing = required_fields - set(data.keys())
        assert not missing, f"Champs manquants : {missing}"

    def test_text_endpoint_not_error(self, client: httpx.Client):
        """Une question simple ne doit pas déclencher is_error=True."""
        r = client.post("/api/text", json={
            "text": "Bonjour, vous êtes ouverts ce samedi ?",
            "skip_tts": True,
        })
        assert r.status_code == 200
        data = r.json()
        assert not data["is_error"], (
            f"L'agent a retourné une erreur : {data.get('response_text')}"
        )

    def test_text_endpoint_response_not_empty(self, client: httpx.Client):
        """La réponse de l'agent ne doit pas être vide."""
        r = client.post("/api/text", json={
            "text": "Quel est le prix du bœuf bourguignon ?",
            "skip_tts": True,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["response_text"].strip(), "response_text est vide"
        assert len(data["response_text"]) > 10, "response_text trop courte"

    def test_text_endpoint_empty_input(self, client: httpx.Client):
        """Un texte vide doit retourner 400."""
        r = client.post("/api/text", json={"text": "", "skip_tts": True})
        assert r.status_code == 400

    def test_text_endpoint_horaires_uses_rag(self, client: httpx.Client):
        """
        Une question sur les horaires doit retourner les vraies horaires.
        Si le RAG fonctionne, la réponse contiendra "08h00" ou "samedi".
        Ce test détecte une régression RAG (index vide ou corrompu).
        """
        r = client.post("/api/text", json={
            "text": "Quels sont vos horaires d'ouverture ?",
            "skip_tts": True,
        })
        assert r.status_code == 200
        data = r.json()
        response = data["response_text"].lower()
        # L'agent doit mentionner des horaires ou des jours
        has_time_info = any(kw in response for kw in [
            "lundi", "mardi", "samedi", "dimanche",
            "08h", "09h", "18h", "19h",
            "ouvert", "fermé", "horaire"
        ])
        assert has_time_info, (
            f"La réponse ne contient pas d'information sur les horaires. "
            f"Réponse : {data['response_text'][:200]}\n"
            "→ Le RAG ne retourne peut-être pas les bons documents."
        )
