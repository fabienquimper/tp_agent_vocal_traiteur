"""
Tests d'isolation des environnements — staging vs production
─────────────────────────────────────────────────────────────
Ces tests vérifient que les environnements sont bien isolés :
  - Staging a ses propres données (marqueurs "STAGING" dans les réponses)
  - Production n'a PAS de données staging
  - Le health endpoint révèle l'environnement courant

Principe :
  Les données staging contiennent des marqueurs uniques :
    - "Assiette Démo Staging"   ← dans data-staging/menus.txt
    - "STAGING_PROMO_TEST_2025" ← dans data-staging/promotions.txt
  Ces marqueurs ne doivent JAMAIS apparaître en production.

Lancement :
  make test-environments             # contre l'environnement détecté
  make staging-test                  # forcer staging (port 8100)
  AGENT_URL=http://localhost:8100 python3 -m pytest tests/test_environments.py -v
"""

import os
import pytest
import httpx


AGENT_URL = os.environ.get("AGENT_URL", "http://localhost:8000")
IS_STAGING = "8100" in AGENT_URL


class TestEnvironmentIdentity:
    """Vérifie que l'agent sait dans quel environnement il tourne."""

    def test_health_returns_env_field(self, fast_client: httpx.Client):
        """
        GET /health doit inclure le champ 'env'.
        Si absent → l'agent tourne sur le code de l'étape 05 (pas mis à jour).
        """
        r = fast_client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "env" in data, (
            "Champ 'env' absent de /health. "
            "L'agent tourne peut-être sur le code de l'étape 05."
        )
        assert data["env"] in ("staging", "production"), (
            f"Valeur 'env' inattendue : {data['env']}"
        )

    def test_staging_env_on_port_8100(self, fast_client: httpx.Client):
        """
        Sur le port 8100 (staging), env doit être 'staging'.
        Vérifie que la variable APP_ENV est bien injectée par docker-compose.staging.yml.
        """
        if not IS_STAGING:
            pytest.skip("Test staging : relancez avec AGENT_URL=http://localhost:8100")

        r = fast_client.get("/health")
        data = r.json()
        assert data["env"] == "staging", (
            f"env={data['env']} sur le port 8100. "
            "Vérifiez que APP_ENV=staging est bien défini dans docker-compose.staging.yml."
        )

    def test_production_env_on_port_8000(self, fast_client: httpx.Client):
        """
        Sur le port 8000 (production), env doit être 'production'.
        """
        if IS_STAGING:
            pytest.skip("Test production : relancez avec AGENT_URL=http://localhost:8000")

        r = fast_client.get("/health")
        data = r.json()
        assert data["env"] == "production", (
            f"env={data['env']} sur le port 8000. "
            "Vérifiez que APP_ENV n'est pas 'staging' dans docker-compose.yml."
        )


class TestDataIsolation:
    """
    Vérifie que staging et production utilisent des données différentes.

    Principe des marqueurs :
      data-staging/ contient des éléments fictifs ("Assiette Démo Staging")
      absents de data/. Un test qui trouve ces marqueurs sait qu'il est en staging.
    """

    STAGING_MARKER = "Assiette Démo Staging"
    STAGING_PROMO_MARKER = "STAGING_PROMO_TEST_2025"

    def test_staging_has_staging_data(self, fast_client: httpx.Client):
        """
        En staging (port 8100), le marqueur staging doit être présent dans l'index.
        Si absent → les données staging ne sont pas indexées.
        """
        if not IS_STAGING:
            pytest.skip("Test staging : relancez avec AGENT_URL=http://localhost:8100")

        r = fast_client.get("/api/rag/search",
                            params={"q": self.STAGING_MARKER, "k": 3})
        assert r.status_code == 200
        data = r.json()
        assert data["hits"] > 0, (
            f"Marqueur staging '{self.STAGING_MARKER}' introuvable dans l'index staging.\n"
            "→ Les données data-staging/ ne sont pas correctement indexées.\n"
            "→ Lancez : make staging-rebuild"
        )

        # Le chunk doit contenir le marqueur
        found = any(
            self.STAGING_MARKER.lower() in chunk["content"].lower()
            for chunk in data["chunks"]
        )
        assert found, (
            f"Marqueur '{self.STAGING_MARKER}' absent des chunks retournés.\n"
            f"Chunks reçus : {[c['content'][:100] for c in data['chunks']]}"
        )

    def test_production_does_not_have_staging_data(self, fast_client: httpx.Client):
        """
        En production (port 8000), le marqueur staging NE DOIT PAS être présent.
        Si présent → une promotion de données staging a eu lieu par erreur, ou
        data/ contient des données de test non nettoyées.

        C'est le test LE PLUS IMPORTANT de l'isolation des environnements.
        """
        if IS_STAGING:
            pytest.skip("Test production : relancez avec AGENT_URL=http://localhost:8000")

        r = fast_client.get("/api/rag/search",
                            params={"q": self.STAGING_MARKER, "k": 3})
        assert r.status_code == 200
        data = r.json()

        # Vérifier que aucun chunk ne contient le marqueur staging
        contaminated = [
            chunk for chunk in data["chunks"]
            if self.STAGING_MARKER.lower() in chunk["content"].lower()
            or self.STAGING_PROMO_MARKER.lower() in chunk["content"].lower()
        ]
        assert not contaminated, (
            f"ALERTE : données staging détectées en production !\n"
            f"Chunks contaminés : {[c['content'][:200] for c in contaminated]}\n\n"
            "Causes possibles :\n"
            "  1. Une promotion de données staging a échoué à mi-chemin\n"
            "  2. data/ a été modifié manuellement avec des données de test\n\n"
            "Actions :\n"
            "  1. Restaurez la sauvegarde : cp -r data-backup-XXXX/. data/\n"
            "  2. Relancez le rebuild production : make rag-rebuild"
        )

    def test_staging_promo_marker_isolated(self, fast_client: httpx.Client):
        """Vérifie l'isolation du marqueur de promotion staging."""
        if IS_STAGING:
            pytest.skip("Ce test est pour la production uniquement")

        r = fast_client.get("/api/rag/search",
                            params={"q": "STAGING_PROMO_TEST_2025 promotion test", "k": 3})
        assert r.status_code == 200
        data = r.json()

        contaminated = [
            chunk for chunk in data["chunks"]
            if self.STAGING_PROMO_MARKER in chunk["content"]
        ]
        assert not contaminated, (
            f"Marqueur de promo staging trouvé en production ! "
            f"Restaurez les données de production depuis la sauvegarde."
        )


class TestPromotionReadiness:
    """
    Vérifie que staging est dans un état valide pour lancer une promotion.
    Ces tests sont lancés par scripts/promote.sh avant de copier les données.
    """

    def test_staging_index_is_healthy(self, fast_client: httpx.Client):
        """L'index staging doit avoir des chunks actifs."""
        if not IS_STAGING:
            pytest.skip("Test staging uniquement")

        r = fast_client.get("/api/rag/status")
        data = r.json()
        assert data["chunks_active"] > 10, (
            f"Index staging trop petit ({data['chunks_active']} chunks). "
            "Relancez : make staging-rebuild"
        )

    def test_staging_quality_gate_passed(self, fast_client: httpx.Client):
        """
        Si un rebuild a eu lieu en staging, la quality gate doit avoir passé.
        Un staging dont la quality gate a échoué ne doit pas être promu.
        """
        if not IS_STAGING:
            pytest.skip("Test staging uniquement")

        r = fast_client.get("/api/rag/status")
        data = r.json()

        state = data.get("state")
        if state == "quality_gate_failed":
            pytest.fail(
                "La quality gate staging a échoué — promotion impossible.\n"
                f"Erreur : {data.get('error')}\n"
                "Corrigez les données staging puis relancez : make staging-rebuild"
            )

        if "quality_gate" in data:
            qg = data["quality_gate"]
            assert qg.get("passed", True), (
                f"Quality gate staging : hit_rate={qg.get('hit_rate'):.1%} "
                f"< seuil={qg.get('threshold')}"
            )
