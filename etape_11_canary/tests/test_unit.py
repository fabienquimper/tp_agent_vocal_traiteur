"""
Tests unitaires — étape 08 CI/CD
──────────────────────────────────
Ces tests :
  - N'ont besoin d'AUCUN service externe (ni Docker, ni Ollama, ni ChromaDB)
  - S'exécutent en millisecondes (< 1s total)
  - Testent la logique métier pure (fonctions Python)

Ils constituent le premier job du pipeline CI (lint → unit-tests → docker-build → security).
Ils s'exécutent aussi en local sans rien démarrer.

Pourquoi des tests unitaires séparés des tests d'intégration ?
  ┌─────────────────────────────────────────────────────┐
  │  Tests unitaires  →  rapides, infra-free, feedback  │
  │  Tests d'intégration → lents, nécessitent Docker    │
  └─────────────────────────────────────────────────────┘
  Le CI peut détecter 80% des bugs avec les tests unitaires
  en < 1 minute, AVANT de démarrer un cluster K8s (20-30 min).
"""

import sys
import os

# Ajouter services/agent au sys.path pour importer les modules sans Docker
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "agent"))

import pytest

# ── Import des fonctions testables ───────────────────────────────────────────
# Ces imports ne lancent PAS de connexions réseau :
# - pydantic_settings lit les valeurs par défaut (pas besoin de .env)
# - ChatOllama ne se connecte qu'au premier invoke(), pas à l'import
from app.config import Settings
from app.main import _detect_payment_method, _extract_phone


# ═══════════════════════════════════════════════════════════════════════════════
# _detect_payment_method : détecte CB ou liquide
# ═══════════════════════════════════════════════════════════════════════════════

class TestDetectPaymentMethod:
    """Logique métier : reconnaissance du mode de paiement depuis un texte libre."""

    def test_cb_keyword(self):
        assert _detect_payment_method("je paie par CB") == "CB"

    def test_carte_keyword(self):
        assert _detect_payment_method("par carte s'il vous plaît") == "CB"

    def test_bancaire_keyword(self):
        assert _detect_payment_method("carte bancaire") == "CB"

    def test_visa_keyword(self):
        assert _detect_payment_method("j'ai une Visa") == "CB"

    def test_mastercard_keyword(self):
        assert _detect_payment_method("paiement Mastercard") == "CB"

    def test_credit_accent(self):
        assert _detect_payment_method("crédit") == "CB"

    def test_credit_no_accent(self):
        assert _detect_payment_method("credit card") == "CB"

    def test_liquide_keyword(self):
        assert _detect_payment_method("en liquide") == "liquide"

    def test_especes_keyword(self):
        assert _detect_payment_method("je paye en espèces") == "liquide"

    def test_especes_no_accent(self):
        assert _detect_payment_method("especes") == "liquide"

    def test_cash_keyword(self):
        assert _detect_payment_method("cash please") == "liquide"

    def test_case_insensitive(self):
        assert _detect_payment_method("CARTE BANCAIRE") == "CB"
        assert _detect_payment_method("LIQUIDE") == "liquide"

    def test_unrecognized_returns_none(self):
        assert _detect_payment_method("je ne sais pas encore") is None

    def test_empty_string_returns_none(self):
        assert _detect_payment_method("") is None

    def test_ambiguous_prefers_cb(self):
        # Si CB et liquide apparaissent dans la même phrase, CB est prioritaire
        # (l'ordre des conditions dans le code détermine cela)
        result = _detect_payment_method("cb ou liquide ?")
        assert result == "CB"


# ═══════════════════════════════════════════════════════════════════════════════
# _extract_phone : extraction de numéros de téléphone français
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractPhone:
    """Extraction regex de numéros de téléphone français depuis texte libre."""

    def test_standard_format(self):
        assert _extract_phone("06 12 34 56 78") == "0612345678"

    def test_dots_format(self):
        assert _extract_phone("06.12.34.56.78") == "0612345678"

    def test_dashes_format(self):
        assert _extract_phone("06-12-34-56-78") == "0612345678"

    def test_no_separator(self):
        assert _extract_phone("0612345678") == "0612345678"

    def test_international_format(self):
        assert _extract_phone("+33 6 12 34 56 78") == "+33612345678"

    def test_international_no_space(self):
        assert _extract_phone("+336 12 34 56 78") == "+33612345678"

    def test_in_sentence(self):
        # Le numéro est extrait même au milieu d'une phrase
        result = _extract_phone("mon numéro est 06 12 34 56 78 merci")
        assert result == "0612345678"

    def test_landline_number(self):
        assert _extract_phone("01 23 45 67 89") == "0123456789"

    def test_no_phone_returns_stripped_text(self):
        # Quand pas de numéro trouvé, retourne le texte nettoyé (fallback)
        assert _extract_phone("  pas de numéro  ") == "pas de numéro"

    def test_empty_string(self):
        assert _extract_phone("") == ""


# ═══════════════════════════════════════════════════════════════════════════════
# Settings : valeurs par défaut (sans fichier .env, sans Docker)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSettingsDefaults:
    """
    Vérifie que la configuration a des valeurs par défaut sensées.
    Ces tests ne lisent pas de fichier .env (os.environ est propre en CI).
    """

    def setup_method(self):
        # Instancier Settings sans lire de fichier .env existant
        self.settings = Settings(_env_file=None)

    def test_default_env_is_production(self):
        assert self.settings.app_env == "production"

    def test_default_quality_threshold(self):
        assert self.settings.rag_quality_threshold == 0.8

    def test_quality_threshold_is_float(self):
        assert isinstance(self.settings.rag_quality_threshold, float)

    def test_default_rag_top_k(self):
        assert self.settings.rag_top_k == 3

    def test_default_llm_model(self):
        assert self.settings.llm_model == "mistral"

    def test_default_llm_temperature(self):
        assert self.settings.llm_temperature == 0.1

    def test_temperature_is_low(self):
        # Température faible = réponses déterministes (important pour les tests de régression)
        assert self.settings.llm_temperature <= 0.2

    def test_order_complexity_threshold(self):
        assert self.settings.order_complexity_threshold == 6

    def test_chunk_size_reasonable(self):
        assert 100 <= self.settings.chunk_size <= 2000

    def test_env_override(self):
        # Vérifier que l'override via variable d'environnement fonctionne
        import os
        os.environ["APP_ENV"] = "staging"
        s = Settings(_env_file=None)
        assert s.app_env == "staging"
        del os.environ["APP_ENV"]

    def test_quality_threshold_env_override(self):
        import os
        os.environ["RAG_QUALITY_THRESHOLD"] = "0.6"
        s = Settings(_env_file=None)
        assert s.rag_quality_threshold == 0.6
        del os.environ["RAG_QUALITY_THRESHOLD"]
