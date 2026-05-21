"""Tests du filtre RGPD dans le module logging_config."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.logging_config import _scrub


class TestScrub:
    # ── Catégorie 1 : données d'identification ────────────────────────────────
    def test_scrubs_credit_card(self):
        text = "carte : 4242 4242 4242 4242 confirmée"
        result = _scrub(text)
        assert "4242 4242 4242 4242" not in result
        assert "[CC]" in result

    def test_scrubs_credit_card_no_spaces(self):
        text = "paiement 4000000000000002 refusé"
        result = _scrub(text)
        assert "4000000000000002" not in result
        assert "[CC]" in result

    def test_scrubs_french_phone(self):
        text = "téléphone : 06 12 34 56 78"
        result = _scrub(text)
        assert "06 12 34 56 78" not in result
        assert "[PHONE]" in result

    def test_scrubs_phone_with_country_code(self):
        text = "contact +33 6 12 34 56 78 pour info"
        result = _scrub(text)
        assert "+33 6 12 34 56 78" not in result

    def test_scrubs_email(self):
        text = "client : jean.dupont@example.com"
        result = _scrub(text)
        assert "jean.dupont@example.com" not in result
        assert "[EMAIL]" in result

    def test_scrubs_multiple_patterns(self):
        text = "Client 06.12.34.56.78 carte 4111111111111111 mail test@test.fr"
        result = _scrub(text)
        assert "06.12.34.56.78" not in result
        assert "4111111111111111" not in result
        assert "test@test.fr" not in result

    # ── Catégorie 2 : données sensibles RGPD art. 9 ──────────────────────────
    def test_scrubs_allergy(self):
        text = "le client a précisé être allergique aux noix"
        result = _scrub(text)
        assert "allergique" not in result
        assert "[HEALTH]" in result

    def test_scrubs_intolerance(self):
        text = "intolérance au lactose signalée"
        result = _scrub(text)
        assert "intolérance" not in result
        assert "[HEALTH]" in result

    def test_scrubs_halal(self):
        text = "le client souhaite des plats halal"
        result = _scrub(text)
        assert "halal" not in result
        assert "[HEALTH]" in result

    def test_scrubs_kosher(self):
        text = "régime casher uniquement"
        result = _scrub(text)
        assert "casher" not in result
        assert "[HEALTH]" in result

    def test_scrubs_diabetes(self):
        text = "attention diabétique, pas de sucre"
        result = _scrub(text)
        assert "diabétique" not in result
        assert "[HEALTH]" in result

    # ── Préservation des données non sensibles ────────────────────────────────
    def test_preserves_non_sensitive_text(self):
        text = "commande de 3 macarons et 2 tartes aux pommes"
        result = _scrub(text)
        assert result == text

    def test_preserves_order_reference(self):
        text = "commande n°A1B2C3D4 confirmée"
        result = _scrub(text)
        assert "A1B2C3D4" in result

    def test_preserves_allergenes_menu(self):
        # Le mot "allergènes" dans le contexte du menu (pas une donnée personnelle)
        # ne doit PAS être masqué — il désigne une information générale
        text = "liste des allergènes disponible sur demande"
        result = _scrub(text)
        # "allergènes" ne matche pas le pattern (qui cible "allergi*")
        assert "allergènes" in result
