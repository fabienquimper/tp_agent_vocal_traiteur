# Prompts prêts à l'emploi — Wireframing IA

Copie-colle directement dans Claude, ChatGPT ou Gemini.

---

## PROMPT MAÎTRE — Interface complète (version avancée)

```
Tu es un expert UX/UI spécialisé en interfaces conversationnelles et accessibilité RGAA.

PROJET : Interface chatbot vocal pour le site web du Traiteur Dupont (Dijon, France).

UTILISATEURS :
- Sophie, 42 ans, cliente, smartphone, pressée (commande en moins de 3 min)
- Marc, 38 ans, employé, ordinateur, scan rapide des commandes

PAGES À CONCEVOIR (3 wireframes HTML annotés) :

PAGE 1 — chat.html (Sophie)
Fonctionnalités : messages bot/user, micro hold-to-record, envoi texte,
indicateur "en cours de traitement", badge commande + total,
formulaire CB inline (apparaît dans la conversation).

PAGE 2 — traiteur.html (Marc)
Fonctionnalités : 4 métriques clés, tableau des commandes filtrable,
badge statut paiement coloré, bouton actualiser.

PAGE 3 — Formulaire CB (composant, pas une page entière)
Fonctionnalités : carte dans le chat, champ carte + expiry + CVV,
bouton payer + annuler, note sécurité.

CONTRAINTES OBLIGATOIRES pour chaque wireframe :
- [ ] RGAA : tous les inputs ont un <label>, attributs aria-* pertinents
- [ ] Fitts : zones tactiles ≥ 48px sur mobile
- [ ] Hick : ≤ 5 actions possibles par écran
- [ ] Proximité Gestalt : éléments liés sont visuellement groupés
- [ ] inputmode correct sur mobile (numeric pour CB, text pour messages)

FORMAT DE RÉPONSE :
HTML commenté avec /* DÉCISION UX : [raison] */ pour chaque choix non évident.
Structure uniquement, pas de CSS de design (juste du HTML sémantique et des class= pour nommer les composants).
Données exemple réalistes (noms français, plats traiteur, montants cohérents).
```

---

## PROMPT AUDIT — Analyser l'interface existante

```
Voici le HTML simplifié de l'interface chat d'un agent vocal traiteur :

[COLLE ICI LE HTML DE index.html]

Effectue un audit UX en évaluant :
1. Loi de Hick : combien d'actions l'utilisateur doit-il gérer simultanément ?
2. Loi de Fitts : les zones cliquables/tactiles sont-elles suffisamment grandes ?
3. RGAA niveau AA : les inputs ont-ils des labels ? Les images des alt-text ?
4. Lisibilité : le rapport de contraste texte/fond est-il ≥ 4.5:1 ?
5. Clarté du flux : un utilisateur non-tech comprend-il comment passer une commande ?

Pour chaque point : note /5, observation, recommandation concrète.
```

---

## PROMPT AMÉLIORATION — Version mobile-first

```
L'interface chat actuelle a été conçue pour desktop puis adaptée mobile.
Reconçois-la en mobile-first pour Sophie (iPhone, pouce droit, debout dans les transports).

Contraintes spécifiques mobile :
- Hauteur totale : 100dvh (dynamic viewport height pour les navigateurs mobile)
- Zone de saisie fixe en bas : ne disparaît pas quand le clavier apparaît
- Bouton micro : 60px minimum, coin bas droit (zone naturelle du pouce)
- Scroll uniquement dans la zone des messages (pas de la page entière)
- Taille police minimum : 16px (évite le zoom auto iOS)
- Pas de hover effects (pas de souris sur mobile)

Génère le HTML + structure CSS (flexbox/grid) commentés.
```

---

## PROMPT VARIANTE DARK MODE

```
Génère une variante dark mode du formulaire de paiement CB du chatbot traiteur.

Palette actuelle (light) :
- Fond formulaire : #FFFDE7 (jaune très clair)
- Bordure : #FFE082 (jaune moyen)
- Bouton payer : #2E7D32 (vert)

Palette dark mode attendue :
- Fond formulaire : à définir (doit garder la signification "action importante")
- Texte : lisible (contraste RGAA ≥ 4.5:1 sur fond sombre)
- Bouton payer : reste identifiable comme CTA principal

Génère les variables CSS :
:root { ... }
[data-theme="dark"] { ... }

Et explique chaque choix de couleur avec le ratio de contraste calculé.
```

---

## PROMPT UX WRITING COMPLET

```
Rédige tous les textes de l'interface chatbot vocal Traiteur Dupont.
Public : 30-60 ans, non-techniciens.
Ton : professionnel et chaleureux, jamais condescendant.

TEXTES À RÉDIGER :

Navigation :
- Titre de la page (onglet navigateur)
- Texte du lien vers le dashboard traiteur

En-tête :
- Tagline sous le nom de l'entreprise (5 mots max)

Zone de chat :
- Message de bienvenue de l'agent (2 phrases, présente les capacités)
- Placeholder de l'input texte
- Label du bouton envoi (accessible, pas juste une icône)
- Label du bouton micro (accessible)

États d'attente :
- "Transcription en cours" (statut, 3 mots)
- Messages de la bulle "Réflexion" (5 messages rotatifs, chacun 3-4 mots)

Collecte d'infos client :
- Demande de nom + prénom + téléphone (1 phrase naturelle)
- Confirmation reçue du nom (1 phrase avec prénom)
- Demande du mode de paiement (1 phrase avec le total)

Paiement CB :
- Titre du formulaire
- Placeholder numéro de carte
- Placeholder expiry + CVV
- Texte bouton "payer" (inclure le montant)
- Note de sécurité (1 phrase rassurante)
- Message succès paiement (2 phrases, inclure numéro de commande)
- Message échec paiement + proposition sur place (2 phrases)

Erreurs :
- Service IA indisponible (1 phrase, pas de jargon technique)
- Erreur réseau (1 phrase rassurante)
- Commande produit hors catalogue (1 phrase, redirige vers boutique)

Format : tableau Markdown | Composant | Texte actuel | Texte amélioré | Raison
```
