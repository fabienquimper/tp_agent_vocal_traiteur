#!/usr/bin/env python3
"""
Benchmark STT — Comparaison Whisper base vs small
══════════════════════════════════════════════════
Ce script mesure OBJECTIVEMENT la qualité et la vitesse de deux modèles Whisper.

Méthodologie :
  1. Pour chaque phrase de test (eval/phrases_test.json) :
     a. Génère de l'audio WAV via le service TTS (Piper)
     b. Transcrit cet audio avec STT-blue (Whisper base)
     c. Transcrit le même audio avec STT-green (Whisper small)
  2. Calcule le WER (Word Error Rate) pour chaque modèle
  3. Mesure les latences P50 et P95
  4. Affiche un tableau comparatif

WER (Word Error Rate) — la métrique standard de l'industrie STT :
  WER = (Substitutions + Insertions + Suppressions) / Nombre de mots de référence
  WER = 0% → transcription parfaite
  WER = 50% → 1 mot sur 2 est faux
  WER = 100% → aucun mot n'est correct

Pourquoi TTS → STT ?
  On n'a pas de corpus audio annoté. On utilise Piper pour générer de l'audio
  à partir de textes connus. C'est un test de bout-en-bout du pipeline vocal.
  Limitation : Piper prononce le texte "parfaitement" — en pratique, les vrais
  utilisateurs parlent avec des accents, hésitations, bruits de fond.
  → Les WER mesurés ici sont des WER "idéaux", meilleurs que la réalité.

Usage :
  # Installer les dépendances (une seule fois)
  pip install -r requirements-benchmark.txt

  # Démarrer les services
  make up && make init-ollama

  # Lancer le benchmark
  python scripts/benchmark_stt.py

  # Ou via le Makefile
  make benchmark-stt
"""

import json
import re
import statistics
import sys
import time
from pathlib import Path

# ── Vérification des dépendances ───────────────────────────────────────────────

try:
    import httpx
except ImportError:
    print("❌ httpx non installé. Exécutez : pip install -r requirements-benchmark.txt")
    sys.exit(1)

try:
    from jiwer import wer as compute_wer
except ImportError:
    print("❌ jiwer non installé. Exécutez : pip install -r requirements-benchmark.txt")
    sys.exit(1)

# ── Configuration ─────────────────────────────────────────────────────────────

TTS_URL       = "http://localhost:8002"
STT_BLUE_URL  = "http://localhost:8011"  # Whisper base  (port exposé côté hôte)
STT_GREEN_URL = "http://localhost:8012"  # Whisper small (port exposé côté hôte)

EVAL_FILE = Path(__file__).parent.parent / "eval" / "phrases_test.json"

TIMEOUT = 120  # secondes — les grands modèles sur CPU peuvent prendre du temps

# ── Couleurs terminal ──────────────────────────────────────────────────────────

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
CYAN   = "\033[96m"


# ── Helpers ────────────────────────────────────────────────────────────────────

def check_service(name: str, url: str) -> bool:
    """Vérifie qu'un service est accessible."""
    try:
        r = httpx.get(f"{url}/health", timeout=5)
        data = r.json()
        model = data.get("model", "inconnu")
        print(f"  {GREEN}✓{RESET} {name} ({url}) — modèle: {BOLD}{model}{RESET}")
        return True
    except Exception as exc:
        print(f"  {RED}✗{RESET} {name} ({url}) — {exc}")
        return False


def generate_audio(text: str) -> bytes:
    """Génère un fichier WAV depuis le service TTS Piper."""
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.post(f"{TTS_URL}/synthesize", json={"text": text})
        r.raise_for_status()
        return r.content


def transcribe(audio: bytes, stt_url: str) -> tuple[str, float]:
    """
    Transcrit un audio WAV via un service STT.
    Retourne (transcript, latence_en_secondes).
    """
    t0 = time.perf_counter()
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.post(
            f"{stt_url}/transcribe",
            files={"audio": ("audio.wav", audio, "audio/wav")},
            params={"language": "fr"},
        )
        r.raise_for_status()
    latency = time.perf_counter() - t0
    transcript = r.json().get("transcript", "").strip()
    return transcript, latency


def normalize(text: str) -> str:
    """
    Normalise le texte pour le calcul du WER :
    - Minuscules
    - Suppression de la ponctuation
    - Espaces multiples réduits
    Sans normalisation, "Bonjour !" ≠ "bonjour" → WER artificiel.
    """
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)   # ponctuation → espace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def wer_pct(reference: str, hypothesis: str) -> float:
    """Calcule le WER en % entre deux textes normalisés."""
    ref_norm = normalize(reference)
    hyp_norm = normalize(hypothesis)
    if not ref_norm:
        return 0.0
    return round(compute_wer(ref_norm, hyp_norm) * 100, 1)


def color_wer(w: float) -> str:
    """Colore le WER selon sa valeur."""
    if w <= 5:
        return f"{GREEN}{w:.1f}%{RESET}"
    elif w <= 15:
        return f"{YELLOW}{w:.1f}%{RESET}"
    else:
        return f"{RED}{w:.1f}%{RESET}"


def color_latency(lat: float) -> str:
    """Colore la latence selon sa valeur."""
    if lat <= 1.0:
        return f"{GREEN}{lat:.2f}s{RESET}"
    elif lat <= 3.0:
        return f"{YELLOW}{lat:.2f}s{RESET}"
    else:
        return f"{RED}{lat:.2f}s{RESET}"


# ── Benchmark principal ────────────────────────────────────────────────────────

def run_benchmark():
    print(f"\n{BOLD}{'═' * 68}{RESET}")
    print(f"{BOLD}  Benchmark STT — Whisper base vs small{RESET}")
    print(f"  Traiteur Dupont — Étape 03")
    print(f"{BOLD}{'═' * 68}{RESET}\n")

    # ── Vérification des services ──────────────────────────────────────────────
    print(f"{BOLD}Vérification des services :{RESET}")
    ok_tts   = check_service("TTS (Piper)",     TTS_URL)
    ok_blue  = check_service("STT-blue (base)", STT_BLUE_URL)
    ok_green = check_service("STT-green (small)", STT_GREEN_URL)

    if not (ok_tts and ok_blue and ok_green):
        print(f"\n{RED}Certains services sont inaccessibles.{RESET}")
        print("Vérifiez que les services sont démarrés : make up && make init-ollama")
        sys.exit(1)

    # ── Chargement du jeu d'évaluation ────────────────────────────────────────
    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        phrases = json.load(f)

    print(f"\n{BOLD}Jeu d'évaluation :{RESET} {len(phrases)} phrases ({EVAL_FILE.name})\n")

    # ── Boucle de benchmark ────────────────────────────────────────────────────
    results = []

    header = (
        f"{'#':>3}  {'Catégorie':<12}  {'Diff.':<9}  "
        f"{'WER base':>8}  {'Lat. base':>10}  "
        f"{'WER small':>9}  {'Lat. small':>11}"
    )
    print(f"{BOLD}{header}{RESET}")
    print("─" * 72)

    for i, phrase in enumerate(phrases, start=1):
        text      = phrase["text"]
        category  = phrase.get("category", "?")
        difficulty = phrase.get("difficulty", "?")

        print(f"\n  {CYAN}[{i:02d}/{len(phrases)}]{RESET} {text[:60]}{'…' if len(text) > 60 else ''}")

        # Génération audio
        try:
            audio = generate_audio(text)
        except Exception as exc:
            print(f"  {RED}TTS erreur : {exc}{RESET}")
            continue

        # Transcription blue (base)
        try:
            hyp_blue, lat_blue = transcribe(audio, STT_BLUE_URL)
        except Exception as exc:
            print(f"  {RED}STT-blue erreur : {exc}{RESET}")
            hyp_blue, lat_blue = "", 999.0

        # Transcription green (small)
        try:
            hyp_green, lat_green = transcribe(audio, STT_GREEN_URL)
        except Exception as exc:
            print(f"  {RED}STT-green erreur : {exc}{RESET}")
            hyp_green, lat_green = "", 999.0

        # Calcul WER
        wer_blue  = wer_pct(text, hyp_blue)
        wer_green = wer_pct(text, hyp_green)

        results.append({
            "id": phrase["id"],
            "category": category,
            "difficulty": difficulty,
            "reference": text,
            "hyp_blue": hyp_blue,
            "hyp_green": hyp_green,
            "wer_blue": wer_blue,
            "wer_green": wer_green,
            "lat_blue": lat_blue,
            "lat_green": lat_green,
        })

        row = (
            f"  {i:>2}.  {category:<12}  {difficulty:<9}  "
            f"{color_wer(wer_blue):>8}  {color_latency(lat_blue):>10}  "
            f"{color_wer(wer_green):>9}  {color_latency(lat_green):>11}"
        )
        print(row)

        # Afficher si small améliore le base
        if wer_green < wer_blue:
            improvement = wer_blue - wer_green
            print(f"           {GREEN}↑ small réduit le WER de {improvement:.1f}pp{RESET}")
        elif wer_green > wer_blue:
            print(f"           {YELLOW}↓ small ne fait pas mieux ici{RESET}")

    # ── Résultats agrégés ──────────────────────────────────────────────────────
    if not results:
        print(f"\n{RED}Aucun résultat collecté.{RESET}")
        return

    wers_blue  = [r["wer_blue"] for r in results]
    wers_green = [r["wer_green"] for r in results]
    lats_blue  = [r["lat_blue"] for r in results]
    lats_green = [r["lat_green"] for r in results]

    avg_wer_blue  = statistics.mean(wers_blue)
    avg_wer_green = statistics.mean(wers_green)
    p50_blue      = statistics.median(lats_blue)
    p95_blue      = sorted(lats_blue)[int(0.95 * len(lats_blue)) - 1]
    p50_green     = statistics.median(lats_green)
    p95_green     = sorted(lats_green)[int(0.95 * len(lats_green)) - 1]

    # WER par difficulté
    diff_labels = sorted({r["difficulty"] for r in results})
    diff_wers: dict[str, dict[str, list]] = {
        d: {"blue": [], "green": []} for d in diff_labels
    }
    for r in results:
        diff_wers[r["difficulty"]]["blue"].append(r["wer_blue"])
        diff_wers[r["difficulty"]]["green"].append(r["wer_green"])

    print(f"\n\n{BOLD}{'═' * 68}{RESET}")
    print(f"{BOLD}  Résultats agrégés{RESET}")
    print(f"{BOLD}{'═' * 68}{RESET}\n")

    print(f"  {'Métrique':<30}  {'Whisper base':>14}  {'Whisper small':>14}")
    print(f"  {'─' * 60}")
    print(f"  {'WER moyen (%)':<30}  {color_wer(avg_wer_blue):>14}  {color_wer(avg_wer_green):>14}")
    print(f"  {'Latence P50 (s)':<30}  {color_latency(p50_blue):>14}  {color_latency(p50_green):>14}")
    print(f"  {'Latence P95 (s)':<30}  {color_latency(p95_blue):>14}  {color_latency(p95_green):>14}")

    print(f"\n  {BOLD}WER par difficulté :{RESET}")
    for diff in diff_labels:
        w_blue  = statistics.mean(diff_wers[diff]["blue"])  if diff_wers[diff]["blue"]  else 0
        w_green = statistics.mean(diff_wers[diff]["green"]) if diff_wers[diff]["green"] else 0
        print(
            f"    {diff:<9} → base: {color_wer(w_blue)}  "
            f"small: {color_wer(w_green)}"
        )

    # ── Recommandation automatique ────────────────────────────────────────────
    print(f"\n{BOLD}{'═' * 68}{RESET}")
    print(f"{BOLD}  Recommandation{RESET}")
    print(f"{BOLD}{'═' * 68}{RESET}\n")

    wer_gain    = avg_wer_blue - avg_wer_green
    latency_cost = p50_green - p50_blue

    if wer_gain > 5 and latency_cost < 2.0:
        verdict = f"{GREEN}RECOMMANDÉ{RESET}"
        reason  = (
            f"Le modèle small réduit le WER de {wer_gain:.1f}pp pour seulement "
            f"+{latency_cost:.2f}s de latence P50. Excellent rapport qualité/vitesse."
        )
        action = "make stt-switch-green"
    elif wer_gain > 2:
        verdict = f"{YELLOW}À ÉVALUER{RESET}"
        reason  = (
            f"small améliore le WER de {wer_gain:.1f}pp mais coûte "
            f"+{latency_cost:.2f}s de latence P50. Acceptable si la précision est prioritaire."
        )
        action = "make stt-switch-green  # si la qualité prime sur la vitesse"
    else:
        verdict = f"{RED}NON RECOMMANDÉ{RESET}"
        reason  = (
            f"Le gain de WER ({wer_gain:.1f}pp) ne justifie pas "
            f"le surcoût de +{latency_cost:.2f}s de latence. Gardez Whisper base."
        )
        action = "# rester sur make stt-switch-blue (déjà actif)"

    print(f"  Verdict : {verdict}")
    print(f"  Raison  : {reason}")
    print(f"\n  Action recommandée :")
    print(f"    {CYAN}{action}{RESET}")

    print(f"\n  {BOLD}Pour effectuer le switch (zéro downtime) :{RESET}")
    print(f"    make stt-switch-green   # base → small")
    print(f"    make stt-switch-blue    # small → base (rollback)")
    print(f"    make stt-status         # vérifier l'actif")
    print(f"\n  {BOLD}Pour vérifier l'impact en production :{RESET}")
    print(f"    Ouvrez Grafana → http://localhost:3001")
    print(f"    Panel 'STT — Latence Whisper P50/P95'")
    print(f"    Le changement de pente est visible immédiatement après le switch.\n")

    # ── Sauvegarde des résultats ───────────────────────────────────────────────
    output_file = Path(__file__).parent.parent / "eval" / "benchmark_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "summary": {
                "n_phrases": len(results),
                "blue": {
                    "model": "whisper-base",
                    "avg_wer_pct": round(avg_wer_blue, 2),
                    "p50_latency_s": round(p50_blue, 3),
                    "p95_latency_s": round(p95_blue, 3),
                },
                "green": {
                    "model": "whisper-small",
                    "avg_wer_pct": round(avg_wer_green, 2),
                    "p50_latency_s": round(p50_green, 3),
                    "p95_latency_s": round(p95_green, 3),
                },
            },
            "details": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"  Résultats sauvegardés → {output_file}\n")


if __name__ == "__main__":
    run_benchmark()
