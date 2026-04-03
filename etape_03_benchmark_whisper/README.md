# Étape 03 — Benchmark Whisper + Blue/Green Deployment

> **Prérequis :** avoir complété l'étape 02 (observabilité opérationnelle).
>
> **Concepts clés :**
> - *"Mesurer avant d'optimiser"* — les métriques de l'étape 02 montrent où passe le temps.
> - *"Déployer sans interrompre"* — le Blue/Green permet de tester en production sans downtime.

---

## Problème posé

L'étape 02 a révélé que le STT (Whisper base) peut être un goulot d'étranglement.
Whisper `small` promet une meilleure précision — mais est-ce vraiment le cas sur
le vocabulaire du traiteur ? Et combien ça coûte en latence ?

**On ne change pas de modèle en production sans données objectives.**

---

## Ce qu'on ajoute dans cette étape

| Étape 02 | Étape 03 (nouveau) |
|---|---|
| 1 service STT (`stt`) | 2 services STT + 1 router nginx |
| Pas de comparaison de modèles | Benchmark WER + latence sur 20 phrases |
| Redémarrage pour changer de modèle | Switch instantané < 100ms (nginx reload) |
| Configuration statique | `WHISPER_MODEL_BLUE` + `WHISPER_MODEL_GREEN` |

### Architecture Blue/Green

```
Avant (étape 02) :
  agent → stt:8001 (Whisper base)
               ↑ changer de modèle = redémarrer = downtime

Après (étape 03) :
  agent → stt-router:8001 (nginx) ─── stt-blue:8001  (Whisper base)  [actif]
                                   └── stt-green:8001 (Whisper small) [standby]

  make stt-switch-green → nginx reload → < 100ms → stt-green devient actif
```

### Nouveaux fichiers

```
etape_03_benchmark_whisper/
├── services/stt-router/
│   ├── Dockerfile              ← nginx:alpine avec les 2 configs upstream
│   ├── nginx.conf              ← config principale (inclut upstream.conf)
│   ├── upstream.blue.conf      ← upstream stt-blue:8001
│   └── upstream.green.conf     ← upstream stt-green:8001
├── eval/
│   └── phrases_test.json       ← 20 phrases françaises de test (facile→difficile)
├── scripts/
│   └── benchmark_stt.py        ← benchmark WER + latence P50/P95
└── requirements-benchmark.txt  ← httpx + jiwer (sur hôte, pas dans Docker)
```

---

## Démarrage

```bash
# Première fois (construit stt-blue, stt-green, stt-router)
make init-all

# Vérifier que tout est UP
make test-health
```

**Services accessibles :**

| Service | URL | Rôle |
|---|---|---|
| Interface | http://localhost:3000 | Agent vocal |
| STT Router | http://localhost:8001 | Point d'entrée (blue par défaut) |
| STT Blue | http://localhost:8011 | Whisper base (accès direct benchmark) |
| STT Green | http://localhost:8012 | Whisper small (accès direct benchmark) |
| Prometheus | http://localhost:9090 | Métriques |
| Grafana | http://localhost:3001 | Dashboard |

---

## Workflow pédagogique

### Étape A — Établir la baseline (Blue actif)

```bash
# Vérifier que Blue est actif
make stt-status
# → Router → {"status": "ok", "model": "base"}

# Générer du trafic pour avoir une baseline Grafana
make traffic
# → Observez la latence STT P95 dans Grafana → notez la valeur
```

### Étape B — Lancer le benchmark

```bash
# Installer les dépendances du benchmark (une seule fois)
make benchmark-install

# Lancer le benchmark complet (20 phrases, ~5-10 min)
make benchmark-stt
```

**Exemple de sortie :**

```
════════════════════════════════════════════════════════════════════════
  Benchmark STT — Whisper base vs small
  Traiteur Dupont — Étape 03
════════════════════════════════════════════════════════════════════════

Vérification des services :
  ✓ TTS (Piper)      — modèle: fr_FR-siwis-medium
  ✓ STT-blue (base)  — modèle: base
  ✓ STT-green (small)— modèle: small

Jeu d'évaluation : 20 phrases (phrases_test.json)

 #  Catégorie     Diff.      WER base  Lat. base  WER small  Lat. small
─────────────────────────────────────────────────────────────────────────
  1.  horaires      facile      2.1%       0.82s       0.0%       1.51s
       ↑ small réduit le WER de 2.1pp
  2.  commande      facile      5.3%       1.12s       0.0%       2.04s
  ...

════════════════════════════════════════════════════════════════════════
  Résultats agrégés
════════════════════════════════════════════════════════════════════════

  Métrique                         Whisper base    Whisper small
  ────────────────────────────────────────────────────────────────────
  WER moyen (%)                           11.2%            4.8%
  Latence P50 (s)                         0.91s            1.74s
  Latence P95 (s)                         1.98s            3.21s

  WER par difficulté :
    facile    → base: 4.1%   small: 0.8%
    moyen     → base: 9.7%   small: 3.2%
    difficile → base: 19.4%  small: 10.1%

════════════════════════════════════════════════════════════════════════
  Recommandation
════════════════════════════════════════════════════════════════════════

  Verdict : RECOMMANDÉ
  Raison  : Le modèle small réduit le WER de 6.4pp pour seulement +0.83s
            de latence P50. Excellent rapport qualité/vitesse.

  Action recommandée :
    make stt-switch-green
```

### Étape C — Déploiement Blue/Green (zéro downtime)

```bash
# Pendant que l'agent traite des requêtes (laissez make traffic tourner
# dans un autre terminal), effectuez le switch :
make stt-switch-green

# Sortie :
# === Blue → Green (Whisper base → small) ===
# Étape 1/3 : Vérification de stt-green...
# ✓ stt-green est healthy
# Étape 2/3 : Mise à jour de la config nginx...
# Étape 3/3 : Rechargement nginx (graceful — aucune requête perdue)...
# ✓ Switch effectué !
#   Actif maintenant : {"status": "ok", "model": "small"}
```

**Ouvrez Grafana** → panel "STT — Latence Whisper P50/P95"
→ Vous verrez la latence augmenter légèrement mais la qualité de transcription s'améliore.

### Étape D — Rollback (si la qualité n'est pas au rendez-vous)

```bash
make stt-switch-blue
# Switch instantané, les nouvelles requêtes retournent sur Whisper base
```

---

## Concepts clés

### Word Error Rate (WER)

La métrique standard de l'industrie pour évaluer la qualité STT :

```
WER = (Substitutions + Insertions + Suppressions) / Nb mots de référence

Exemples :
  Référence  : "deux quiches lorraines"
  Hypothèse  : "deux kiches lorraines"
  → 1 substitution / 3 mots = WER = 33%

  Hypothèse  : "deux quiches lorraines et"
  → 1 insertion / 3 mots = WER = 33%
```

**Valeurs typiques pour le français conversationnel :**

| Modèle | WER français | Vitesse CPU |
|---|---|---|
| tiny | ~25% | Très rapide |
| base | ~12% | Rapide |
| small | ~6% | Modéré |
| medium | ~4% | Lent |
| large-v3 | ~2% | Très lent |

### Pourquoi TTS → STT pour le benchmark ?

On n'a pas de corpus audio annoté en français pour le traiteur.
On utilise Piper TTS pour générer de l'audio depuis des textes connus.
Le WER mesuré est **optimiste** (Piper prononce parfaitement, sans accent ni bruit).
En production réelle, le WER sera plus élevé (~2× à 3×).
→ Les WER de ce benchmark servent surtout à **comparer** les modèles entre eux,
  pas à estimer la performance absolue.

### Pourquoi nginx pour le Blue/Green ?

```
Avant nginx -s reload :
  Connexion 1 (en cours)  → stt-blue ─── se termine proprement
  Connexion 2 (nouvelle)  → stt-blue  ←── attend le reload

Après nginx -s reload (<100ms) :
  Connexion 1 (toujours en cours) → stt-blue  ─── se termine
  Connexion 3 (nouvelle)          → stt-green ←── nouveau upstream
```

`nginx -s reload` est **non-bloquant** : nginx fork un nouveau worker process
avec la nouvelle configuration, attend que les workers anciens terminent
leurs connexions ouvertes, puis les supprime.

C'est exactement le mécanisme utilisé par Argo Rollouts, Flagger, et
HAProxy en production pour les déploiements Blue/Green et Canary.

### Différence Blue/Green vs Canary vs Rolling

```
Blue/Green :
  100% Blue → [switch instantané] → 100% Green
  Avantage : rollback immédiat
  Inconvénient : 2× les ressources pendant la transition

Canary (étape suivante possible) :
  100% Blue → 10% Green + 90% Blue → 50%/50% → 100% Green
  Avantage : détecte les régressions progressivement
  Inconvénient : plus complexe (besoin de traffic splitting)

Rolling Update (Kubernetes par défaut) :
  Remplace les pods un par un
  Avantage : économique (pas de doublement des ressources)
  Inconvénient : pendant la transition, les 2 versions coexistent
```

---

## Commandes utiles

```bash
make up                   # Démarre tous les services
make test-health          # Vérifie que tout répond

# Benchmark
make benchmark-install    # Installe httpx + jiwer
make benchmark-stt        # Benchmark complet (20 phrases, ~5-10 min)

# Blue/Green
make stt-status           # Quel modèle est actif ?
make stt-switch-green     # Déploie Whisper small (< 100ms, zéro downtime)
make stt-switch-blue      # Rollback vers Whisper base (< 100ms)

# Vérification
make traffic              # Génère du trafic pour Grafana
make metrics              # Métriques STT brutes
make grafana              # Ouvre Grafana
```

---

## Ce que prépare cette étape

Maintenant qu'on sait benchmarker un composant et le déployer sans downtime,
les prochaines briques logiques sont :

```
Étape 04 → Hot RAG reload (zéro downtime)
  Problème : réindexer ChromaDB prend du temps et bloque les requêtes RAG.
  Solution : indexer dans une collection "staging" (shadow index),
             puis basculer atomiquement le pointeur (comme Blue/Green mais pour les données).
  Concepts : atomic pointer swap, shadow indexing, eventual consistency.

Étape 05 → Tests automatisés + CI simulé
  Problème : comment garantir que le switch ne casse rien ?
  Solution : pytest sur l'API + score WER minimum comme gate de déploiement.
  Concepts : tests d'intégration, quality gates, pipeline CI.
```
