# Décisions architecturales — ADR-style

## ADR-01 : Pas de RAG pour le menu

**Date** : Mai 2026  
**Statut** : Accepté

**Contexte** : Le RAG (Retrieval-Augmented Generation) est la tendance dominante pour injecter des données métier dans un LLM. Faut-il l'utiliser pour le menu ?

**Décision** : Non. Le menu fait ~2 KB, soit ~500 tokens. On injecte le menu intégral dans le system prompt à chaque requête.

**Raisons** :
- À ce volume, un vector store (ChromaDB) ajoute de la latence, des dépendances lourdes et un risque de retrieval imparfait.
- Le modèle voit *moins* que tout le menu avec le RAG (il ne récupère que les chunks les plus proches).
- Le menu entier tient largement dans la fenêtre de contexte des modèles modernes (128k tokens).
- Simplicité opérationnelle : pas de ChromaDB à gérer, pas de réindexation.

**Conséquences** : Si le menu dépasse ~50 KB (très improbable pour un traiteur), réévaluer.

**Référence** : voir `src/menu/menu.yaml`, `src/prompts/system_prompt.yaml`

---

## ADR-02 : Ollama sur l'hôte, pas dans Docker

**Date** : Mai 2026  
**Statut** : Accepté

**Contexte** : Doit-on inclure Ollama dans le docker-compose.yml ?

**Décision** : Non. Ollama tourne sur l'hôte.

**Raisons** :
- Ollama dans Docker nécessite de passer les GPU (--gpus all), de gérer les volumes pour les modèles (~4-40 GB), et alourdit le docker compose.
- La plupart des développeurs ont déjà Ollama installé localement.
- L'hôte peut utiliser le GPU natif sans configuration Docker complexe.
- L'agent accède à Ollama via `host.docker.internal:11434` (Mac/Windows) ou `extra_hosts` (Linux).

**Conséquences** : `setup_ollama_local.sh` doit être exécuté avant le premier démarrage en mode local.

---

## ADR-03 : Provider pattern avec factory centralisée

**Date** : Mai 2026  
**Statut** : Accepté

**Contexte** : Etape 01 avait des `if provider == "groq"` dispersés dans nodes.py.

**Décision** : Interface abstraite `STTProvider`/`LLMProvider` + implémentations dans `providers/` + instanciation unique dans `factory.py`.

**Raisons** :
- Zéro if-else sur le provider dans la logique métier.
- Ajouter un nouveau provider = créer un fichier dans `providers/` + une ligne dans `factory.py`.
- Testable : on peut mocker le provider sans toucher au reste.
- Lisible : le comportement d'un provider est entièrement dans son fichier.

---

## ADR-04 : Prompts dans des fichiers YAML versionnés

**Date** : Mai 2026  
**Statut** : Accepté

**Contexte** : Les prompts étaient codés en dur dans nodes.py (strings Python).

**Décision** : Tous les prompts dans `src/prompts/system_prompt.yaml`, chargés au démarrage.

**Raisons** :
- Un tag Git capture exactement le comportement de l'agent (code + prompt + config + menu).
- Modifier un prompt ne nécessite pas de recompiler l'image Docker (avec un volume monté).
- Lisibilité : le YAML est plus lisible qu'une f-string Python multiligne.
- Tracing : `git blame` sur un prompt montre qui a changé quoi et pourquoi.

---

## ADR-05 : Suppression de LangChain et LangGraph

**Date** : Mai 2026  
**Statut** : Accepté

**Contexte** : Etape 01 utilisait LangChain + LangGraph pour l'orchestration.

**Décision** : Orchestration directe en Python async. Appels LLM via SDK des providers.

**Raisons** :
- LangChain/LangGraph ajoutent ~200 MB de dépendances et une couche d'abstraction qui masque ce qui se passe réellement.
- Pour notre cas d'usage (classify → respond), un graph n'apporte pas de valeur : la logique est linéaire.
- Plus facile à tester et à débugger (les appels LLM sont explicites).
- Moins de surface d'attaque (moins de dépendances = moins de CVE potentielles).

---

## ADR-06 : STT intégré dans le conteneur agent (pas de service séparé)

**Date** : Mai 2026  
**Statut** : Accepté

**Contexte** : Etape 01 avait un service `stt` séparé.

**Décision** : Le STT (faster-whisper) tourne dans le même conteneur que l'agent, ou via l'API Groq.

**Raisons** :
- Un service STT séparé ajoute une latence réseau inter-conteneurs.
- Pour le mode cloud (Groq), l'appel se fait directement depuis l'agent.
- Pour le mode local, `faster-whisper` s'importe comme une lib Python standard.
- Réduction à 2 services (agent + tts) = docker-compose plus simple.

**Conséquences** : L'image Docker est légèrement plus grande (faster-whisper ~200 MB). Acceptable.

---

## ADR-07 : Logging structuré avec filtre RGPD

**Date** : Mai 2026  
**Statut** : Accepté

**Contexte** : Les logs de l'étape 01 pouvaient contenir des transcriptions et des informations client.

**Décision** : `structlog` avec filtre regex pour scrubber les patterns sensibles (carte bancaire, téléphone, email). Transcriptions loggées uniquement si `DEBUG_LOCAL=true`.

**Raisons** :
- Conformité RGPD par défaut.
- `DEBUG_LOCAL=false` en production = zéro donnée personnelle dans les logs.
- Filtre appliqué aussi sur le logging stdlib (pour les libs tierces).
- `structlog` produit du JSON structuré, compatible avec les agrégateurs de logs.
