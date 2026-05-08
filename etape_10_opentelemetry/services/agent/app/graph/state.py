"""
État du graphe LangGraph
────────────────────────
Un TypedDict représente l'état partagé entre tous les nœuds du graphe.
Chaque nœud reçoit l'état complet et retourne les champs qu'il modifie.
"""

from typing import Optional, List
from typing_extensions import TypedDict


class OrderItem(TypedDict):
    """Un article dans une commande."""
    produit: str
    quantite: int


class AgentState(TypedDict):
    """
    État global de la conversation – transmis à travers tous les nœuds.

    Flux typique :
      audio_bytes → [transcribe] → text_input
      text_input  → [classify]   → intent + order_items
      intent      → [route]      → search_rag | process_order | generate_response
                  → [generate]   → response_text
                  → [synthesize] → audio_response
    """

    # ── Entrée ─────────────────────────────────────────────────────────────────
    audio_bytes: Optional[bytes]   # Audio brut (None si entrée texte)
    text_input: str                # Texte transcrit ou directement fourni

    # ── Classification ─────────────────────────────────────────────────────────
    intent: str
    # Valeurs possibles :
    #   "info"              → question sur menus / horaires / congés
    #   "commande_simple"   → commande ≤ ORDER_COMPLEXITY_THRESHOLD unités
    #   "commande_complexe" → commande > ORDER_COMPLEXITY_THRESHOLD unités
    #   "autre"             → salutation, hors-sujet, incompréhensible

    order_items: List[OrderItem]   # Articles extraits (vide si intent != commande)
    query_topic: str               # "menu" | "horaires" | "conges" | "general"

    # ── RAG ────────────────────────────────────────────────────────────────────
    rag_context: str               # Contexte récupéré dans les fichiers de l'entreprise

    # ── Sortie ─────────────────────────────────────────────────────────────────
    response_text: str             # Réponse textuelle générée
    audio_response: Optional[bytes]  # Audio synthétisé (WAV)

    # ── Contrôle ───────────────────────────────────────────────────────────────
    skip_tts: bool                 # True = pas de synthèse vocale (mode texte)
    error: Optional[str]           # Message d'erreur éventuel
