"""
tp03_a_appel_agent.py — Appel cross-plateforme à l'agent (WSL · Ubuntu · macOS · PowerShell)

Remplace :
  curl -s -X POST http://localhost:8000/api/text \\
    -H "Content-Type: application/json" \\
    -d '{"text": "...", "skip_tts": true}' | python3 -m json.tool

Prérequis : venv activé + dépendances installées (httpx est dans requirements.txt)

Usages :
  # Appel simple
  python tests/tp03_a_appel_agent.py "Prix du saumon ?"

  # Mesurer la latence (comme 'time curl ...')
  python tests/tp03_a_appel_agent.py "Bonjour" --timing

  # Consulter un endpoint GET (/api/orders, /health, /api/status, /metrics)
  python tests/tp03_a_appel_agent.py --get /api/orders
  python tests/tp03_a_appel_agent.py --get /metrics --filtre traiteur

  # URL différente (prod ou autre port)
  python tests/tp03_a_appel_agent.py "Bonjour" --url http://localhost:8080
"""

import argparse
import json
import sys
import time

import httpx


def appel_agent(message: str, url_base: str, timing: bool) -> None:
    url = f"{url_base}/api/text"
    payload = {"text": message, "skip_tts": True}
    t0 = time.perf_counter()
    try:
        r = httpx.post(url, json=payload, timeout=30)
        elapsed = time.perf_counter() - t0
    except httpx.ConnectError:
        print(f"[ERREUR] Impossible de joindre {url}")
        print("         Vérifiez que l'agent est démarré : docker compose up -d")
        sys.exit(1)

    if timing:
        print(f"Temps : {elapsed:.3f}s")

    if r.status_code == 200:
        data = r.json()
        print(data.get("response_text", json.dumps(data, ensure_ascii=False, indent=2)))
    else:
        print(f"[HTTP {r.status_code}] {r.text}")


def appel_get(chemin: str, url_base: str, filtre: str | None) -> None:
    url = f"{url_base}{chemin}"
    try:
        r = httpx.get(url, timeout=10)
    except httpx.ConnectError:
        print(f"[ERREUR] Impossible de joindre {url}")
        print("         Vérifiez que l'agent est démarré : docker compose up -d")
        sys.exit(1)

    if r.status_code != 200:
        print(f"[HTTP {r.status_code}] {r.text}")
        return

    content_type = r.headers.get("content-type", "")
    if "json" in content_type:
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))
    else:
        lignes = r.text.splitlines()
        if filtre:
            lignes = [l for l in lignes if filtre.lower() in l.lower()]
        print("\n".join(lignes))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Appel à l'agent Traiteur Dupont — fonctionne sur toutes les plateformes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("message", nargs="?", help="Message à envoyer à l'agent (mode POST)")
    parser.add_argument("--get", metavar="CHEMIN", help="Endpoint GET à consulter (ex: /api/orders)")
    parser.add_argument("--filtre", metavar="MOT", help="Filtrer les lignes de la réponse texte (ex: traiteur)")
    parser.add_argument("--timing", action="store_true", help="Afficher le temps de réponse")
    parser.add_argument("--url", default="http://localhost:8000", help="URL de base de l'agent")
    args = parser.parse_args()

    if args.get:
        appel_get(args.get, args.url, args.filtre)
    elif args.message:
        appel_agent(args.message, args.url, args.timing)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
