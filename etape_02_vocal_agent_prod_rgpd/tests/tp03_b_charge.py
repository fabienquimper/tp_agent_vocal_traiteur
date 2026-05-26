"""
tp03_b_charge.py — Test de charge simple cross-plateforme (WSL · Ubuntu · macOS · PowerShell)

Remplace la boucle bash :
  for i in $(seq 1 5); do
    curl -s -X POST http://localhost:8000/api/text \\
      -d '{"text": "...", "skip_tts": true}' &
  done
  wait

Prérequis : venv activé + dépendances installées (httpx est dans requirements.txt)

Usages :
  # 5 requêtes en parallèle (défaut)
  python tests/tp03_b_charge.py

  # 10 requêtes avec un message personnalisé
  python tests/tp03_b_charge.py --n 10 --message "Prix du saumon ?"

  # URL différente
  python tests/tp03_b_charge.py --n 3 --url http://mon-app.onrender.com
"""

import argparse
import asyncio
import time

import httpx


async def _une_requete(
    client: httpx.AsyncClient, url: str, message: str, idx: int
) -> tuple[int, float, str, str]:
    t0 = time.perf_counter()
    try:
        r = await client.post(
            url, json={"text": message, "skip_tts": True}, timeout=60
        )
        elapsed = time.perf_counter() - t0
        if r.status_code == 200:
            texte = r.json().get("response_text", "")[:100]
            return idx, elapsed, "OK", texte
        return idx, elapsed, f"HTTP {r.status_code}", r.text[:100]
    except httpx.ConnectError:
        return idx, time.perf_counter() - t0, "CONNEXION REFUSÉE", "docker compose up -d ?"
    except Exception as e:
        return idx, time.perf_counter() - t0, "ERREUR", str(e)


async def run(n: int, message: str, url_base: str) -> None:
    url = f"{url_base}/api/text"
    print(f"Envoi de {n} requêtes en parallèle vers {url}")
    print(f"Message : « {message} »\n")

    t_global = time.perf_counter()
    async with httpx.AsyncClient() as client:
        resultats = await asyncio.gather(
            *[_une_requete(client, url, message, i + 1) for i in range(n)]
        )
    total = time.perf_counter() - t_global

    for idx, elapsed, statut, texte in sorted(resultats):
        icone = "✓" if statut == "OK" else "✗"
        print(f"  {icone} #{idx} [{statut}] {elapsed:.2f}s — {texte}")

    ok = [r for r in resultats if r[2] == "OK"]
    erreurs = n - len(ok)
    if ok:
        temps = [r[1] for r in ok]
        print(
            f"\nRésumé : {len(ok)}/{n} OK"
            + (f" | {erreurs} erreur(s)" if erreurs else "")
            + f" | min {min(temps):.2f}s | moy {sum(temps)/len(temps):.2f}s"
            + f" | max {max(temps):.2f}s | total mur {total:.2f}s"
        )
    else:
        print(f"\nToutes les requêtes ont échoué. L'agent est-il démarré ?")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test de charge simple — envoie N requêtes en parallèle à l'agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--n", type=int, default=5, help="Nombre de requêtes (défaut: 5)")
    parser.add_argument(
        "--message", default="Prix du saumon ?", help="Message envoyé à chaque requête"
    )
    parser.add_argument("--url", default="http://localhost:8000", help="URL de base de l'agent")
    args = parser.parse_args()

    asyncio.run(run(args.n, args.message, args.url))


if __name__ == "__main__":
    main()
