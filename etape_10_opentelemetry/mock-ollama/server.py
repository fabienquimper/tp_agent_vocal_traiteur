"""
mock-ollama — Serveur HTTP minimaliste qui simule l'API Ollama
─────────────────────────────────────────────────────────────
Pourquoi un mock ?
  Les runners GitHub Actions ont ~7 GB RAM.
  Ollama + Mistral 7B = ~4.5 GB (téléchargement + chargement en mémoire).
  Sur un runner partagé, c'est trop lent et trop proche de la limite.

Ce mock répond à l'API Ollama REST de façon statique :
  POST /api/generate  → réponse JSON fixe (utilisée par LangChain ChatOllama)
  POST /api/chat      → réponse JSON fixe (format OpenAI-compatible)
  GET  /api/tags      → liste les modèles disponibles
  GET  /              → health check

Les tests smoke et RAG quality gate ne font PAS d'appels LLM
(ils testent /health, /metrics, /api/rag/search, /api/rag/status).
Le mock est utilisé uniquement pour que l'agent démarre sans erreur
(le LangGraph workflow a besoin qu'Ollama réponde à /api/tags au startup).

Usage :
  python server.py
  # → écoute sur 0.0.0.0:11434
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 11434
MODEL = "mistral"

# Réponses statiques simulant Mistral
_CHAT_RESPONSE = {
    "role": "assistant",
    "content": (
        "Bonjour ! Je suis l'assistant du Traiteur Dupont. "
        "Nos horaires sont du lundi au vendredi de 9h à 18h. "
        "Comment puis-je vous aider ?"
    ),
}

_CLASSIFY_RESPONSE = {
    "role": "assistant",
    "content": json.dumps({
        "intent": "information",
        "confidence": 0.9,
        "entities": {},
    }),
}


class MockOllamaHandler(BaseHTTPRequestHandler):
    """Gestionnaire HTTP minimaliste pour simuler l'API Ollama."""

    def log_message(self, fmt, *args):
        # Log sur stderr pour ne pas polluer stdout
        print(f"[mock-ollama] {fmt % args}", file=sys.stderr)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path == "/health":
            self._send_json({"status": "ok", "mock": True})

        elif self.path == "/api/tags":
            # Liste des modèles disponibles — l'agent vérifie que mistral est présent
            self._send_json({
                "models": [
                    {
                        "name": MODEL,
                        "model": MODEL,
                        "size": 4109868032,
                        "digest": "mock-digest-abc123",
                        "details": {
                            "format": "gguf",
                            "family": "llama",
                            "parameter_size": "7B",
                            "quantization_level": "Q4_0",
                        },
                    }
                ]
            })

        elif self.path.startswith("/api/show"):
            self._send_json({"model": MODEL, "mock": True})

        else:
            self._send_json({"error": f"unknown path: {self.path}"}, status=404)

    def do_POST(self):
        body = self._read_body()
        prompt = body.get("prompt", body.get("messages", [{}])[-1].get("content", ""))
        stream = body.get("stream", False)

        if self.path == "/api/generate":
            # LangChain OllamaLLM utilise /api/generate
            response_text = self._choose_response(prompt)
            if stream:
                # Ollama streame en NDJSON — on envoie un seul chunk + done
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                chunk = json.dumps({"response": response_text, "done": False}) + "\n"
                done = json.dumps({"response": "", "done": True}) + "\n"
                self.wfile.write(chunk.encode())
                self.wfile.write(done.encode())
            else:
                self._send_json({
                    "model": MODEL,
                    "response": response_text,
                    "done": True,
                })

        elif self.path == "/api/chat":
            # LangChain ChatOllama utilise /api/chat
            response_text = self._choose_response(prompt)
            if stream:
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                chunk = json.dumps({
                    "message": {"role": "assistant", "content": response_text},
                    "done": False,
                }) + "\n"
                done = json.dumps({
                    "message": {"role": "assistant", "content": ""},
                    "done": True,
                }) + "\n"
                self.wfile.write(chunk.encode())
                self.wfile.write(done.encode())
            else:
                self._send_json({
                    "model": MODEL,
                    "message": {"role": "assistant", "content": response_text},
                    "done": True,
                })

        elif self.path == "/api/pull":
            # Simule le téléchargement d'un modèle
            self._send_json({"status": "success", "mock": True})

        else:
            self._send_json({"error": f"unknown path: {self.path}"}, status=404)

    def _choose_response(self, prompt: str) -> str:
        """Retourne une réponse statique cohérente selon le contenu du prompt."""
        p = prompt.lower() if isinstance(prompt, str) else ""

        # Si le prompt ressemble à une classification → retourner du JSON
        if "json" in p or "intent" in p or "classif" in p:
            return json.dumps({
                "intent": "information",
                "confidence": 0.9,
                "entities": {},
            })

        # Réponse générique de l'assistant
        return (
            "Bonjour ! Je suis l'assistant du Traiteur Dupont. "
            "Nos horaires sont du lundi au vendredi de 9h à 18h, "
            "et le samedi de 9h à 12h. Comment puis-je vous aider ?"
        )


def main():
    server = HTTPServer(("0.0.0.0", PORT), MockOllamaHandler)
    print(f"[mock-ollama] Démarrage sur le port {PORT}", file=sys.stderr)
    print(f"[mock-ollama] Modèle simulé : {MODEL}", file=sys.stderr)
    print("[mock-ollama] Endpoints disponibles : GET /api/tags, POST /api/chat, POST /api/generate", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[mock-ollama] Arrêt", file=sys.stderr)


if __name__ == "__main__":
    main()
