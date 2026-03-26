"""
Graphe LangGraph – Orchestration de l'agent
─────────────────────────────────────────────
Flux visuel :
                     ┌──────────────┐
                     │  transcribe  │  (si audio_bytes)
                     └──────┬───────┘
                            │
                     ┌──────▼───────┐
                     │   classify   │
                     └──────┬───────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
       ┌──────▼──────┐           ┌────────▼────────┐
       │  search_rag │           │ generate_response│  ← commandes + autre
       └──────┬──────┘           └────────┬────────┘
              └─────────────┬─────────────┘
                            │
                   ┌────────▼────────┐
                   │   synthesize    │
                   └────────┬────────┘
                            │
                          [END]

Note : les commandes ne passent plus par un nœud "process_order".
L'écriture Excel/JSON est déclenchée par main.py en fin de session
de collecte des informations client.
"""

from langgraph.graph import StateGraph, START, END

from .state import AgentState
from .nodes import (
    transcribe_audio,
    classify_request,
    search_rag,
    generate_response,
    synthesize_speech,
    route_after_classify,
)

# ── Singleton du graphe compilé ───────────────────────────────────────────────
_compiled_graph = None


def build_graph():
    """Construit et compile le graphe LangGraph."""
    graph = StateGraph(AgentState)

    graph.add_node("transcribe", transcribe_audio)
    graph.add_node("classify", classify_request)
    graph.add_node("search_rag", search_rag)
    graph.add_node("generate_response", generate_response)
    graph.add_node("synthesize", synthesize_speech)

    graph.add_edge(START, "transcribe")
    graph.add_edge("transcribe", "classify")

    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        {
            "search_rag": "search_rag",
            "generate_response": "generate_response",
        },
    )

    graph.add_edge("search_rag", "generate_response")
    graph.add_edge("generate_response", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()


def get_graph():
    """Retourne le graphe compilé (singleton)."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph
