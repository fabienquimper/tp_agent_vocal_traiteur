# TP 07 — Diagnostic, Interface Vocale et Décisions d'Architecture (3h30)

**Durée estimée :** 3h30
**Prérequis :** TP 01 à TP 06 · agent démarré (`docker compose up`)

> **Version TP :** 1.0.0 — synchronisé avec `system_prompt.yaml v1.6.0`, `ui/app.js` (session stable, MediaRecorder, paiement CB), `docs/DECISIONS.md` (7 ADRs)
> **Mis à jour :** 2026-05-26

---

> **Cas réel — Cloudflare (2020) :** Un bug dans un déploiement d'eBPF a causé une cascade de pannes affectant 10 % du trafic Internet mondial. Les ingénieurs ont mis 27 minutes à identifier la cause racine parce que les logs d'erreurs étaient eux-mêmes impactés par la panne. Leçon : savoir lire les logs et diagnostiquer une panne en production n'est pas un "nice to have" — c'est une compétence critique que 90 % des développeurs n'ont jamais pratiquée dans un environnement guidé.

---

## Partie 1 — Diagnostiquer une panne (1h30)

> Les pannes ne se décrivent pas toujours avec des messages d'erreur clairs. Le diagnostic est un processus méthodique : observer le symptôme, consulter le premier point d'entrée fiable (`/api/status`), lire les logs, isoler le composant fautif.

### 1.1 Cinq scénarios de panne à diagnostiquer

Pour chaque scénario, vous disposez d'un symptôme observable. Votre travail : décrire la démarche de diagnostic complète, identifier la cause racine probable, et proposer le correctif.

---

**Scénario A — L'agent répond "difficulté technique" à toutes les requêtes**

L'agent démarre sans erreur visible (`docker compose up` retourne "Application startup complete"), mais chaque message envoyé déclenche la réponse "Je rencontre une difficulté technique, veuillez réessayer."

**Démarche suggérée :**
1. Consulter `/api/status` dans le navigateur ou avec `python tests/tp03_a_appel_agent.py --get /api/status`
2. Lire les 50 dernières lignes de logs : `docker compose logs agent | tail -50`
3. Chercher les lignes avec `"level": "error"` ou `"authentication"` dans les logs

**Questions :**
1. Quel champ de `/api/status` permet d'identifier en premier le composant défaillant ?
2. Quel message d'erreur exact apparaît dans les logs quand la clé Groq est invalide ou absente ?
3. Proposez le correctif (quelle variable d'environnement, dans quel fichier).
4. Si la clé est présente dans `.env` mais que l'agent dit quand même "difficulté technique", quelle autre cause faut-il envisager ?

---

**Scénario B — `pytest tests/ -m "not slow"` retourne 47 tests au lieu de 51**

Vous avez cloné le dépôt sur une nouvelle machine. Les tests s'exécutent sans erreur apparente, mais le total est de 47 au lieu des 51 attendus.

**Démarche suggérée :**
1. Lister tous les tests collectés : `pytest --collect-only 2>&1 | head -80`
2. Comparer avec la liste attendue : `pytest --collect-only 2>&1 | grep "test session starts" -A 200`
3. Chercher des erreurs de collecte dans la sortie de `pytest --collect-only`

**Questions :**
1. Comment `pytest --collect-only` permet-il de distinguer "test non collecté" de "test échoué" ?
2. Un fichier `tests/conversations/conv_0X.json` malformé (JSON invalide) peut-il empêcher la collecte d'un module Python entier ? Pourquoi ?
3. Comment vérifiez-vous rapidement qu'un fichier JSON est valide ?
4. Quel est le message d'erreur typique de pytest quand il échoue à importer un module de test ?

---

**Scénario C — Le golden set promptfoo retourne 0/25**

Vous lancez `npx promptfoo@latest eval --config tests/promptfoo.yaml --no-cache` et obtenez 0 succès sur 25 tests. Tous les tests échouent avec "connection refused" ou "unexpected response".

**Démarche suggérée :**
1. Vérifier que l'agent est bien démarré : `docker compose ps`
2. Tester manuellement un appel : `python tests/tp03_a_appel_agent.py "Bonjour"`
3. Inspecter `tests/promptfoo.yaml` : vérifier l'URL cible et le corps des requêtes
4. Tester avec `skip_tts: true` explicitement dans le body

**Questions :**
1. Pourquoi le champ `skip_tts: true` dans le body de la requête est-il important pour promptfoo ?
2. Quelle URL doit pointer `tests/promptfoo.yaml` pour appeler l'agent en local ?
3. Comment `tp03_a_appel_agent.py` peut-il servir de "témoin" pour valider que l'agent répond avant de lancer promptfoo ?
4. Si l'agent répond à `tp03_a_appel_agent.py` mais que promptfoo retourne 0/25, quelle différence dans le format de requête faut-il inspecter ?

---

**Scénario D — Les métriques Grafana ne se mettent plus à jour (courbes plates)**

Le dashboard Grafana affiche des données historiques mais toutes les courbes sont plates depuis 20 minutes. Aucune alerte n'a été déclenchée.

**Démarche suggérée :**
1. Vérifier les targets Prometheus : `http://localhost:9090/targets`
2. Lire les logs Prometheus : `docker compose logs prometheus | tail -30`
3. Vérifier que le service agent est bien up : `docker compose ps`
4. Tester directement `/metrics` : `python tests/tp03_a_appel_agent.py --get /metrics --filtre traiteur`

**Questions :**
1. Quelle est la différence entre "Prometheus ne scrape plus" et "l'agent n'expose plus `/metrics`" ? Comment distinguer les deux cas depuis l'interface Prometheus ?
2. Si l'agent a redémarré sur un port différent du port configuré dans `prometheus.yml`, comment corriger sans redémarrer toute la stack ?
3. Pourquoi Grafana peut-il afficher des données historiques même quand Prometheus ne reçoit plus rien ?
4. Quel délai maximum faut-il attendre après le redémarrage de l'agent avant que les métriques reprennent (en lien avec l'intervalle de scrape configuré) ?

---

**Scénario E — La commande vocale fonctionne en local mais échoue en production (Render)**

L'agent est déployé sur Render. En local, `/api/voice` fonctionne. En production, la transcription STT fonctionne mais la synthèse vocale (TTS) échoue — l'agent retourne une réponse texte mais pas d'audio.

**Démarche suggérée :**
1. Consulter `/api/status` en production (URL Render + `/api/status`)
2. Vérifier les variables d'environnement dans le dashboard Render
3. Lire les logs Render (onglet "Logs" du service)
4. Comparer les variables `TTS_SERVICE_URL` en local et en production

**Questions :**
1. Pourquoi `TTS_SERVICE_URL=http://tts:8002` (valeur valide en local avec Docker Compose) ne fonctionne-t-il pas en production sur Render ?
2. Quelle variable d'environnement faut-il modifier, et quelle valeur faut-il lui donner pour que la production fonctionne sans service TTS séparé ?
3. Comment `/api/status` permet-il de diagnostiquer ce problème sans accès aux logs ?
4. Quelle est la différence architecturale entre Docker Compose (réseau interne) et un déploiement cloud comme Render qui explique cette incompatibilité ?

---

### 1.2 Lire les logs structurés

L'agent utilise `structlog` qui produit des logs JSON. Contrairement aux logs texte classiques, chaque ligne est un objet JSON parseable.

Lancez quelques requêtes, puis filtrez les logs :

```bash
docker compose logs agent 2>&1 | python -c "
import sys, json
for line in sys.stdin:
    try:
        d = json.loads(line)
        if d.get('level') in ('error', 'warning'):
            print(d)
    except: pass
"
```

Pour voir tous les événements LLM :
```bash
docker compose logs agent 2>&1 | python -c "
import sys, json
for line in sys.stdin:
    try:
        d = json.loads(line)
        if 'llm' in str(d.get('event', '')).lower():
            print(json.dumps(d, indent=2, ensure_ascii=False))
    except: pass
" | head -60
```

**Questions :**
1. Quelle est la différence de sévérité entre les niveaux `DEBUG`, `INFO`, `WARNING` et `ERROR` ? Donnez un exemple de chaque niveau dans le contexte de cet agent.
2. Pourquoi les logs contiennent-ils un champ `session_id` mais pas le texte brut de la transcription (`DEBUG_LOCAL=false`) ?
3. Comment corréleriez-vous un incident signalé par un client ("ma commande de 14h35 n'a pas été enregistrée") avec les logs, sachant que vous ne connaissez que l'heure approximative ?
4. En quoi les logs JSON structurés sont-ils supérieurs aux logs texte classiques pour une exploitation en production (hint : Elasticsearch, Grafana Loki) ?

---

### 1.3 Utiliser `/api/status` pour le diagnostic

L'endpoint `/api/status` retourne l'état de chaque provider (LLM, STT, TTS, Ollama si configuré). C'est le premier réflexe en cas de panne.

**Exercice :**

1. Arrêtez le service TTS : `docker compose stop tts`
2. Consultez `/api/status` : `python tests/tp03_a_appel_agent.py --get /api/status`
3. Notez la réponse exacte du champ TTS
4. Redémarrez : `docker compose start tts`

**Questions :**
1. Quel champ de `/api/status` indique que le service TTS est down ? Quelle valeur prend-il ?
2. Pourquoi ne faut-il pas exposer les clés API (ex. `GROQ_API_KEY`) dans la réponse de `/api/status`, même partiellement ?
3. Quel timeout (en secondes) semble raisonnable pour le health check TTS dans `/api/status` ? Justifiez en fonction de la latence observée en fonctionnement normal.
4. Si `/api/status` lui-même met plus de 10 secondes à répondre, que cela indique-t-il ?

---

## Partie 2 — Comprendre l'interface vocale (1h)

> `ui/app.js` est le fichier JavaScript qui pilote toute l'interface vocale. Jusqu'ici, vous n'en avez jamais eu besoin pour faire fonctionner l'agent. Dans cette partie, vous allez l'ouvrir et suivre le flux d'un message vocal de bout en bout.

### 2.1 Le cycle de vie d'un message vocal

Ouvrez `ui/app.js` et suivez les fonctions dans l'ordre du flux réel :

1. **`_genId()`** (ligne ~35) — génère le `session_id` côté client au chargement de la page
2. **`startRecording()`** — demande l'accès au microphone, crée un `MediaRecorder`
3. **`stopRecording()`** — arrête l'enregistrement, déclenche `sendAudio()`
4. **`sendAudio(blob)`** — envoie l'audio en deux étapes : d'abord `POST /api/transcribe`, puis `POST /api/text` avec la transcription
5. **`handleAgentResponse(data)`** — met à jour `sessionId` si le serveur en retourne un, gère les étapes de commande (`order_step`)
6. **`addBotResponse(data)`** — affiche la bulle de réponse, lit l'audio TTS si `data.audio_base64` est présent

**Questions :**
1. Où est stocké le `session_id` entre deux messages d'une même conversation ? Est-ce une variable locale ou globale ?
2. Que se passe-t-il si l'utilisateur recharge la page (`F5`) en plein milieu d'une commande ?
3. Quel codec audio est utilisé en priorité par `startRecording()` ? Et si ce codec n'est pas supporté par le navigateur ?
4. Pourquoi l'interface envoie-t-elle `session_id` dans le corps de la requête dès le premier message, alors que la session vient d'être créée et que le serveur ne la connaît pas encore ?

---

### 2.2 Observer la robustesse de la session

**Comportement actuel :** le `session_id` est généré une fois au chargement de la page (`_genId()` ligne ~36 de `ui/app.js`) et stocké en mémoire JavaScript. Il n'est **pas** persisté dans `localStorage` ni dans les cookies — un rechargement de page génère un nouvel identifiant.

**Exercice — Observer la perte de session lors d'un rechargement :**

1. Ouvrez les DevTools du navigateur (F12) → onglet **Console**.
2. Démarrez une commande : envoyez "Bonjour, je voudrais 2 bœufs bourguignons". L'agent devrait vous demander votre prénom.
3. Dans la console, tapez `sessionId` et appuyez sur Entrée. Notez la valeur affichée (ex : `"a3f8-…"`).
4. Rechargez la page (F5 ou Ctrl+R).
5. Envoyez "Bonjour" et observez ce que répond l'agent.
6. Tapez à nouveau `sessionId` dans la console. Comparez avec la valeur notée à l'étape 3.

**Complétez le tableau de comparaison :**

| | Avant rechargement | Après rechargement |
|---|---|---|
| Valeur de `sessionId` | | |
| Étape de commande côté agent | | |
| Réponse de l'agent au message suivant | | |

7. Ouvrez DevTools → onglet **Application** → **Local Storage** → `http://localhost:8000`. Y a-t-il une clé `traiteur_session` ? Qu'est-ce que cela vous dit sur l'implémentation actuelle ?

**Questions :**
1. Quelle est la durée de vie d'une entrée dans `localStorage` ? Dans quel cas est-elle effacée automatiquement ?
2. En quoi stocker un `session_id` dans `localStorage` diffère-t-il du stockage dans un cookie du point de vue du RGPD ?
3. Si un utilisateur laisse sa commande en suspens pendant 2 heures puis revient, que se passe-t-il côté backend quand il envoie un nouveau message avec l'ancien `session_id` ? (Indice : inspectez la gestion des sessions dans `src/app.py`)
4. Si on persistait le `session_id` dans `localStorage`, à quels moments faudrait-il le nettoyer ? Listez trois événements qui devraient déclencher ce nettoyage.

---

## Partie 3 — Décisions d'architecture (1h)

> `docs/DECISIONS.md` documente les choix de conception sous forme d'ADR (Architecture Decision Records). Un ADR répond à la question "pourquoi a-t-on fait ça plutôt qu'autre chose ?". C'est le fichier que vous lirez dans 6 mois quand vous vous demanderez pourquoi il n'y a pas de LangChain dans ce projet.

### 3.1 Lire les décisions documentées

Ouvrez `docs/DECISIONS.md`. Ce fichier contient 7 ADRs (ADR-01 à ADR-07).

**Questions sur les ADRs :**
1. (ADR-01) Le menu fait ~500 tokens. À partir de quelle taille (en tokens) le RAG deviendrait-il justifié selon l'ADR-01 ? Quelle est la limite évoquée ?
2. (ADR-03) Qu'est-ce que le "provider pattern" ? En quoi est-il différent d'une suite de `if/elif` sur le nom du provider ?
3. (ADR-05) LangChain a été supprimé. Quelle est la raison principale citée dans l'ADR-05 — poids des dépendances, complexité de debug, ou les deux ? Citez la phrase exacte.
4. (ADR-07) Le logging filtre les données sensibles. Quel marqueur dans les logs indique qu'un numéro de carte bancaire a été masqué ? Quel fichier implémente ce filtre ?

---

### 3.2 Pourquoi pas de RAG ?

Le menu est injecté intégralement dans le prompt système à chaque requête. C'est la décision ADR-01.

**Exercice — Mesurer la taille du prompt :**

```bash
python -c "
import yaml
from pathlib import Path

menu = yaml.safe_load(Path('src/menu/menu.yaml').read_text(encoding='utf-8'))
prompt = yaml.safe_load(Path('src/prompts/system_prompt.yaml').read_text(encoding='utf-8'))

menu_text = menu.get('text', '')
classify_prompt = str(prompt.get('classify', ''))
respond_prompt = str(prompt.get('respond', ''))

print(f'Menu : {len(menu_text)} caractères ≈ {len(menu_text)//4} tokens')
print(f'Classify prompt : {len(classify_prompt)} chars ≈ {len(classify_prompt)//4} tokens')
print(f'Respond prompt : {len(respond_prompt)} chars ≈ {len(respond_prompt)//4} tokens')
print(f'Total estimé par requête : ≈ {(len(menu_text)+len(classify_prompt)+len(respond_prompt))//4} tokens')
"
```

**Questions :**
1. Combien de tokens le prompt système consomme-t-il environ à chaque requête ?
2. Citez deux avantages concrets du "no RAG" pour un projet en production maintenu par une équipe de 2 personnes.
3. À partir de quelle taille de menu (en tokens) le RAG deviendrait-il économiquement justifié, sachant que Groq facture au token d'entrée ?
4. Si vous deviez implémenter du RAG sur ce projet demain, quels deux outils choisiriez-vous ? Justifiez brièvement.

---

### 3.3 Pourquoi deux appels LLM par requête (`classify` + `respond`) ?

Dans `src/app.py`, chaque message utilisateur déclenche deux appels LLM distincts :
- `_llm_classify(text)` → détecte l'intent (`info`, `commande`, `suppression`, etc.) et extrait les articles commandés
- `_llm_respond(intent, text, order_items)` → génère la réponse conversationnelle adaptée à l'intent

**Questions :**
1. Citez deux avantages du double appel (classify + respond) par rapport à un appel unique qui ferait les deux en même temps.
2. Quel est l'inconvénient principal du double appel en termes d'expérience utilisateur ?
3. Dans quel cas un seul appel LLM serait-il préférable ? (Pensez à la latence perçue sur mobile avec une connexion lente)
4. Le pipeline CI/CD (TP05) exécute le golden set promptfoo à chaque push. En quoi cela facilite-t-il le test des deux approches si vous voulez expérimenter un seul appel LLM ?

---

### 3.4 Limites connues et évolutions possibles

L'agent actuel présente plusieurs limitations identifiées. Remplissez le tableau suivant en vous basant sur vos expériences des TP précédents et vos tests :

| # | Limitation | Symptôme observable | Solution technique possible |
|---|---|---|---|
| 1 | Négation dans les commandes | "Je ne veux PAS de bœuf" commande quand même du bœuf | ? |
| 2 | Pluriels ambigus | "des macarons" → quantité indéterminée | ? |
| 3 | Références pronominales | "j'en veux 4" sans contexte immédiat | ? |
| 4 | Contexte long (> 10 tours) | L'agent "oublie" les premiers éléments de la commande | ? |
| 5 | Multi-langue | Mélange français/anglais dégrade la classification | ? |

**Questions :**
1. Parmi ces 5 limitations, laquelle aurait le plus d'impact sur la satisfaction des clients du traiteur Dupont au quotidien ? Justifiez.
2. Estimez le temps de développement pour corriger la limitation n°1 (négation). Décomposez en : modification du prompt, ajout de tests, validation golden set.
3. La limitation n°4 (contexte long) est-elle un problème de prompt, de modèle, ou d'architecture ? Argumentez.
4. Comment le golden set du TP03 pourrait-il être étendu pour détecter automatiquement une régression sur la limitation n°3 (références pronominales) ?

---

## Rendu attendu

- [ ] Les 5 scénarios de panne (1.1) : pour chaque scénario, la démarche de diagnostic, la cause racine identifiée et le correctif documentés par écrit
- [ ] Section 1.2 : les 4 questions sur les logs structurés répondues, avec au moins un exemple de log JSON réel extrait de votre agent
- [ ] Section 1.3 : capture d'écran ou sortie terminal de `/api/status` avec le service TTS arrêté
- [ ] Section 2.2 : tableau "avant/après rechargement" complété avec les valeurs observées, réponses aux 4 questions (durée de vie `localStorage`, différence RGPD avec les cookies, comportement backend après expiration de session, événements de nettoyage)
- [ ] Section 3.1 : les 4 questions sur les ADRs répondues en citant `docs/DECISIONS.md`
- [ ] Section 3.4 : le tableau des limites rempli avec des solutions techniques argumentées
