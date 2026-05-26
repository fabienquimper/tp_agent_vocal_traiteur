"""
tp03_c_compare.py — Compare deux fichiers de résultats promptfoo (.json)

Permet de détecter les régressions et améliorations entre deux runs du golden set :
- Changement de modèle (ex : 8B → 70B)
- Changement de prompt (ex : v1.6.0 → v1.7.0)
- Déploiement local vs production

Usages :
  # Comparer deux modèles sur le même prompt
  python tests/tp03_c_compare.py \\
      tests/results/results-v1.6.0-8b.json \\
      tests/results/results-v1.6.0-70b.json

  # Détecter les régressions après une mise à jour du prompt
  python tests/tp03_c_compare.py \\
      tests/results/results-v1.6.0-8b.json \\
      tests/results/results-v1.7.0-8b.json

Codes de sortie :
  0 — aucune régression
  1 — au moins une régression détectée (utilisable en CI)
"""

import argparse
import json
import sys


def load_results(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("results", {}).get("results", [])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare deux runs promptfoo — détecte régressions et améliorations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("avant", help="Fichier JSON baseline (ex: results-v1.6.0-8b.json)")
    parser.add_argument("apres", help="Fichier JSON comparé (ex: results-v1.6.0-70b.json)")
    args = parser.parse_args()

    avant = load_results(args.avant)
    apres = load_results(args.apres)

    if len(avant) != len(apres):
        print(f"Attention : {len(avant)} tests dans '{args.avant}' vs {len(apres)} dans '{args.apres}'")

    n = min(len(avant), len(apres))
    regressions: list[str] = []
    ameliorations: list[str] = []

    for i in range(n):
        a, b = avant[i], apres[i]
        desc = str(a.get("vars", {}).get("message", f"test {i + 1}"))[:70]
        a_ok = bool(a.get("success", False))
        b_ok = bool(b.get("success", False))

        if a_ok and not b_ok:
            regressions.append(f"  ✗ [{i + 1:02d}] {desc}")
        elif not a_ok and b_ok:
            ameliorations.append(f"  ✓ [{i + 1:02d}] {desc}")

    avant_score = sum(1 for r in avant if r.get("success"))
    apres_score = sum(1 for r in apres if r.get("success"))
    delta = apres_score - avant_score

    print(f"\nBaseline ({args.avant}) : {avant_score}/{len(avant)} ({avant_score / len(avant):.0%})")
    print(f"Comparé  ({args.apres}) : {apres_score}/{len(apres)} ({apres_score / len(apres):.0%})")
    print(f"Delta    : {delta:+d} tests\n")

    if ameliorations:
        print("── Améliorations ──────────────────────────────────────────")
        for line in ameliorations:
            print(line)
        print()

    if regressions:
        print("── Régressions ────────────────────────────────────────────")
        for line in regressions:
            print(line)
        print()
        print(f"ATTENTION : {len(regressions)} régression(s) détectée(s).")
        sys.exit(1)
    else:
        print("Aucune régression détectée.")


if __name__ == "__main__":
    main()
