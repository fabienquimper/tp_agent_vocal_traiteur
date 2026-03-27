# 03 — Atomic Design : la logique composant que tu connais déjà

> ⏱ **Durée :** 30 min
> 🎯 **Objectif :** Reconnaître dans l'interface la même logique de décomposition qu'en code

---

## Pourquoi l'Atomic Design intéresse les développeurs

Brad Frost a inventé cette méthode en 2013.
L'idée : **une interface, c'est comme de la chimie**.

- Les **atomes** sont les éléments les plus simples (bouton, input, badge)
- Les **molécules** sont des groupes d'atomes qui fonctionnent ensemble (barre de recherche)
- Les **organismes** sont des sections complètes (header, bulle de chat)
- Les **templates** sont des squelettes de pages
- Les **pages** sont les templates avec du vrai contenu

**En tant que développeur, tu penses déjà comme ça.**
Tu crées des `<button>`, des `<form>`, des `<div class="chat-bubble">`.
L'Atomic Design, c'est juste mettre des noms sur ce que tu fais déjà.

---

## Les 5 niveaux avec l'app traiteur

### Niveau 1 — Atomes (les briques de base)

Ce sont les éléments HTML purs, stylés mais sans logique métier.

```html
<!-- Atome : Bouton -->
<button class="btn-primary">Envoyer</button>

<!-- Atome : Input -->
<input type="text" placeholder="Votre message..." />

<!-- Atome : Badge -->
<div class="intent-badge">📋 Informations</div>

<!-- Atome : Avatar bot -->
<div class="avatar">🤖</div>

<!-- Atome : Indicateur de statut -->
<span class="status-dot online"></span>
```

**Dans `style.css` :** chaque atome a sa classe CSS isolée.
Les atomes n'ont pas de marge externe (pas de `margin`) — c'est la molécule qui gère l'espacement.

### Niveau 2 — Molécules (atomes qui collaborent)

Une molécule a un rôle précis. Elle combine des atomes.

```html
<!-- Molécule : Zone de saisie -->
<div class="input-area">
  <input type="text" placeholder="Votre message..." />
  <button class="btn-send">▶</button>
  <button class="btn-mic">🎤</button>
</div>

<!-- Molécule : Bulle de message utilisateur -->
<div class="message user">
  <div class="bubble">J'aimerais commander 3 tartes...</div>
</div>

<!-- Molécule : Badge + texte de statut -->
<div class="order-status">
  <span class="order-total">Total estimé : 60.00 €</span>
  <div class="intent-badge">👤 En attente : nom...</div>
</div>
```

### Niveau 3 — Organismes (sections fonctionnelles)

Un organisme est une section complète de l'interface. Il peut fonctionner de manière autonome.

```html
<!-- Organisme : Header -->
<header>
  <span class="logo">🍽️</span>
  <div class="title-block">...</div>
  <span class="status-dot"></span>
  <a href="/traiteur.html">📋</a>
</header>

<!-- Organisme : Bulle de réponse bot complète -->
<div class="message bot">
  <div class="avatar">🤖</div>
  <div class="bubble">
    [texte de la réponse]
    [badge total]
    [bouton audio]
    [intent badge]
  </div>
</div>

<!-- Organisme : Formulaire de paiement -->
<div class="payment-form">
  <p class="payment-title">💳 Paiement CB</p>
  <p class="payment-amount">Montant : 60.00 €</p>
  <input class="payment-input" placeholder="Numéro de carte..." />
  <div class="payment-row">...</div>
  <button class="btn-pay">Payer</button>
  <p class="payment-hint">Test : 4242...</p>
</div>
```

### Niveau 4 — Templates (squelettes de pages)

Le template définit **la structure** sans le contenu réel.

```
Page Chat — Template :
┌─────────────────────────────┐
│ [HEADER]                    │
├─────────────────────────────┤
│                             │
│  [CHAT-AREA]                │  ← scroll vertical
│  (liste de messages)        │
│                             │
├─────────────────────────────┤
│ [STATUS-BAR]                │
├─────────────────────────────┤
│ [INPUT-AREA]                │
└─────────────────────────────┘
```

```
Page Traiteur — Template :
┌─────────────────────────────┐
│ [HEADER]                    │
├─────────────────────────────┤
│ [STATS-GRID]                │  ← 4 cartes métriques
├─────────────────────────────┤
│ [TOOLBAR]     [BTN-REFRESH] │
├─────────────────────────────┤
│ [TABLE-WRAPPER]             │  ← tableau responsive
└─────────────────────────────┘
```

### Niveau 5 — Pages (templates + vrai contenu)

C'est ce que l'utilisateur voit : le template avec des vraies commandes, de vrais messages, de vraies données.

---

## Inventaire des composants de l'app

Voici tous les composants identifiés dans l'interface actuelle :

### Atomes
| Composant | Classe CSS | Fichier |
|-----------|-----------|---------|
| Bouton envoi | `.btn-send` | `style.css` |
| Bouton micro | `.btn-mic` | `style.css` |
| Bouton payer | `.btn-pay` | `style.css` |
| Bouton lecture audio | `.btn-play-audio` | `style.css` |
| Avatar bot | `.avatar` | `style.css` |
| Indicateur statut | `.status-dot` | `style.css` |
| Badge intention | `.intent-badge` | `style.css` |
| Badge total commande | `.order-total` | `style.css` |
| Input texte | `#textInput` | `style.css` |
| Input carte CB | `.payment-input` | `style.css` |

### Molécules
| Composant | Classes CSS | Description |
|-----------|------------|-------------|
| Bulle utilisateur | `.message.user > .bubble` | Texte ou audio |
| Bulle bot | `.message.bot > .bubble` | Réponse + badge + audio |
| Bulle "Réflexion" | `.thinking-bubble` | Animée, pendant traitement |
| Zone de saisie | `.input-area` | Input + 2 boutons |
| Transcription audio | `.audio-transcript` | Texte sous la bulle audio |

### Organismes
| Composant | ID/Classe CSS | Description |
|-----------|--------------|-------------|
| Header | `header` | Logo + titre + liens + statut |
| Zone de chat | `#chatArea` | Conteneur scrollable des messages |
| Formulaire CB | `.payment-form` | Formulaire paiement inline |
| Choix sur place | `.payment-choice` | Boutons après refus CB |
| Barre de statut | `#statusBar` | Feedback transcription/traitement |

---

## Exercice 1 — Décomposition dans Penpot

Dans Penpot, tu vas créer des **composants** pour chaque atome.
Un composant Penpot = une classe CSS réutilisable.

**À créer en premier (les atomes) :**
1. Un bouton vert avec texte blanc (→ `.btn-pay`)
2. Un badge vert arrondi avec texte (→ `.intent-badge`)
3. Un avatar 🤖 dans un cercle gris

**Pourquoi commencer par les atomes ?**
Parce que si tu changes la couleur de "vert" en "bleu" dans l'atome,
tous les composants qui utilisent cet atome se mettent à jour automatiquement.
Exactement comme les variables CSS :

```css
:root {
  --primary: #2E7D32;  /* Changer ici = change partout */
}
```

---

## Exercice 2 — Trouver la molécule manquante

L'interface actuelle n'a **pas** de composant "message d'erreur".

Quand le paiement échoue, on affiche le texte d'erreur en rouge dans le formulaire.
Mais il n'y a pas de composant standardisé pour les erreurs de l'agent (réseau coupé, Ollama indisponible...).

**Ta mission :**
Dessine (sur papier ou dans Penpot) une molécule "message d'erreur" cohérente avec le design system.
Elle devrait contenir :
- Une icône ⚠️
- Un texte d'erreur (ex: "Service temporairement indisponible")
- Un bouton "Réessayer"

Quelles contraintes de design dois-tu respecter pour qu'elle s'intègre à l'interface existante ?

---

## Le lien direct avec ton code

```
ATOMIC DESIGN          ÉQUIVALENT CODE
──────────────         ──────────────────────────
Atome                  classe CSS + élément HTML
Molécule               fonction JS addBotMessage()
Organisme              section HTML + gestionnaire d'événements
Template               layout HTML (structure div)
Page                   index.html rendu dans le navigateur
```

En React ou Vue, tu aurais :
- Atome → `<Button />`
- Molécule → `<ChatBubble />`
- Organisme → `<ChatArea />`
- Template → `<ChatLayout />`
- Page → `<ChatPage />`

Ici on est en Vanilla JS, donc c'est plus implicite — mais la logique est identique.

---

## Ce qu'on a appris

- Atomic Design = décomposer l'interface de la même façon qu'on décompose le code
- Commencer par les atomes garantit la cohérence visuelle de toute l'app
- Cette logique se traduit directement en classes CSS, fonctions JS, ou composants React/Vue

➡️ **Suite :** [04 — Wireframing avec l'IA](../04_wireframing_avec_ia/README.md)
