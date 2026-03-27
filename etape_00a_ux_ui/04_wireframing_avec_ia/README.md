# 04 — Wireframing avec l'IA : générer une structure en 5 minutes

> ⏱ **Durée :** 30 min
> 🎯 **Objectif :** Utiliser Claude/ChatGPT pour générer la structure HTML d'un écran, puis l'affiner

---

## C'est quoi un wireframe ?

Un wireframe (maquette filaire) = la **structure** d'une interface sans le design.
Pas de couleurs, pas de polices, pas d'images — juste les blocs et leur disposition.

```
MAUVAISE APPROCHE             BONNE APPROCHE
────────────────              ─────────────────
Ouvrir Photoshop              1. Wireframe (structure)
Choisir les couleurs          2. Validation avec le persona
Dessiner les boutons          3. Design (couleurs, typo)
Se rendre compte que          4. Code
ça ne marche pas              5. Tests utilisateur
Recommencer                   ↑ 80% des problèmes trouvés
                               aux étapes 1-2, pas en prod
```

**Un bon wireframe prend 10-30 minutes et évite des heures de refactoring.**

---

## L'IA comme outil de wireframing

L'IA excelle à générer des structures HTML annotées ("wireframes en code").
Tu n'as pas besoin de savoir dessiner — tu décris, l'IA structure.

**Workflow recommandé :**
1. Prompt Claude/ChatGPT → HTML filaire annoté
2. Ouvrir dans le navigateur → vérification rapide
3. Importer les éléments dans Penpot
4. Ajuster selon les lois de design (module 02)

---

## Les 3 prompts prêts à l'emploi

### Prompt 1 — Interface chat (Sophie, cliente)

```
Tu es un expert UX spécialisé en interfaces conversationnelles.
Génère le wireframe HTML d'une interface de chatbot vocal pour le site web
d'un traiteur français (Traiteur Dupont, Dijon).

Contraintes UX :
- Utilisateur principal : Sophie, 42 ans, sur smartphone, pressée
- Loi de Hick : maximum 3 actions visibles simultanément
- Loi de Fitts : zone de saisie en bas (accessible au pouce)
- Loi de Miller : pas plus de 5-7 éléments par section

Fonctionnalités à intégrer :
- Zone de chat scrollable avec bulles (bot à gauche, utilisateur à droite)
- Bouton micro (grande zone tactile ≥ 48px, bas droite)
- Champ texte + bouton envoi
- Indicateur "en train de taper..." animé
- Badge statut du service (en ligne / hors ligne)

Format de réponse : HTML commenté avec des annotations UX
(/* DÉCISION UX : raison du choix */).
Utilise des Lorem ipsum ou des exemples de commande traiteur.
Pas de CSS (juste la structure).
```

### Prompt 2 — Dashboard traiteur (Marc, employé)

```
Génère le wireframe HTML d'un tableau de bord de commandes pour un gérant
de restauration traiteur.

Utilisateur : Marc, gérant, 38 ans, ordinateur de bureau, scan rapide le matin.
Objectif : voir en un coup d'œil les commandes du jour et leur statut de paiement.

Éléments à inclure :
- 4 cartes de métriques : total commandes, payées CB, règlement sur place, CA total
- Tableau des commandes : Réf. | Date | Client | Articles (résumé) | Total | Paiement
- Bouton "Actualiser"
- Filtre par statut de paiement (optionnel)

Contraintes :
- Design épuré, pas de surcharge visuelle
- Le statut de paiement doit être immédiatement identifiable (code couleur)
- Adapté à un écran 1280x720 minimum

Format : HTML annoté avec décisions UX. Données exemple réalistes (noms français,
plats de traiteur, montants cohérents).
```

### Prompt 3 — Formulaire de paiement inline (dans le chat)

```
Génère le wireframe d'un formulaire de paiement CB qui s'intègre comme une "carte"
dans une interface de chat.

Contexte : Ce formulaire apparaît dans la conversation après que l'agent demande
le mode de paiement. Il ne doit pas ouvrir une nouvelle page mais s'insérer
dans le fil de conversation.

Éléments :
- Titre "💳 Paiement sécurisé" + montant en évidence
- Champ numéro de carte (formatage automatique 4444 4444 4444 4444)
- Champs expiration + CVV côte à côte
- Bouton "Payer X €" (couleur différente = action critique)
- Lien "Annuler / Régler sur place"
- Note rassurante sur la sécurité
- Cartes de test : 4242... = OK, 4000...0002 = KO

UX critique : l'utilisateur doit comprendre immédiatement que c'est une action
irréversible. Comment signaler ça visuellement sans créer d'anxiété inutile ?

Format : HTML annoté.
```

---

## Exemple de sortie IA commentée

Voici un exemple de ce que l'IA génère pour le prompt 3 :

```html
<!-- ────────────────────────────────────────────────────────────────
     WIREFRAME — Formulaire CB inline dans le chat
     DÉCISION UX : Fond jaune clair → signal "attention requise"
     sans alarmer (rouge = danger, jaune = vigilance)
     ──────────────────────────────────────────────────────────────── -->
<div class="payment-card" role="form" aria-label="Formulaire de paiement par carte">

  <!-- DÉCISION UX : Icône + titre → ancre cognitive immédiate -->
  <header class="payment-header">
    <span aria-hidden="true">💳</span>
    <h2>Paiement sécurisé</h2>
  </header>

  <!-- DÉCISION UX : Montant EN GROS → évite les surprises, principe de transparence -->
  <p class="payment-amount" aria-live="polite">
    Montant à débiter : <strong>60,00 €</strong>
  </p>

  <!-- DÉCISION UX : champ unique, pleine largeur → Fitts (grand, facile à toucher) -->
  <!-- Formatage 4-4-4-4 → Miller (chunking, réduit la charge cognitive) -->
  <label for="card-number">Numéro de carte
    <input id="card-number" type="text" inputmode="numeric"
           autocomplete="cc-number" maxlength="19"
           placeholder="1234 5678 9012 3456"
           aria-describedby="card-hint" />
  </label>

  <!-- DÉCISION UX : 2 champs côte à côte → même "groupe logique" (proximité Gestalt) -->
  <div class="card-secondary-fields" role="group" aria-label="Validité et code de sécurité">
    <label for="expiry">Expiration
      <input id="expiry" type="text" inputmode="numeric"
             autocomplete="cc-exp" maxlength="5" placeholder="MM/AA" />
    </label>
    <label for="cvv">CVV
      <input id="cvv" type="text" inputmode="numeric"
             autocomplete="cc-csc" maxlength="3" placeholder="123"
             aria-describedby="cvv-hint" />
      <span id="cvv-hint" class="hint">3 chiffres au dos de la carte</span>
    </label>
  </div>

  <!-- DÉCISION UX : bouton CTA (Call To Action) distinct des boutons secondaires
       Action irréversible → couleur pleine, libellé explicite avec le montant -->
  <button type="submit" class="btn-pay-confirm">
    Payer 60,00 € par carte
  </button>

  <!-- DÉCISION UX : Échappatoire visible → réduit l'anxiété de l'utilisateur
       (s'il sait qu'il peut annuler, il est moins stressé) -->
  <button type="button" class="btn-pay-cancel">
    Annuler — je réglerai sur place
  </button>

  <!-- DÉCISION UX : Note de sécurité → signal de confiance.
       Petite typographie → ne surcharge pas visuellement -->
  <p class="security-note" role="note">
    🔒 Paiement simulé — aucune donnée réelle transmise.
    Test : 4242 4242 4242 4242 = accepté
  </p>
</div>
```

---

## Ce que tu observes dans cet exemple

1. **`role="form"` et `aria-label`** → déjà pensé accessibilité (RGAA module 06)
2. **`inputmode="numeric"`** → le clavier numérique s'ouvre sur mobile (Fitts)
3. **`autocomplete="cc-number"`** → le navigateur peut auto-remplir (UX rapide)
4. **`aria-describedby`** → description additionnelle pour les lecteurs d'écran
5. **Labels explicites** → pas de placeholder comme seul label (piège UX/RGAA courant)

---

## Exercice — Générer et comparer

**Étape 1 :** Lance les 3 prompts dans Claude ou ChatGPT.

**Étape 2 :** Ouvre les 3 fichiers HTML générés dans un navigateur.
Compare avec les vraies pages de `etape_01` :

| Critère | Version IA | Version réelle | Quelle version est meilleure ? |
|---------|-----------|----------------|-------------------------------|
| Nombre d'actions sur l'écran | ? | 3 (Hick ✅) | ? |
| Labels accessibles | ? | Partiellement | ? |
| Zone micro tactile | ? | 48px (Fitts ✅) | ? |
| Clarté du formulaire CB | ? | Moyenne | ? |

**Étape 3 :** Prends la meilleure version et prépare-la pour Penpot (module 05).

---

## Le Copywriting : les textes aussi font partie du design

L'IA peut aussi générer les **textes** de l'interface (UX Writing).

```
Prompt UX Writing :

Rédige les textes d'interface pour un chatbot vocal traiteur.
Public : clients de 30-60 ans, pas forcément tech-savvy.
Ton : professionnel mais chaleureux, jamais froid.

Textes à rédiger :
1. Message de bienvenue (2 phrases max)
2. Placeholder du champ texte (3-4 mots)
3. Texte du bouton d'envoi (1 mot)
4. Message d'erreur réseau (1 phrase rassurante, pas technique)
5. Confirmation de commande (2-3 phrases, inclure le numéro de commande)
6. Message si paiement CB refusé (1 phrase, proposer alternative)

Contrainte : pas de jargon technique, pas de "erreur 500", pas de "null"
```

---

## Récapitulatif

- Wireframe = structure d'abord, design ensuite
- L'IA génère la structure + les annotations UX en quelques secondes
- Les prompts avec des contraintes précises (Hick, Fitts, Miller) donnent de meilleurs résultats
- Le code HTML généré est directement importable/adaptable dans Penpot ou dans l'app

➡️ **Suite :** [05 — Penpot : atelier pratique](../05_penpot_atelier/README.md)
