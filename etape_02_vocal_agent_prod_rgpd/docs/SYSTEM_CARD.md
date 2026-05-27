# System Card — Agent Vocal Traiteur Dupont

> Conformité AI Act art. 13 — Transparence envers les utilisateurs et les déployeurs
> **Version :** 1.0.0 | **Mis à jour :** 2026-05-26 | **Propriétaire :** Traiteur Dupont

---

## 1. Identification du système

| Champ | Valeur |
|---|---|
| **Nom** | Agent Vocal Traiteur Dupont |
| **Version** | voir `/health` (`version` field) |
| **Type de système IA** | Agent conversationnel vocal (art. 50 AI Act : obligation de transparence) |
| **Fournisseur du modèle LLM** | Groq (Llama 3.1/3.3 — Meta AI) ou Mistral AI ou Ollama (local) |
| **Responsable du déploiement** | Traiteur Dupont |
| **Contact** | À définir par le déployeur |

---

## 2. Finalité et usage prévu

**Usage prévu :** Prise de commandes alimentaires par vocal ou texte pour le Traiteur Dupont. L'agent guide l'utilisateur à travers la sélection d'articles du menu, la collecte des informations de contact, et le paiement.

**Utilisateurs cibles :** Clients particuliers et professionnels du Traiteur Dupont.

**Usage non prévu :**
- Conseil médical ou nutritionnel (allergies, régimes thérapeutiques)
- Informations légales ou comptables
- Prise en charge d'urgences
- Toute interaction hors du domaine de la commande alimentaire

---

## 3. Capacités et limitations connues

### Ce que l'agent fait bien
- Reconnaître les articles du menu et calculer les totaux
- Gérer des commandes simples (<7 articles) et complexes
- Rediriger les questions hors-sujet poliment
- Masquer les données personnelles dans les logs (RGPD)
- Résister aux tentatives de détournement de prompt (jailbreak)

### Limitations connues

| Limitation | Impact | Contournement |
|---|---|---|
| Négation composée mal gérée ("je ne veux PAS de bœuf") | Peut commander l'article nié | Reformuler sans négation |
| Références pronominales ambiguës ("Donnez-m'en deux") | Hallucination du produit référencé | Préciser le nom du produit |
| Menu figé au démarrage | Ne reflète pas les modifications en cours de journée | Redémarrer l'agent (`docker compose restart agent`) |
| Session en mémoire uniquement | Redémarrage = perte des commandes en cours | Éviter les redémarrages pendant le service |
| TTS non disponible en cloud gratuit | Réponses textuelles uniquement sur Render Free | Utiliser une instance payante ou un provider TTS API |
| Multi-langue non supporté | Requêtes en anglais/espagnol classées "autre" | Interface en français uniquement |

### Score golden set (indicateur de qualité)
Le système doit maintenir un score ≥ 90 % sur le golden set de 25 cas (`tests/promptfoo.yaml`). Ce score est vérifié automatiquement à chaque release par le pipeline CI/CD.

---

## 4. Données personnelles traitées

Conformément au RGPD (art. 13 — information au moment de la collecte) :

| Donnée | Finalité | Base légale (art. 6) | Conservation |
|---|---|---|---|
| Prénom | Identification de la commande | Exécution du contrat (6.1.b) | Durée légale comptable (à définir) |
| Nom | Identification de la commande | Exécution du contrat (6.1.b) | Durée légale comptable |
| Téléphone | Contact pour confirmation | Exécution du contrat (6.1.b) | Durée légale comptable |
| Articles commandés | Traitement de la commande | Exécution du contrat (6.1.b) | Durée légale comptable |
| Montant total | Facturation | Exécution du contrat (6.1.b) | Durée légale comptable |
| Audio vocal (transcrit) | Transcription STT uniquement | Consentement implicite (usage du service) | **Non conservé** — transféré à Groq STT, résultat seul stocké |

**Données catégories spéciales (art. 9) :** allergies et régimes alimentaires mentionnés oralement **ne sont pas stockés** — masqués par le filtre `logging_config.py` avec le label `[HEALTH]`.

**Transferts internationaux :** Si `LLM_PROVIDER=groq` ou `STT_PROVIDER=groq`, les données (texte de la commande, audio) sont transférées vers les serveurs Groq (USA). Base légale : décision d'adéquation ou clauses contractuelles types. Pour éviter ce transfert : utiliser `LLM_PROVIDER=local_ollama`.

---

## 5. Transparence envers les utilisateurs (AI Act art. 50)

L'agent se présente comme une IA à chaque première interaction via le message `transparency_greeting` configuré dans `src/prompts/system_prompt.yaml`. Ce message mentionne :
1. Que l'utilisateur interagit avec un système IA (pas un humain)
2. La finalité du système (prise de commande)

Si un utilisateur demande explicitement "Es-tu un humain ?", l'agent répond qu'il est une IA (comportement testé dans le golden set).

---

## 6. Sécurité et robustesse

| Risque | Mesure en place |
|---|---|
| Prompt injection / jailbreak | Règle `anti_jailbreak` dans `classify`, `respond_other` refuse hors-sujet |
| Exfiltration de données via le chat | Le LLM n'a pas accès aux commandes passées (pas dans le contexte) |
| Accès non autorisé à `/api/orders` | ⚠️ **Non protégé par défaut** — ajouter authentification avant production (voir TP03 4.4) |
| Logs contenant des données personnelles | Filtre regex `_scrub()` dans `logging_config.py` |
| Clés API exposées | Stockées dans `.env` (non versionné), jamais dans le code |

---

## 7. Métriques de suivi qualité

Métriques Prometheus disponibles sur `/metrics` :

| Métrique | Signal de dégradation |
|---|---|
| `traiteur_intent_autre_total` | Augmentation → dérive des requêtes hors domaine |
| `traiteur_errors_total` | Augmentation → problème provider LLM/STT |
| `traiteur_feedback_total{rating="negative"}` | Augmentation → dégradation qualité perçue |
| `traiteur_llm_duration_seconds` p95 | Augmentation → dégradation latence |
| `traiteur_orders_total` | Diminution → problème de conversion |

Tableau de bord Grafana : `monitoring/grafana/dashboards/traiteur.json`

---

## 8. Procédure de signalement d'incident

En cas de comportement anormal de l'agent (réponses incorrectes, données exposées, comportement hors rôle) :

1. **Arrêter le service immédiatement** : `docker compose stop agent`
2. **Collecter les logs** : `docker compose logs agent > incident_$(date +%Y%m%d_%H%M).log`
3. **Identifier la cause** : vérifier `/api/status`, comparer le score promptfoo avec le dernier run CI
4. **Corriger et re-tester** : golden set ≥ 90 % avant tout redémarrage
5. **Notifier les utilisateurs** si des données personnelles ont pu être exposées (obligation RGPD art. 33/34)

---

## 9. Historique des versions

| Version système | Date | Changement principal |
|---|---|---|
| 1.0.0 | 2026-05-26 | Première System Card |

> Ce document doit être mis à jour à chaque changement significatif du comportement du système (nouveau modèle, modification des prompts, nouvelles données collectées).
