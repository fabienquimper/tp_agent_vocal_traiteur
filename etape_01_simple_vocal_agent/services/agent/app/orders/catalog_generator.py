"""
Génération automatique de catalog.json depuis menus.txt
────────────────────────────────────────────────────────
Appelé par initialize_vectorstore(force_reload=True) pour maintenir
une source de vérité unique : menus.txt → catalog.json.

Le LLM extrait les produits et prix en JSON structuré.
Le résultat est utilisé par orders/catalog.py pour les lookups de prix.
"""

import json
import logging
from pathlib import Path

from ..config import settings

logger = logging.getLogger(__name__)

_META_PROMPT = """Tu es un extracteur de données structurées pour un logiciel de commande.
Voici la carte d'un traiteur. Extrais tous les produits et services qui ont un prix explicite.

Règles strictes :
- Clé   : nom court normalisé en minuscules, sans parenthèses ni précisions de quantité
          Exemples : "bœuf bourguignon", "quiche lorraine", "formule cocktail"
- Valeur : prix en euros, nombre décimal (ex: 13.0, 3.5, 12.0)
- Pour les formules "par personne", indique le prix à la personne
- N'inclus que les produits ayant un prix explicite
- Retourne UNIQUEMENT le JSON valide, sans texte avant ni après, sans balises markdown

Format attendu :
{{"bœuf bourguignon": 42.0, "poulet rôti": 22.0, "macaron": 2.5}}

Carte du traiteur :
{menu_content}"""


def generate_catalog_from_menu() -> bool:
    """
    Lit menus.txt, demande au LLM d'en extraire les prix, sauvegarde dans catalog.json.

    Utilise un import différé de `llm` depuis graph.nodes pour éviter les imports
    circulaires (nodes → retriever → catalog_generator → nodes serait circulaire
    à l'import, mais pas à l'appel car tous les modules sont déjà chargés).

    Retourne True si succès, False sinon.
    """
    menu_path = Path(settings.data_dir) / "menus.txt"
    if not menu_path.exists():
        logger.warning("menus.txt introuvable — catalog.json non régénéré")
        return False

    menu_content = menu_path.read_text(encoding="utf-8")

    try:
        # Import différé : tous les modules sont déjà chargés au moment de l'appel
        from ..graph.nodes import llm
        from langchain.schema import HumanMessage

        prompt = _META_PROMPT.format(menu_content=menu_content)
        response = llm.invoke([HumanMessage(content=prompt)])

        raw = response.content.strip()
        # Nettoyage des balises markdown si le LLM en ajoute
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        catalog: dict = json.loads(raw)
        if not isinstance(catalog, dict) or not catalog:
            raise ValueError(f"Réponse JSON vide ou invalide : {raw[:200]}")

        catalog = {k.lower().strip(): float(v) for k, v in catalog.items()}

        catalog_path = Path(settings.data_dir) / "catalog.json"
        with open(catalog_path, "w", encoding="utf-8") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)

        logger.info(
            f"catalog.json régénéré depuis menus.txt : {len(catalog)} produits extraits"
        )
        return True

    except json.JSONDecodeError as exc:
        logger.error(f"Le LLM n'a pas retourné un JSON valide : {exc}")
    except Exception as exc:
        logger.error(f"Erreur génération catalog.json : {exc}")

    return False
