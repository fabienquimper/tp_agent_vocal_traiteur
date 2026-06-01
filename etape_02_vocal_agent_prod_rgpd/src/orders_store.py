"""
Stockage JSON des commandes (en mémoire + fichier).
Séparé de app.py pour être testable unitairement.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

_ORDERS_DIR = os.getenv("ORDERS_DIR", "/app/orders")
_ORDERS_FILE = "orders.json"
_orders: list[dict] = []
_loaded = False


def _load_from_disk() -> None:
    global _orders, _loaded
    path = Path(_ORDERS_DIR) / _ORDERS_FILE
    if path.exists():
        try:
            _orders = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            _orders = []
    _loaded = True


def delete_by_phone(self, phone: str) -> int:
    """Supprime toutes les commandes correspondant au numéro de téléphone."""
    original_len = len(self._orders)
    self._orders = [o for o in self._orders if o.get("customer_phone") != phone]
    if len(self._orders) != original_len:
        self._persist()   # réécriture du JSON + rebuild Excel
    return original_len - len(self._orders)

def _save_to_disk() -> None:
    path = Path(_ORDERS_DIR) / _ORDERS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_orders, ensure_ascii=False, indent=2), encoding="utf-8")


def append_order(order: dict[str, Any]) -> str:
    global _orders
    if not _loaded:
        _load_from_disk()
    _orders.append(order)
    _save_to_disk()
    return order.get("id", "")


def get_all_orders() -> list[dict]:
    if not _loaded:
        _load_from_disk()
    return list(_orders)
