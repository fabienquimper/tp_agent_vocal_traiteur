# Étape 00a — UX / UI : Concevoir avant de coder

> **Prérequis :** Aucun. Ce module vient *avant* etape_01 dans la logique d'apprentissage.
> **Durée :** 1 journée (environ 6h de travail guidé)
> **Outil central :** [Penpot](https://penpot.app) — gratuit, open-source, dans le navigateur

---

## Pourquoi ce module existe

Dans `etape_01`, tu as une application qui fonctionne.
Elle a une interface : des boutons, des bulles de chat, un formulaire de paiement.

**Ces choix de design ne sont pas des hasards.** Quelqu'un a décidé :
- que le bouton micro serait en bas à droite (pas en haut à gauche)
- que la couleur principale serait verte (pas rouge)
- que la bulle utilisateur serait à droite (pas à gauche)
- que le montant serait affiché dans un badge distinct

Ce module te donne les outils pour *comprendre* ces décisions — et pour en prendre toi-même de bonnes.

---

## Ce que ce n'est pas

- ❌ Un cours de graphisme (pas besoin de savoir dessiner)
- ❌ Un cours Photoshop / Illustrator (on utilise Penpot, pas Adobe)
- ❌ Une liste de règles esthétiques subjectives ("c'est beau/moche")

## Ce que c'est

- ✅ Une méthode pour **poser les bonnes questions** avant d'écrire du code
- ✅ Des **contraintes mesurables** (contraste RGAA, taille des zones cliquables)
- ✅ Une logique de **composants** que tu reconnais dans ton code HTML/CSS
- ✅ Une façon d'utiliser l'IA pour **accélérer le maquettage**

---

## Le projet : Chatbot Vocal Traiteur Dupont

Tout au long de ce module, tu travailles sur **une seule application** :
un assistant vocal pour le site web d'un traiteur.

L'utilisateur peut :
1. Envoyer un message texte ou vocal
2. Obtenir des infos (menu, horaires)
3. Passer une commande
4. Payer par CB ou régler sur place

Il y a **3 écrans** à concevoir :

| Écran | Rôle | Utilisateur |
|-------|------|-------------|
| `chat.html` | Interface principale de conversation | Client |
| `paiement` (inline) | Formulaire CB dans le chat | Client |
| `traiteur.html` | Dashboard des commandes | Employé traiteur |

---

## Planning de la journée

### Matin (3h) — Comprendre

| Durée | Module | Ce qu'on fait |
|-------|--------|---------------|
| 30 min | [01 — Analyse des besoins](./01_analyse_besoins/README.md) | Qui utilise l'app ? Pourquoi ? |
| 45 min | [02 — Lois de design](./02_lois_de_design/README.md) | Hick, Miller, Fitts : les règles qui expliquent les choix |
| 30 min | [03 — Atomic Design](./03_atomic_design/README.md) | La logique composant que tu connais déjà |
| 15 min | Pause | |
| 30 min | [04 — Wireframing avec l'IA](./04_wireframing_avec_ia/README.md) | Générer une structure en 5 min avec un prompt |

### Après-midi (3h) — Construire

| Durée | Module | Ce qu'on fait |
|-------|--------|---------------|
| 30 min | [05 — Penpot : prise en main](./05_penpot_atelier/README.md) | Créer un compte, interface, premiers composants |
| 60 min | Atelier Penpot guidé | Maquetter les 3 écrans |
| 30 min | [06 — RGAA & Accessibilité](./06_rgaa_accessibilite/README.md) | Vérifier les contrastes, les labels |
| 45 min | [07 — Handover : du design au code](./07_handover_code/README.md) | Exporter le CSS, adapter dans l'app |
| 15 min | Bilan & feedback |  |

---

## L'interface de référence

Voici les éléments clés de l'interface `etape_01` que tu vas analyser, critiquer et améliorer :

```
┌─────────────────────────────────────────────┐
│ 🍽️  Traiteur Dupont        [📋] [⚙]  [●] │  ← Header
├─────────────────────────────────────────────┤
│                                             │
│  🤖 Bonjour ! Je suis l'assistant...       │  ← Bulle bot
│                                             │
│        J'aimerais commander 3 tartes... 🎤  │  ← Bulle utilisateur
│                                             │
│  🤖 J'ai bien noté votre commande...       │  ← Bulle bot
│     Total estimé : 60.00 €                 │
│     👤 En attente : nom / prénom...        │  ← Badge état
│                                             │
├─────────────────────────────────────────────┤
│  [Réflexion...]                             │  ← Bulle animée
├─────────────────────────────────────────────┤
│  ┌──────────────────────────────┐  [▶] [🎤] │  ← Zone de saisie
│  │ Votre message...             │           │
│  └──────────────────────────────┘           │
└─────────────────────────────────────────────┘
```

---

## Comment utiliser ce module

Chaque dossier contient :
- Un `README.md` avec la théorie (15-20 min de lecture)
- Des exercices pratiques avec l'app réelle
- Des prompts IA prêts à l'emploi
- Des critères de validation ("Comment savoir si c'est bien ?")

**Tu n'as pas besoin de faire tous les exercices.** Chaque module est indépendant.
Si tu es pressé, fais au minimum : **01 → 04 → 06 → 07**.

---

## Outils à installer avant de commencer

1. **Penpot** : https://penpot.app → créer un compte gratuit (2 min)
2. **Navigateur moderne** : Chrome, Firefox ou Edge (pas IE)
3. **Extension Penpot Devtools** (optionnel mais utile pour le handover)

> 💡 **Penpot est 100% open-source.** Pas de compte payant, pas de limite de projets.
> C'est l'outil de référence open-source face à Figma.
