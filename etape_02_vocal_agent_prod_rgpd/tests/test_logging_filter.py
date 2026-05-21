"""Tests du filtre RGPD dans le module logging_config."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.logging_config import _scrub


class TestScrub:
    def test_scrubs_credit_card(self):
        text = "carte : 4242 4242 4242 4242 confirmée"
        result = _scrub(text)
        assert "4242 4242 4242 4242" not in result
        assert "[REDACTED]" in result

    def test_scrubs_credit_card_no_spaces(self):
        text = "paiement 4000000000000002 refusé"
        result = _scrub(text)
        assert "4000000000000002" not in result
        assert "[REDACTED]" in result

    def test_scrubs_french_phone(self):
        text = "téléphone : 06 12 34 56 78"
        result = _scrub(text)
        assert "06 12 34 56 78" not in result
        assert "[REDACTED]" in result

    def test_scrubs_phone_with_country_code(self):
        text = "contact +33 6 12 34 56 78 pour info"
        result = _scrub(text)
        assert "+33 6 12 34 56 78" not in result

    def test_scrubs_email(self):
        text = "client : jean.dupont@example.com"
        result = _scrub(text)
        assert "jean.dupont@example.com" not in result
        assert "[REDACTED]" in result

    def test_preserves_non_sensitive_text(self):
        text = "commande de 3 macarons et 2 tartes aux pommes"
        result = _scrub(text)
        assert result == text

    def test_scrubs_multiple_patterns(self):
        text = "Client 06.12.34.56.78 carte 4111111111111111 mail test@test.fr"
        result = _scrub(text)
        assert "06.12.34.56.78" not in result
        assert "4111111111111111" not in result
        assert "test@test.fr" not in result

    def test_preserves_order_reference(self):
        text = "commande n°A1B2C3D4 confirmée"
        result = _scrub(text)
        assert "A1B2C3D4" in result
