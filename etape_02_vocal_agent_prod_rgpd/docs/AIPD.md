# AIPD — Analyse d'Impact relative à la Protection des Données

**Traiteur Dupont — Agent Vocal IA (Étape 02)**  
Version 1.0 — Mai 2026  
Responsable du traitement : Traiteur Dupont (traitement fictif et local)

---

## 1. Description du traitement

| Champ | Valeur |
|-------|--------|
| Finalité | Prise de commandes vocales par un assistant IA |
| Base légale | Exécution d'un contrat (art. 6.1.b RGPD) |
| Responsable | Traiteur Dupont |
| Durée de conservation | Commandes : durée légale comptable (10 ans) ; transcriptions : non conservées (transit uniquement) |
| Pays de traitement | France / UE (mode local) ou USA (Groq) — voir flux |

> **Note** : ce traitement est fictif et local. Aucune vraie donnée personnelle n'est collectée.

---

## 2. Données traitées

| Catégorie | Nature | Durée | Localisation |
|-----------|--------|-------|--------------|
| Voix de l'utilisateur | Audio (transit uniquement) | < 5 secondes | RAM → Provider STT |
| Transcription | Texte (transit uniquement) | < 1 minute | RAM uniquement |
| Nom et prénom du client | Identité | Durée de la session + export Excel | Fichier local |
| Numéro de téléphone | Contact | Durée de la session + export Excel | Fichier local |
| Commande | Données de la transaction | 10 ans (comptabilité) | Fichier Excel local |
| **Numéro de carte bancaire** | **Données de paiement** | **Non stocké** | **Transit uniquement (simulation)** |

---

## 3. Flux de données

```
Microphone
    │
    ▼
STT Provider ────────► [Groq API / USA] (si STT_PROVIDER=groq)
    │                   ou [faster-whisper / local] (si STT_PROVIDER=local_ollama)
    │ transcription (texte)
    ▼
LLM Provider ────────► [Groq API / USA] (si LLM_PROVIDER=groq)
    │                   ou [Mistral API / EU] (si LLM_PROVIDER=mistral)
    │                   ou [Ollama / local] (si LLM_PROVIDER=local_ollama)
    │ réponse texte
    ▼
TTS (piper-tts) ──────► [local, 100 % hors-ligne]
    │
    ▼
Export Excel ─────────► /app/orders/ [volume Docker local]
```

**Mode 100 % local** : choisir `STT_PROVIDER=local_ollama` + `LLM_PROVIDER=local_ollama`.  
Dans ce mode, aucune donnée ne quitte la machine.

---

## 4. Risques identifiés

| N° | Risque | Probabilité | Impact | Niveau |
|----|--------|-------------|--------|--------|
| R1 | Fuite audio vers provider STT tiers (Groq) | Moyen | Élevé | **Élevé** |
| R2 | Fuite transcription/réponse vers provider LLM tiers (Groq, Mistral) | Moyen | Élevé | **Élevé** |
| R3 | Interception réseau (HTTP sans TLS) | Faible | Élevé | **Moyen** |
| R4 | Log accidentel de données personnelles | Faible | Moyen | **Moyen** |
| R5 | Hallucination de prix ou de produits | Moyen | Faible | **Moyen** |
| R6 | Biais de transcription selon accent ou langue | Moyen | Faible | **Moyen** |
| R7 | Jailbreak conduisant à des réponses inappropriées | Faible | Moyen | **Faible** |
| R8 | Conservation non conforme des données client (Excel) | Faible | Moyen | **Faible** |

---

## 5. Mesures de réduction des risques

| Risque | Mesure |
|--------|--------|
| R1, R2 | Mode 100 % local disponible (`local_ollama`) — recommandé en production |
| R1, R2 | Si cloud : Groq RGPD-compliant (DPA disponible), données EU pour Mistral |
| R3 | Toutes communications entre services via réseau Docker privé ou TLS |
| R4 | Filtre regex RGPD dans `logging_config.py` (numéros de carte, téléphone, email) |
| R4 | `DEBUG_LOCAL=false` par défaut — transcriptions non loggées en production |
| R5 | Menu injecté intégralement dans le prompt ; instruction explicite "ne jamais inventer" |
| R5 | Golden set de tests promptfoo incluant des cas hors-menu |
| R6 | Choix du modèle Whisper (large-v3 recommandé pour l'accent français) |
| R7 | Prompt système avec instructions de refus explicites |
| R8 | Politique de rétention documentée ; volume Docker non exposé |

---

## 6. Conformité AI Act

| Critère | Évaluation |
|---------|------------|
| Niveau de risque | **Risque limité** (système d'IA interagissant avec des humains) |
| Obligation principale | Transparence : l'agent doit s'identifier comme IA |
| Mise en œuvre | Phrase d'accueil versionnée dans `system_prompt.yaml` → `transparency_greeting` |
| Surveillance humaine | Commandes "complexes" marquées "À traiter manuellement" dans l'Excel |
| Exclusions | Pas de prise de décision automatisée à impact significatif |

---

## 7. Décision

**Traitement acceptable** sous réserve des mesures listées, notamment :

1. Activation du mode 100 % local en production réelle.
2. Filtre de logs activé et testé (voir `tests/test_logging_filter.py`).
3. Phrase de transparence IA présente à chaque session.
4. Politique de rétention et suppression des fichiers Excel appliquée.

---

*Document à réviser lors de tout changement de provider ou d'architecture.*
