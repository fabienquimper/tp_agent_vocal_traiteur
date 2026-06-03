"""Tests unitaires du module basket — fonctions pures, pas de réseau."""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.basket import (
    add_item, remove_item, set_item, compute_total,
    from_order_items, to_order_items, total_units, format_basket,
)

CATALOG = {
    "plateau de charcuterie": 38.0,
    "bœuf bourguignon": 42.0,
    "tarte aux pommes": 20.0,
    "macaron": 2.5,
    "formule buffet complet": 35.0,
}


class TestAddItem:
    def test_add_new_item(self):
        basket = add_item({}, "plateau de charcuterie", 2)
        assert basket["plateau de charcuterie"] == 2

    def test_add_existing_item_cumulates(self):
        basket = add_item({"macaron": 3}, "macaron", 5)
        assert basket["macaron"] == 8

    def test_add_normalizes_case(self):
        basket = add_item({}, "MACARON", 1)
        assert "macaron" in basket

    def test_add_does_not_mutate_original(self):
        original = {"macaron": 2}
        _ = add_item(original, "macaron", 1)
        assert original["macaron"] == 2


class TestRemoveItem:
    def test_remove_existing(self):
        basket = remove_item({"macaron": 3, "bœuf bourguignon": 1}, "macaron")
        assert "macaron" not in basket
        assert "bœuf bourguignon" in basket

    def test_remove_nonexistent_is_noop(self):
        basket = remove_item({"macaron": 3}, "tarte aux pommes")
        assert basket == {"macaron": 3}

    def test_remove_partial_name_matches_longer_key(self):
        # LLM peut retourner "quiche lorraine" alors que le panier a "quiche lorraine (8 parts)"
        basket = remove_item({"quiche lorraine (8 parts)": 2, "macaron": 5}, "quiche lorraine")
        assert not any("quiche" in k for k in basket)
        assert basket.get("macaron") == 6

    def test_remove_does_not_mutate_original(self):
        original = {"macaron": 3, "bœuf bourguignon": 1}
        _ = remove_item(original, "macaron")
        assert "macaron" in original


class TestSetItem:
    def test_set_replaces_qty(self):
        basket = set_item({"macaron": 5}, "macaron", 2)
        assert basket["macaron"] == 2

    def test_set_zero_removes(self):
        basket = set_item({"macaron": 5}, "macaron", 0)
        assert "macaron" not in basket


class TestComputeTotal:
    def test_single_item(self):
        basket = {"tarte aux pommes": 2}
        assert compute_total(basket, CATALOG) == 40.0

    def test_multiple_items(self):
        basket = {"macaron": 4, "tarte aux pommes": 1}
        assert compute_total(basket, CATALOG) == pytest.approx(30.0)

    def test_unknown_item_counts_zero(self):
        basket = {"pizza": 3, "macaron": 2}
        assert compute_total(basket, CATALOG) == pytest.approx(5.0)

    def test_empty_basket(self):
        assert compute_total({}, CATALOG) == 0.0

    def test_substring_match(self):
        # "boeuf bourguignon" should match "bœuf bourguignon" via substring
        basket = {"bœuf bourguignon": 1}
        assert compute_total(basket, CATALOG) == 42.0


class TestFromOrderItems:
    def test_converts_list_to_dict(self):
        items = [
            {"produit": "Macaron", "quantite": 3},
            {"produit": "Tarte aux pommes", "quantite": 1},
        ]
        basket = from_order_items(items)
        assert basket["macaron"] == 3
        assert basket["tarte aux pommes"] == 1

    def test_merges_duplicates(self):
        items = [
            {"produit": "macaron", "quantite": 2},
            {"produit": "macaron", "quantite": 3},
        ]
        basket = from_order_items(items)
        assert basket["macaron"] == 5

    def test_skips_zero_qty(self):
        items = [{"produit": "macaron", "quantite": 0}]
        basket = from_order_items(items)
        assert "macaron" not in basket


class TestTotalUnits:
    def test_sum_all_quantities(self):
        assert total_units({"macaron": 3, "bœuf bourguignon": 2}) == 5

    def test_empty_basket(self):
        assert total_units({}) == 0


class TestFormatBasket:
    def test_formats_items(self):
        text = format_basket({"macaron": 2, "tarte aux pommes": 1})
        assert "2× macaron" in text
        assert "1× tarte aux pommes" in text

    def test_empty_basket(self):
        assert format_basket({}) == "panier vide"
