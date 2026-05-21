"""
Catalogue des prix – Traiteur Dupont
─────────────────────────────────────
Source de vérité : data/catalog.json
  → généré automatiquement depuis menus.txt via LLM lors de chaque `make reload-docs`
  → fallback sur _DEFAULT_CATALOG si le fichier est absent

Lookup en deux passes :
  1. Substring (fast-path) : "bœuf bourguignon" ∈ "boeuf bourguignon" → ✗
     Non, mais "bœuf bourguignon" ∈ "je veux du bœuf bourguignon" → ✓
  2. Similarité cosinus sur embeddings paraphrase-multilingual-MiniLM-L12-v2
     (modèle déjà chargé pour le RAG – pas de surcoût mémoire)
     Gère : accents, ligatures (bœuf/boeuf), synonymes, fautes de frappe
"""

import json
import logging
from pathlib import Path

from ..config import settings

logger = logging.getLogger(__name__)

# ── Fallback codé en dur (si catalog.json absent au démarrage) ─────────────
_DEFAULT_CATALOG: dict[str, float] = {
    "plateau de charcuterie": 38.0,
    "terrine de campagne": 12.0,
    "quiche lorraine": 18.0,
    "quiche aux légumes": 16.0,
    "salade niçoise": 8.0,
    "velouté de légumes": 9.0,
    "bœuf bourguignon": 42.0,
    "poulet rôti": 22.0,
    "gratin dauphinois": 16.0,
    "ratatouille provençale": 14.0,
    "saumon en croûte": 48.0,
    "rougail saucisse": 13.0,
    "tarte aux pommes": 20.0,
    "tarte aux fraises": 24.0,
    "éclair au chocolat": 3.5,
    "macaron": 2.5,
    "mousse au chocolat": 15.0,
    "mille-feuille": 4.0,
    "formule cocktail": 12.0,
    "formule repas": 25.0,
    "formule buffet complet": 35.0,
}

# ── Singletons invalidés par reload_catalog() ─────────────────────────────
_catalog: dict[str, float] = {}
_catalog_embeddings: dict[str, list[float]] = {}
_embeddings_model = None


# ── Chargement ────────────────────────────────────────────────────────────

def _load_catalog() -> dict[str, float]:
    catalog_path = Path(settings.data_dir) / "catalog.json"
    if catalog_path.exists():
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            catalog = {k.lower().strip(): float(v) for k, v in data.items()}
            logger.info(f"catalog.json chargé ({len(catalog)} produits)")
            return catalog
        except Exception as exc:
            logger.warning(f"Erreur lecture catalog.json : {exc} — fallback sur catalogue par défaut")
    logger.info("catalog.json absent — utilisation du catalogue par défaut")
    return dict(_DEFAULT_CATALOG)


def _get_catalog() -> dict[str, float]:
    global _catalog
    if not _catalog:
        _catalog = _load_catalog()
    return _catalog


# ── Embeddings ────────────────────────────────────────────────────────────

def _get_embeddings_model():
    global _embeddings_model
    if _embeddings_model is None:
        from langchain_huggingface import HuggingFaceEmbeddings
        _embeddings_model = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        logger.info(f"Modèle embeddings catalogue chargé : {settings.embedding_model}")
    return _embeddings_model


def _get_catalog_embeddings() -> dict[str, list[float]]:
    global _catalog_embeddings
    if not _catalog_embeddings:
        catalog = _get_catalog()
        model = _get_embeddings_model()
        keys = list(catalog.keys())
        vectors = model.embed_documents(keys)
        _catalog_embeddings = dict(zip(keys, vectors))
        logger.info(f"Embeddings catalogue pré-calculés ({len(keys)} clés)")
    return _catalog_embeddings


def _dot(a: list[float], b: list[float]) -> float:
    """Produit scalaire = cosinus (vecteurs normalisés)."""
    return sum(x * y for x, y in zip(a, b))


# ── API publique ──────────────────────────────────────────────────────────

def reload_catalog() -> None:
    """Invalide le cache en mémoire. Appelé après make reload-docs."""
    global _catalog, _catalog_embeddings
    _catalog = {}
    _catalog_embeddings = {}
    logger.info("Cache catalogue invalidé — rechargement au prochain appel")


def get_unit_price(product_name: str, threshold: float = 0.72) -> float | None:
    """
    Retourne le prix unitaire d'un produit.

    Passe 1 — substring : rapide, couvre les cas exacts et partiels.
    Passe 2 — cosinus embeddings : gère accents, synonymes, fautes de frappe.
              Seuil 0.72 calibré pour éviter les faux positifs sur des noms proches.
    """
    normalized = product_name.lower().strip()
    catalog = _get_catalog()

    # Passe 1 — substring
    for key, price in catalog.items():
        if key in normalized or normalized in key:
            return price

    # Passe 2 — embeddings sémantiques
    try:
        embeddings = _get_catalog_embeddings()
        query_vec = _get_embeddings_model().embed_query(normalized)

        best_key, best_score = max(
            ((k, _dot(query_vec, v)) for k, v in embeddings.items()),
            key=lambda kv: kv[1],
        )

        if best_score >= threshold:
            logger.info(
                f"Prix par embedding : '{normalized}' → '{best_key}' "
                f"(cosinus={best_score:.2f}, {catalog[best_key]}€)"
            )
            return catalog[best_key]

        logger.warning(
            f"Prix introuvable pour '{product_name}' "
            f"(meilleur candidat='{best_key}', cosinus={best_score:.2f} < seuil={threshold})"
        )

    except Exception as exc:
        logger.error(f"Erreur embedding lookup prix : {exc}")

    return None


def compute_total(order_items: list[dict]) -> float:
    """Calcule le montant total d'une commande. Retourne 0.0 si prix inconnus."""
    total = 0.0
    for item in order_items:
        price = get_unit_price(item.get("produit", ""))
        if price is not None:
            total += price * item.get("quantite", 1)
    return round(total, 2)
