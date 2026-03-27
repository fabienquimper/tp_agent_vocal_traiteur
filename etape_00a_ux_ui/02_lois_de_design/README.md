# 02 — Les lois de design : les règles qui expliquent les choix

> ⏱ **Durée :** 45 min
> 🎯 **Objectif :** Comprendre pourquoi certains designs "fonctionnent" — et le mesurer

---

## Introduction : le design n'est pas du goût, c'est de la cognition

Quand on dit "c'est bien fait", on décrit en réalité un cerveau qui n'est pas mis en difficulté.
Les lois de design sont des résultats de recherche en psychologie cognitive.
Elles s'appliquent à toute interface, web, mobile ou vocale.

---

## Loi 1 — La loi de Hick : le paradoxe du choix

### Principe
> *"Le temps pour prendre une décision augmente avec le nombre et la complexité des options."*

**En pratique :** plus tu proposes d'options, plus l'utilisateur hésite et abandonne.

### Formule
```
Temps de décision ≈ log₂(N + 1)
où N = nombre d'options
```

2 options → rapide. 8 options → 3x plus lent. 20 options → pénible.

### Dans notre app

Interface de chat : l'utilisateur a exactement **2 actions** en bas :
- Écrire et envoyer (texte)
- Parler (micro)

On ne lui propose pas 5 options. On n'a pas mis de bouton "Joindre un fichier", "Changer de langue", "Effacer l'historique".

**Audit :**

```
Page chat — options proposées à l'utilisateur :
✅ Envoyer un texte     (1 option)
✅ Enregistrer un vocal (1 option)
✅ Répondre à l'agent   (1 option implicite)
                    Total : 3 → rapide à décider
```

**Ce qu'on évite :**
```
❌ Ce qui aurait été une mauvaise UX :
[Envoyer] [Photo] [Fichier] [Répondre] [Annuler] [Aide] [Changer de langue]
          ↑ L'utilisateur est paralysé par le choix
```

### Exercice
Ouvre la page `/traiteur.html`. Compte le nombre d'actions possibles.
Est-ce conforme à la loi de Hick pour Marc qui scanne rapidement ses commandes ?

---

## Loi 2 — La loi de Miller : 7 ± 2

### Principe
> *"La mémoire à court terme humaine peut retenir entre 5 et 9 éléments simultanément."*

**En pratique :** afficher plus de 7 éléments dans une liste ou un menu fatigue le cerveau.

### Dans notre app

Le tableau des commandes (`/traiteur.html`) :

```
Colonnes affichées : Réf. | Date | Client | Téléphone | Articles | Total | Paiement | Type
                     1      2       3          4          5          6        7         8
```

8 colonnes — c'est à la limite. On pourrait regrouper "Réf. + Date" ou masquer "Type" par défaut.

**Ce qu'on évite :**
- Ne pas afficher 15 colonnes d'un coup
- Ne pas mettre 200 commandes sans pagination
- Ne pas proposer 12 filtres différents

### Exercice — Chunking

Le chunking (regroupement) est la technique pour dépasser la limite de 7.
Au lieu de mémoriser "0666056274", on retient "06 66 05 62 74" (5 groupes de 2).

Dans le formulaire CB inline du chat :
```
Mauvais : 4242424242424242
Bon :     4242 4242 4242 4242
```

Comment est implémenté ce chunking dans `app.js` ? (indice : cherche `replace(/(.{4})/g`)

---

## Loi 3 — La loi de Fitts : la taille des zones cliquables

### Principe
> *"Le temps pour atteindre une cible est proportionnel à la distance et inversement proportionnel à sa taille."*

**En pratique :** les boutons importants doivent être **grands** et **proches du pouce**.

### Formule (simplifiée)
```
Difficulté ∝ Distance / Taille_cible
```
Un bouton petit et loin → difficile à atteindre.
Un bouton grand et proche → rapide et naturel.

### La zone du pouce sur mobile

```
iPhone 14 — zone d'atteinte naturelle du pouce droit :

┌─────────────────┐
│   ✗ difficile   │  ← coin haut gauche (pouce ne va pas là)
│                 │
│   ~ moyen       │  ← milieu de l'écran
│                 │
│   ✓ facile      │  ← coin bas droit (zone naturelle du pouce)
└─────────────────┘
```

### Dans notre app

Le bouton micro est en **bas à droite** — zone naturelle du pouce.
Si on l'avait mis en haut à gauche, Sophie dans le métro galèrerait à l'atteindre.

Taille minimale recommandée pour une zone tactile : **44 × 44 px** (Apple HIG) / **48 × 48 dp** (Material Design).

**Audit du bouton micro dans `style.css` :**

```css
/* Cherche ces valeurs dans style.css */
.btn-mic {
  width: ?px;    /* Est-ce ≥ 44px ? */
  height: ?px;   /* Est-ce ≥ 44px ? */
}
```

### Exercice
Ouvre `style.css` et mesure la taille des éléments interactifs.
Quels boutons sont trop petits selon Fitts ?

---

## Loi 4 — La loi de Proximité (Gestalt)

### Principe
> *"Les éléments visuellement proches semblent liés."*

**En pratique :** groupe ce qui appartient ensemble. Sépare ce qui n'est pas lié.

### Dans notre app

```
Dans une bulle de message bot :

  ┌─────────────────────────────────┐
  │ Merci Fabien ! Votre commande   │
  │ s'élève à 60.00 €.              │
  │                                 │
  │ [Total estimé : 60.00 €]   ←── │ Badge proche du texte → lié au message
  │                                 │
  │ ▶ Écouter                  ←── │ Proche du message → appartient à ce message
  │                                 │
  │ 👤 En attente : nom...     ←── │ En bas du bloc → statut du processus
  └─────────────────────────────────┘

Puis, séparé visuellement :

  ┌──────────────── FORMULAIRE CB ──┐
  │ 💳 Paiement par carte bancaire  │  ← Bloc visuel distinct (jaune, bordure)
  │ ...                             │
  └─────────────────────────────────┘
```

Le formulaire CB est intentionnellement dans un bloc à part (fond jaune, bordure orange) pour signaler qu'il s'agit d'une action critique différente de la conversation.

---

## Résumé : le tableau de bord des lois

| Loi | Question à poser | Seuil critique |
|-----|-----------------|----------------|
| **Hick** | Combien d'options sur cette écran ? | > 5 → simplifier |
| **Miller** | Combien d'éléments dans cette liste ? | > 7 → paginer ou grouper |
| **Fitts** | Les boutons sont-ils assez grands ? | < 44px → trop petit |
| **Proximité** | Est-ce que ce qui est lié est visuellement proche ? | Sinon → regrouper |

---

## Exercice final — Audit de l'interface existante

Remplis ce tableau pour les 3 pages de l'app :

| Page | Loi | Observation | Note /5 | Amélioration proposée |
|------|-----|-------------|---------|----------------------|
| `index.html` | Hick | Nb d'options : ? | ? | ... |
| `index.html` | Fitts | Taille bouton micro : ?px | ? | ... |
| `traiteur.html` | Miller | Nb de colonnes : ? | ? | ... |
| `traiteur.html` | Proximité | Infos groupées logiquement ? | ? | ... |

---

## Pour aller plus loin

- **Laws of UX** : https://lawsofux.com (site de référence, illustré)
- **Nielsen Norman Group** : https://nngroup.com (recherches UX sérieuses)
- **Material Design** : https://m3.material.io/foundations (référence Google)

➡️ **Suite :** [03 — Atomic Design](../03_atomic_design/README.md)
