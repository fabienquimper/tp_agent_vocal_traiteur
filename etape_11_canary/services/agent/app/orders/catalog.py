"""
Catalogue des prix – Traiteur Dupont
─────────────────────────────────────
Utilisé pour calculer le montant total d'une commande.
Les prix correspondent aux tarifs définis dans data/menus.txt.
"""

# Mapping produit (clé normalisée) → prix unitaire en €
_CATALOG: dict[str, float] = {
    "plateau de charcuterie maison": 38.00,
    "quiche lorraine": 22.00,
    "salade composée traiteur": 18.00,
    "velouté de légumes du marché": 12.00,
    "terrine de campagne": 15.00,
    "feuilletés apéritifs": 24.00,
    "bœuf bourguignon": 48.00,
    "poulet rôti aux herbes": 42.00,
    "gratin dauphinois": 28.00,
    "saumon en croûte": 52.00,
    "tajine d'agneau": 45.00,
    "tarte aux pommes": 18.00,
    "tarte au citron meringuée": 22.00,
    "mousse au chocolat": 24.00,
    "éclairs": 20.00,
    "macarons": 28.00,
    "crème brûlée": 22.00,
    "formule buffet froid": 18.00,
    "formule cocktail apéritif": 12.00,
    "formule repas complet": 35.00,
}

# Mots-clés secondaires pour la correspondance partielle
_KEYWORDS: dict[str, float] = {
    "charcuterie": 38.00,
    "quiche": 22.00,
    "salade": 18.00,
    "velouté": 12.00,
    "terrine": 15.00,
    "feuilleté": 24.00,
    "bourguignon": 48.00,
    "poulet": 42.00,
    "gratin": 28.00,
    "saumon": 52.00,
    "tajine": 45.00,
    "citron meringuée": 22.00,
    "mousse au chocolat": 24.00,
    "éclair": 20.00,
    "macaron": 28.00,
    "crème brûlée": 22.00,
    "buffet froid": 18.00,
    "cocktail apéritif": 12.00,
    "repas complet": 35.00,
    # Correspondances génériques (produits hors catalogue ou variantes)
    "tarte": 20.00,    # Valeur indicative – à confirmer
    "cake": 20.00,
    "gâteau": 20.00,
    "dessert": 20.00,
    "plat": 42.00,
    "entrée": 22.00,
}


def get_unit_price(product_name: str) -> float | None:
    """Retourne le prix unitaire d'un produit par correspondance (exacte puis partielle)."""
    normalized = product_name.lower()
    for key, price in _CATALOG.items():
        if key in normalized or normalized in key:
            return price
    for kw, price in _KEYWORDS.items():
        if kw in normalized:
            return price
    return None


def compute_total(order_items: list[dict]) -> float:
    """Calcule le montant total d'une commande. Retourne 0.0 si les prix sont inconnus."""
    total = 0.0
    for item in order_items:
        price = get_unit_price(item.get("produit", ""))
        if price is not None:
            total += price * item.get("quantite", 1)
    return round(total, 2)
