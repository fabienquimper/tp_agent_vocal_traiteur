"""
Stockage JSON des commandes confirmées
───────────────────────────────────────
Alimente le tableau de bord traiteur (GET /api/orders).
Les commandes sont persistées dans /app/orders/orders.json,
monté sur le volume Docker ./orders.
"""

import json
import os
import uuid
from datetime import datetime
from typing import Any

ORDERS_FILE = "/app/orders/orders.json"


def _load() -> list[dict[str, Any]]:
    if not os.path.exists(ORDERS_FILE):
        return []
    try:
        with open(ORDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save(orders: list[dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(ORDERS_FILE), exist_ok=True)
    with open(ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2, default=str)


def append_order(order: dict[str, Any]) -> str:
    """
    Sauvegarde une commande dans le fichier JSON.
    Injecte un ID unique et la date de création.
    Retourne l'ID généré.
    """
    orders = _load()
    order_id = str(uuid.uuid4())[:8].upper()
    order["id"] = order_id
    order["created_at"] = datetime.now().isoformat()
    orders.append(order)
    _save(orders)
    return order_id


def get_all_orders() -> list[dict[str, Any]]:
    """Retourne toutes les commandes enregistrées (ordre chronologique inverse)."""
    return list(reversed(_load()))
