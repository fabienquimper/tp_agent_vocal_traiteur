# TP 01 — Logs, RGPD & AI Act : audit d'un agent vocal IA

> **Niveau** : intermédiaire | **Durée estimée** : 2 h | **Prérequis** : avoir parcouru l'architecture de l'étape 01

---

## Mise en situation

Vous venez d'être recruté comme consultant technique par le **Traiteur Dupont** de Dijon.
Leur développeur a livré l'étape 01 de l'agent vocal il y a deux semaines.
Le directeur a reçu un email d'un client mécontent qui a "entendu parler du RGPD" et qui se demande
ce que le traiteur fait avec sa voix, son nom et son numéro de carte.

Le directeur vous demande un **audit rapide** avant que la CNIL ne frappe à la porte.

Vous ouvrez le code. Bonne chance.

---

## 1. Ce que vous devez savoir avant de commencer

### 1.1 Le RGPD en 5 principes (version terrain)

Le Règlement Général sur la Protection des Données (2018) n'est pas une liste de cases à cocher.
C'est une philosophie : **les données personnelles appartiennent aux personnes, pas aux entreprises.**

Les 5 principes que vous rencontrerez dans ce TP :

| Principe | Ce que ça veut dire en vrai |
|---|---|
| **Finalité** | On collecte les données pour une raison précise, et on ne s'en sert pas pour autre chose. |
| **Minimisation** | On ne collecte que ce dont on a besoin. Pas de "au cas où". |
| **Durée limitée** | On efface ce qu'on n'a plus besoin. Les données ne sont pas éternelles. |
| **Sécurité** | On protège les données contre les accès non autorisés et les fuites. |
| **Transparence** | La personne sait ce qu'on fait avec ses données, avant qu'on le fasse. |

> **Anecdote réelle** : En 2019, la CNIL a infligé 50 millions d'euros d'amende à Google pour
> manque de transparence lors de la création d'un compte Android. Le problème ? Les informations
> sur l'utilisation des données étaient "trop vagues, trop génériques". Le code de notre traiteur
> a le même problème — on y reviendra.

### 1.2 L'AI Act — ce qui change pour les agents IA

L'AI Act européen (entré en application progressivement depuis août 2024) introduit une obligation
nouvelle qui concerne directement notre agent vocal : **l'article 50**.

En résumé : **si votre IA parle à un humain, elle doit lui dire qu'elle est une IA.**

C'est simple, c'est clair, et notre agent ne le fait pas.

Il y a aussi des obligations de **traçabilité** : les systèmes d'IA doivent maintenir des logs
structurés permettant de comprendre les décisions prises. Pas juste des `print()` déguisés.

---

## 2. Exploration des logs — suivez la trace

### 2.1 Qu'est-ce qu'un log, exactement ?

Un log est une trace écrite de ce qui s'est passé dans votre application.
C'est l'équivalent du journal de bord d'un navire : irremplaçable pour comprendre un incident,
mais catastrophique si un marin y note "j'ai perdu la clé de la salle des torpilles".

Dans notre projet, le logging est fait avec la bibliothèque standard Python `logging`.
Voici comment l'initialisation est faite dans `services/agent/app/main.py` :

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)
```

Le format est lisible mais les logs partent où ? Dans la **sortie standard** du container Docker.
Pas de fichier, pas de rotation, pas de durée de rétention — ils vivent tant que Docker les garde.

### 2.2 Exercice 1 — Chasse aux données personnelles dans les logs

**Objectif** : identifier tous les endroits du code où des données personnelles (DCP) sont écrites dans les logs.

Parcourez les fichiers suivants et listez chaque appel `logger.info()` ou `logger.error()`
qui contient (ou pourrait contenir) une donnée personnelle :

- `services/agent/app/main.py`
- `services/agent/app/graph/nodes.py`
- `services/stt/app.py`

**Questions :**

**Q1.** Dans `nodes.py`, ligne ~115, que logue le nœud de transcription ?
Est-ce une donnée personnelle ? Pourquoi ?

```python
logger.info(f"Transcription : '{transcript}'")
```

**Q2.** Dans `main.py`, trouvez la ligne qui logue la finalisation d'une commande.
Quelles données personnelles apparaissent dans ce log ?

*Indice : cherchez `Commande finalisée`.*

**Q3.** Dans `main.py`, autour des lignes 270-272, qu'est-ce qui est passé à `write_order()` ?
Ces mêmes données transitent-elles par les logs ?

**Q4.** Le service STT (`stt/app.py`) logue-t-il le contenu de ce que dit l'utilisateur ?
Comparez les trois modes de déploiement (local Whisper, HuggingFace, Groq) — la réponse
n'est pas la même pour tous.

> **Note** : le projet supporte plusieurs providers STT selon la puissance du poste.
> En mode local, le contenu n'est pas loggué. En mode cloud (HF/Groq), observez ce que
> font les lignes ~115 et ~125. Ce décalage de comportement selon le provider est un
> vrai cas d'école en contexte on-premise vs. cloud.

---

### 2.3 Exercice 2 — Le voyage des données personnelles

Voici le flux d'une commande vocale dans notre système. Complétez le tableau en indiquant
à chaque étape quelles données personnelles sont présentes et si elles sont **loggées**,
**persistées** (stockées durablement) ou **juste en mémoire**.

| Étape | Données présentes | Loggée ? | Persistée ? | En mémoire ? |
|---|---|---|---|---|
| 1. Audio reçu par `/api/voice` | Voix brute de l'utilisateur | | | |
| 2. Transcription STT | Texte transcrit | | | |
| 3. Classification LLM | Texte + intent | | | |
| 4. Session créée | Nom, prénom (pas encore) | | | |
| 5. Collecte nom/prénom | Nom, prénom | | | |
| 6. Collecte téléphone | Téléphone | | | |
| 7. Collecte mode de paiement | Mode de paiement | | | |
| 8. Collecte CB (`/api/payment/simulate`) | Numéro de carte, CVV, expiry | | | |
| 9. Finalisation commande | Tout + total | | | |
| 10. Écriture Excel | Nom, prénom, tel, paiement | | | |

*Conseil : ouvrez `main.py` et suivez le code de `_handle_session_step` et `_finalize_order`.*

---

## 3. Analyse RGPD — les questions difficiles

### 3.1 Exercice 3 — Consentement et transparence

Ouvrez `ui/index.html` ou `ui/traiteur.html` et regardez l'interface utilisateur.

**Q5.** L'utilisateur voit-il une information lui indiquant :
- Qu'il va interagir avec une IA ?
- Quelles données seront collectées ?
- Comment seront-elles utilisées ?
- Combien de temps seront-elles conservées ?
- Comment exercer ses droits (accès, effacement) ?

**Q6.** Selon l'article 13 du RGPD, ces informations doivent être fournies
"au moment de la collecte". À quel moment précis la collecte commence-t-elle dans notre agent ?
*(La voix est-elle une donnée personnelle dès l'instant où elle est enregistrée ?)*

> **Pour aller plus loin** : La CNIL a publié en 2023 une recommandation sur les systèmes
> d'IA conversationnels. Elle précise que l'enregistrement vocal — même s'il n'est pas conservé —
> constitue un traitement de données dès sa collecte. L'absence de stockage ne dispense pas
> de l'obligation d'information.

**Q7.** Notre agent collecte le numéro de téléphone du client. Quelle est la **finalité déclarée** ?
Y a-t-il un risque de **détournement de finalité** si les fichiers Excel sont utilisés à d'autres fins ?

---

### 3.2 Exercice 4 — Durée de conservation

Regardez `services/agent/app/main.py` autour des lignes 107-119.

```python
_sessions: dict[str, OrderSession] = {}
_SESSION_TTL = timedelta(minutes=30)
```

**Q8.** Les sessions en mémoire sont nettoyées après 30 minutes d'inactivité.
C'est bien. Mais une fois la commande finalisée, que devient-elle ?
Regardez `orders/writer.py` — y a-t-il une durée de conservation définie pour les fichiers Excel ?

**Q9.** Selon le RGPD (article 5.1.e), les données doivent être conservées "le temps nécessaire
à la finalité". Pour une commande traiteur :
- Quelle durée serait raisonnable selon vous ?
- Quelle durée est requise par la loi française pour les données comptables ?
  *(Indice : Code de commerce, article L123-22)*

---

### 3.3 Exercice 5 — Droits des personnes

L'article 15 du RGPD donne à chaque personne le droit d'accéder à ses données.
L'article 17 donne le droit à l'effacement ("droit à l'oubli").

**Q10.** Parcourez tous les endpoints FastAPI dans `main.py` (cherchez les `@app.`).
Y a-t-il un endpoint permettant à un client de :
- Consulter ses commandes ?
- Demander l'effacement de ses données ?

**Q11.** Si un client appelle le traiteur en disant "J'exerce mon droit à l'oubli,
supprimez mes données", comment le traiteur pourrait-il le faire avec l'outil actuel ?
Évaluez la complexité de l'opération.

---

## 4. L'AI Act — Transparence obligatoire

### 4.1 Exercice 6 — L'obligation d'information

L'article 50 de l'AI Act dispose :

> *"Les fournisseurs de systèmes d'IA destinés à interagir avec des personnes physiques
> veillent à ce que les personnes physiques soient informées qu'elles interagissent
> avec un système d'IA, sauf si cela est évident au vu du contexte."*

**Q12.** Notre agent s'appelle "Traiteur Dupont — Agent Vocal IA". Le nom contient "IA".
Est-ce suffisant selon vous pour satisfaire l'obligation d'information ?
Argumentez en vous appuyant sur la notion de "personne raisonnablement informée".

**Q13.** Regardez la réponse système du LLM dans `nodes.py`, ligne ~221 :

```python
_RESPONSE_SYSTEM = """Tu es l'assistant vocal du Traiteur Dupont, une entreprise française
de restauration traiteur à Dijon. Tu réponds en français, avec chaleur et professionnalisme."""
```

L'agent est instruit de répondre "avec chaleur et professionnalisme" — ce qui est naturel.
Mais si un client demande directement "êtes-vous un robot ?", que devrait répondre l'agent ?
Y a-t-il une instruction à ce sujet dans le prompt système ?

---

### 4.2 Exercice 7 — Traçabilité des décisions IA

L'AI Act exige que les systèmes d'IA maintiennent des journaux permettant de comprendre
les décisions automatisées prises.

Regardez les logs de classification dans `nodes.py`, ligne ~130 :

```python
logger.info(f"Intent='{intent}' topic='{topic}' items={order_items}")
```

**Q14.** Ce log contient-il suffisamment d'informations pour auditer la décision du LLM ?
Qu'est-ce qui manque pour constituer un audit trail conforme ? Listez au moins 3 éléments.

*Indice : pensez à ce qu'un auditeur voudrait savoir : "qui a décidé quoi, quand, sur quelle base, avec quel modèle ?"*

**Q14b.** *(Dimension supplémentaire — nouvelle architecture)*
Le LLM est maintenant impliqué dans une deuxième décision automatisée : lors du
`make reload-docs`, il lit `menus.txt` et génère `catalog.json` — le fichier qui
détermine les prix facturés aux clients.

Cette décision est-elle tracée dans les logs ? Qu'est-ce qu'un auditeur AI Act devrait
pouvoir vérifier à propos de cette extraction automatique de prix ?

*Indice : imaginez que le LLM génère le prix "42.0" pour "bœuf bourguignon" — comment
savoir s'il a correctement lu le menu ou s'il a inventé ce prix ?*

---

## 5. Données bancaires — zone rouge

### 5.1 Exercice 8 — Le numéro de carte en clair

Regardez l'endpoint de paiement simulé dans `main.py`, lignes ~145-149 :

```python
class PaymentSimulateRequest(BaseModel):
    session_id: str
    card_number: str
    expiry: str = ""
    cvv: str = ""
```

Et l'utilisation, lignes ~667-669 :

```python
card = re.sub(r'[\s\-]', '', request.card_number)
if not card.isdigit() or len(card) != 16:
    raise HTTPException(status_code=400, detail="Numéro de carte invalide")
```

**Q15.** Le paiement est simulé (pas de vrai argent). Mais imaginez que ce code soit
en production avec une vraie passerelle de paiement. Identifiez au moins 3 problèmes
de sécurité/conformité dans la gestion actuelle du numéro de carte.

**Q16.** La norme PCI-DSS (Payment Card Industry Data Security Standard) interdit formellement
de stocker le CVV sous quelque forme que ce soit après la transaction.
Dans notre code, le CVV est dans `PaymentSimulateRequest`. Où pourrait-il apparaître
involontairement dans les logs ou les traces ? *(Cherchez les `logger.error` et les stack traces.)*

---

## 6. Checklist finale — À vous de jouer

Complétez cette checklist après avoir répondu aux exercices. Pour chaque point,
indiquez : ✅ Conforme | ⚠️ Partiel | ❌ Non conforme | ❓ À vérifier

### RGPD

- [ ] Information de l'utilisateur avant la collecte (art. 13/14)
- [ ] Base légale du traitement identifiée et documentée (art. 6)
- [ ] Durée de conservation définie et appliquée (art. 5.1.e)
- [ ] Droit d'accès aux données implémenté (art. 15)
- [ ] Droit à l'effacement implémenté (art. 17)
- [ ] Données minimales collectées (pas de "au cas où")
- [ ] Logs ne contenant pas de DCP inutiles
- [ ] Données stockées de façon sécurisée (chiffrement au repos)
- [ ] Données bancaires traitées conformément à PCI-DSS
- [ ] Endpoints d'administration protégés par authentification

### AI Act

- [ ] Information explicite "vous interagissez avec une IA" (art. 50)
- [ ] Réponse prévue si l'utilisateur demande si c'est une IA
- [ ] Audit trail structuré des décisions LLM (version modèle, timestamp, intent)
- [ ] Audit trail de la génération catalog.json (hash du menu, modèle, produits extraits)
- [ ] Documentation technique du système (art. 11)

### Bonne pratique générale

- [ ] Politique de rotation des logs définie
- [ ] Aucune DCP dans les messages d'erreur exposés à l'utilisateur
- [ ] Volumes Docker protégés en accès

---

## 7. Pour aller plus loin

**Textes de référence** :
- CNIL — Guide pratique de la sécurité des données personnelles (2023)
- CNIL — Recommandation sur les systèmes d'IA (délibération 2023-011)
- AI Act — Articles 50 (transparence) et 13 (information)
- OWASP LLM Top 10 — LLM06 (Sensitive Information Disclosure)

**À méditer** :
> "Le RGPD n'est pas un obstacle à l'innovation. C'est un cadre qui oblige à réfléchir
> avant d'agir. Les entreprises qui l'intègrent dès la conception (*privacy by design*)
> évitent les refontes coûteuses — et les amendes." — Max Schrems, NOYB (2022)

---

*La solution détaillée de ce TP est disponible dans `TP_01_logs_RGPD_ia_act_SOLUTION.md`.*
