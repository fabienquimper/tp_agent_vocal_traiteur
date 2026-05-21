"""
Logique panier — fonctions pures, sans état global.
Le panier est un dict[str, int] : {nom_produit_normalisé: quantité}.
"""

from __future__ import annotations


def _normalize(name: str) -> str:
    return name.lower().strip()


def add_item(basket: dict[str, int], product: str, qty: int) -> dict[str, int]:
    """Ajoute ou cumule un article dans le panier."""
    key = _normalize(product)
    return {**basket, key: basket.get(key, 0) + qty}


def remove_item(basket: dict[str, int], product: str) -> dict[str, int]:
    """Supprime un article du panier (ignoré s'il n'y est pas)."""
    key = _normalize(product)
    return {k: v for k, v in basket.items() if k != key}


def set_item(basket: dict[str, int], product: str, qty: int) -> dict[str, int]:
    """Fixe une quantité absolue (remplace l'existant)."""
    key = _normalize(product)
    if qty <= 0:
        return remove_item(basket, product)
    return {**basket, key: qty}


def compute_total(basket: dict[str, int], catalog: dict[str, float]) -> float:
    """Calcule le montant total. Produits inconnus comptent 0 €."""
    total = 0.0
    for product, qty in basket.items():
        price = _lookup_price(product, catalog)
        if price is not None:
            total += price * qty
    return round(total, 2)


def _lookup_price(product: str, catalog: dict[str, float]) -> float | None:
    """Recherche le prix par substring (passage 1) puis fuzzy (passage 2)."""
    product_norm = _normalize(product)
    # Passe 1 : substring exact
    for key, price in catalog.items():
        if key in product_norm or product_norm in key:
            return price
    return None


def from_order_items(order_items: list[dict]) -> dict[str, int]:
    """Convertit la liste LLM [{produit, quantite}] en panier interne."""
    basket: dict[str, int] = {}
    for item in order_items:
        name = item.get("produit", "")
        qty = int(item.get("quantite", 1))
        if name and qty > 0:
            basket = add_item(basket, name, qty)
    return basket


def to_order_items(basket: dict[str, int]) -> list[dict]:
    """Convertit le panier interne en liste d'items pour l'export."""
    return [{"produit": k, "quantite": v} for k, v in basket.items() if v > 0]


def total_units(basket: dict[str, int]) -> int:
    return sum(basket.values())


def format_basket(basket: dict[str, int]) -> str:
    if not basket:
        return "panier vide"
    return ", ".join(f"{qty}× {name}" for name, qty in basket.items())
