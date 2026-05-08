"""
Tests quality gate RAG — évaluation du hit rate
─────────────────────────────────────────────────
Ce fichier reproduit la logique de la quality gate embarquée dans le retriever.
Il évalue le hit rate du RAG actif via GET /api/rag/search (pas de LLM).

Concepts testés :
  - Hit rate : % de requêtes qui retournent au moins 1 chunk
  - Threshold : seuil minimum (80% par défaut)
  - Régression : un test qui échoue = l'index a régressé

Avantages de tester via /api/rag/search plutôt que /api/text :
  1. Rapide (< 5s pour 15 requêtes, pas de LLM)
  2. Déterministe (toujours le même résultat pour le même index)
  3. Ciblé : teste uniquement le RAG, pas le LLM

Lancement : make test-rag
"""

import json
import pytest
import httpx
from pathlib import Path

# Chargement du jeu d'évaluation
EVAL_FILE = Path(__file__).parent.parent / "eval" / "rag_quality_eval.json"
RAG_QUALITY_THRESHOLD = 0.8  # 80% — doit correspondre à rag_quality_threshold dans config.py


def load_eval_queries() -> list[dict]:
    """Charge les requêtes d'évaluation depuis eval/rag_quality_eval.json."""
    assert EVAL_FILE.exists(), (
        f"Fichier d'évaluation introuvable : {EVAL_FILE}\n"
        "Ce fichier doit exister pour que les tests quality gate fonctionnent."
    )
    return json.loads(EVAL_FILE.read_text(encoding="utf-8"))


class TestRagQualityGate:
    """
    Tests du contrôle qualité RAG.

    Reproduit exactement ce que fait _check_quality_gate() dans retriever.py.
    La différence : ces tests s'exécutent depuis l'extérieur (via HTTP),
    tandis que la quality gate s'exécute de l'intérieur (avant le swap).
    """

    @pytest.fixture(scope="class")
    def eval_queries(self) -> list[dict]:
        return load_eval_queries()

    @pytest.fixture(scope="class")
    def search_results(self, fast_client: httpx.Client, eval_queries: list[dict]) -> list[dict]:
        """
        Exécute toutes les requêtes d'évaluation et collecte les résultats.
        Fixture de classe pour n'exécuter les recherches qu'une seule fois.
        """
        results = []
        for item in eval_queries:
            query = item.get("query", "").strip()
            if not query:
                continue
            r = fast_client.get("/api/rag/search", params={"q": query, "k": 1})
            assert r.status_code == 200, f"Erreur HTTP pour '{query}': {r.status_code}"
            data = r.json()
            results.append({
                "query": query,
                "topic": item.get("topic", ""),
                "description": item.get("description", ""),
                "hits": data["hits"],
                "chunks": data["chunks"],
            })
        return results

    def test_eval_file_exists(self):
        """Le fichier d'évaluation doit exister."""
        assert EVAL_FILE.exists(), f"Fichier manquant : {EVAL_FILE}"

    def test_eval_file_has_queries(self, eval_queries: list[dict]):
        """Le fichier d'évaluation doit contenir des requêtes."""
        assert len(eval_queries) >= 5, (
            f"Trop peu de requêtes ({len(eval_queries)}). "
            "Un jeu d'évaluation pertinent doit avoir au moins 5 requêtes."
        )

    def test_global_hit_rate_above_threshold(self, search_results: list[dict]):
        """
        Le hit rate global doit dépasser le seuil configuré.

        C'est le test le plus important : il reproduit exactement la décision
        prise par la quality gate lors d'un rebuild.
        Si ce test échoue → la quality gate bloquerait un rebuild → l'index actuel
        ne sera jamais remplacé tant que ce problème n'est pas résolu.
        """
        total = len(search_results)
        hits = sum(1 for r in search_results if r["hits"] > 0)
        hit_rate = hits / total if total > 0 else 0.0

        # Affiche un rapport détaillé pour le débogage
        misses = [r for r in search_results if r["hits"] == 0]
        if misses:
            miss_info = "\n".join(
                f"  - [{r['topic']}] {r['query']}"
                for r in misses
            )
            pytest.fail(
                f"Hit rate trop bas : {hit_rate:.1%} ({hits}/{total}) "
                f"< seuil={RAG_QUALITY_THRESHOLD:.0%}\n\n"
                f"Requêtes sans résultat ({len(misses)}) :\n{miss_info}\n\n"
                "→ Ces requêtes n'ont pas de chunk correspondant dans ChromaDB.\n"
                "→ Vérifiez que les fichiers data/*.txt sont bien indexés."
            )

        assert hit_rate >= RAG_QUALITY_THRESHOLD, (
            f"Hit rate {hit_rate:.1%} < seuil {RAG_QUALITY_THRESHOLD:.0%}"
        )

    def test_horaires_topic_hits(self, search_results: list[dict]):
        """Les requêtes sur les horaires doivent toutes retourner des résultats."""
        horaires = [r for r in search_results if r["topic"] == "horaires"]
        if not horaires:
            pytest.skip("Pas de requêtes 'horaires' dans le jeu d'évaluation")

        failures = [r for r in horaires if r["hits"] == 0]
        assert not failures, (
            f"Requêtes 'horaires' sans résultat : "
            f"{[r['query'] for r in failures]}\n"
            "→ Vérifiez que data/horaires.txt est bien indexé."
        )

    def test_menus_topic_hits(self, search_results: list[dict]):
        """Les requêtes sur les menus/produits doivent retourner des résultats."""
        menus = [r for r in search_results if r["topic"] == "menus"]
        if not menus:
            pytest.skip("Pas de requêtes 'menus' dans le jeu d'évaluation")

        hits_count = sum(1 for r in menus if r["hits"] > 0)
        hit_rate = hits_count / len(menus)
        assert hit_rate >= 0.7, (
            f"Hit rate menus trop bas : {hit_rate:.1%} ({hits_count}/{len(menus)})\n"
            "→ Vérifiez que data/menus.txt est bien indexé."
        )

    def test_chunks_have_content(self, search_results: list[dict]):
        """Tous les chunks retournés doivent avoir du contenu non vide."""
        for result in search_results:
            for chunk in result["chunks"]:
                assert chunk["content"].strip(), (
                    f"Chunk vide retourné pour '{result['query']}'"
                )

    def test_search_response_time(self, fast_client: httpx.Client):
        """
        Une recherche RAG doit être rapide (< 2s).
        Si ce test échoue, l'indexation est peut-être corrompue ou
        le service ChromaDB est surchargé.
        """
        import time
        t0 = time.time()
        r = fast_client.get("/api/rag/search", params={"q": "horaires samedi", "k": 3})
        elapsed = time.time() - t0

        assert r.status_code == 200
        assert elapsed < 2.0, (
            f"Recherche RAG trop lente : {elapsed:.2f}s (seuil : 2s)\n"
            "→ ChromaDB est peut-être surchargé ou l'index est fragmenté."
        )


class TestQualityGateIntegration:
    """
    Tests de l'intégration quality gate avec l'état du RAG.
    """

    def test_rebuild_status_has_quality_gate_field_after_rebuild(
        self, fast_client: httpx.Client
    ):
        """
        Après un rebuild, le statut doit inclure le champ 'quality_gate'.
        Si absent, l'agent tourne encore sur le code de l'étape 04.
        """
        r = fast_client.get("/api/rag/status")
        assert r.status_code == 200
        data = r.json()

        # Ce test passe seulement si un rebuild a déjà eu lieu
        # (le champ quality_gate n'est présent qu'après le premier rebuild)
        if data["state"] in ("done", "quality_gate_failed"):
            assert "quality_gate" in data, (
                "Le champ 'quality_gate' est absent après un rebuild.\n"
                "→ L'agent tourne peut-être encore sur le code de l'étape 04."
            )
            qg = data["quality_gate"]
            assert "hit_rate" in qg
            assert "passed" in qg
            assert "threshold" in qg
            assert 0.0 <= qg["hit_rate"] <= 1.0
        else:
            pytest.skip(
                f"Aucun rebuild effectué (state={data['state']}). "
                "Lancez `make rag-rebuild` puis attendez la fin avant de relancer ce test."
            )
