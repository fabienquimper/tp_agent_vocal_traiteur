# 05 — Penpot : atelier pratique

> ⏱ **Durée :** 90 min (30 min prise en main + 60 min atelier guidé)
> 🎯 **Objectif :** Maquetter les 3 écrans de l'app dans Penpot, en utilisant des composants réutilisables

---

## Pourquoi Penpot et pas Figma ?

| Critère | Figma | Penpot |
|---------|-------|--------|
| Prix | Gratuit limité / payant | 100% gratuit |
| Hébergement | Cloud propriétaire (US) | Open-source, auto-hébergeable |
| Export code | Limité en gratuit | CSS/SVG inclus |
| Données | Chez Figma (RGPD ?) | Chez vous |
| Format | Propriétaire | Standard SVG |
| Idéal pour | Startups, agences | Formation, open-source, sobriété |

> **Pour un cursus de formation publique et un usage pédagogique : Penpot est le bon choix.**

---

## Mise en place (15 min)

### 1. Créer un compte

1. Aller sur https://penpot.app
2. Cliquer "Get started for free"
3. Créer un compte (email ou GitHub)
4. Créer un projet : **"Traiteur Dupont — Design System"**

### 2. Créer les 3 pages

Dans Penpot, un projet peut avoir plusieurs "pages" (comme des onglets) :
- Page 1 : **Design System** (atomes + molécules)
- Page 2 : **Chat Client**
- Page 3 : **Dashboard Traiteur**

### 3. Configurer les frames

Pour chaque maquette, crée un **Frame** aux bonnes dimensions :

| Écran | Dimensions | Pourquoi |
|-------|-----------|---------|
| Chat Client | 390 × 844 px | iPhone 14 (mobile-first) |
| Dashboard Traiteur | 1280 × 800 px | Écran bureau standard |

---

## Les variables de design (Design Tokens)

Avant de dessiner quoi que ce soit, configure les couleurs de l'app.
Dans Penpot, c'est dans **Assets → Colors**.

### Palette du projet

```
Primaire (vert)
  Primary-700   #1B5E20   ← vert très foncé (texte sur fond vert)
  Primary-500   #2E7D32   ← vert principal (boutons, header)
  Primary-100   #E8F5E9   ← vert très clair (fonds, badges)

Accent (orange)
  Accent-700    #E65100   ← orange foncé (hover boutons accent)
  Accent-500    #FF8F00   ← orange principal
  Accent-100    #FFF3E0   ← orange très clair (alertes, sur place)

Neutre
  Gray-900      #212121   ← texte principal
  Gray-600      #757575   ← texte secondaire, labels
  Gray-200      #EEEEEE   ← bordures, séparateurs
  Gray-50       #F5F5F0   ← fond de page

Sémantique
  Success       #2E7D32   ← = Primary-500
  Warning       #FF8F00   ← = Accent-500
  Error         #C62828   ← rouge erreur
  Info          #1565C0   ← bleu info

Paiement (spécifique au projet)
  Card-bg       #FFFDE7   ← fond formulaire CB
  Card-border   #FFE082   ← bordure formulaire CB
```

Crée chaque couleur dans Penpot **avant** de commencer à dessiner.

---

## Exercice guidé 1 — La page Design System (30 min)

Cette page est ton **kit de composants**. On part des atomes.

### Atome 1 — Le bouton primaire

1. Crée un rectangle : 120 × 44 px, rayon 22 px (pill shape)
2. Couleur de fond : `Primary-500` (`#2E7D32`)
3. Ajoute un texte centré : "Envoyer", blanc, Segoe UI ou Inter, 14px, Bold
4. **Créer un composant** (Ctrl+K sur la sélection)
5. Nommer le composant : `Button/Primary`

### Atome 2 — Le bouton micro

1. Cercle 52 × 52 px
2. Fond : `Gray-200` par défaut
3. Icône 🎤 centré (ou un rectangle de 24×24 px pour symboliser l'icône)
4. Variante "recording" : fond `Error` (`#C62828`) + animation ring (cercle extérieur)
5. Composant : `Button/Mic`

### Atome 3 — Badge d'intention

1. Rectangle à coins arrondis, 12 px de rayon
2. Fond : `Primary-100` (`#E8F5E9`)
3. Texte : "📋 Informations", `Primary-500`, 12px
4. Padding interne : 4px × 12px
5. Composant : `Badge/Intent`

### Atome 4 — Badge total commande

1. Même forme que le badge d'intention
2. Fond : `Primary-100`
3. Texte : "Total estimé : 60,00 €", `Primary-500`, 12px, **Bold**
4. Composant : `Badge/Total`

### Molécule — Bulle de message bot

1. Rectangle blanc avec ombre légère, rayon 12 px (coin haut-gauche à 0)
2. Maximum 280 px de large
3. Ajouter à l'intérieur : texte + Badge/Intent + Badge/Total
4. À gauche : l'avatar 🤖 (cercle gris 32×32)
5. Composant : `Message/Bot`

---

## Exercice guidé 2 — La page Chat Client (30 min)

Frame 390 × 844 px (iPhone 14).

### Structure (de haut en bas)

```
┌─ Header ─ hauteur fixe 56 px ──────────────────────────────────────┐
│  🍽️ Traiteur Dupont                          [📋] [⚙] [●]        │
└───────────────────────────────────────────────────────────────────┘

┌─ Chat Area ─ flex: 1, overflow: scroll ────────────────────────────┐
│                                                                     │
│  [Message/Bot] Bonjour ! Je suis l'assistant...                    │
│                                                                     │
│      [Message/User] J'aimerais commander 3 tartes... [🎤]          │
│                                                                     │
│  [Message/Bot thinking] ●●● Analyse de la demande...               │
│                                                                     │
└───────────────────────────────────────────────────────────────────┘

┌─ Status Bar ─ hauteur 20 px ───────────────────────────────────────┐
│  Transcription en cours...                                          │
└───────────────────────────────────────────────────────────────────┘

┌─ Input Area ─ hauteur fixe 72 px ──────────────────────────────────┐
│  [Input text ─ flex: 1]                          [▶] [🎤 52px]    │
└───────────────────────────────────────────────────────────────────┘
```

**Astuce Penpot :** utilise les **grilles de layout** (Grid/Flex) pour que les éléments s'adaptent automatiquement.

### Points critiques Fitts à vérifier

- Bouton micro : ≥ 52 × 52 px ✓
- Bouton envoi : ≥ 44 × 44 px ✓
- Zone cliquable du bouton = zone visuelle + padding ✓

---

## Exercice guidé 3 — La page Dashboard Traiteur (30 min)

Frame 1280 × 800 px.

### Structure

```
┌─ Header ─ 64 px ───────────────────────────────────────────────────┐
│  🍽️ Traiteur Dupont — Tableau de bord          [💬] [⚙]          │
└───────────────────────────────────────────────────────────────────┘

┌─ Stats Grid ─ 4 colonnes ──────────────────────────────────────────┐
│  [Card: 12 commandes]  [Card: 7 CB]  [Card: 5 sur place]  [Card: 580€]│
└───────────────────────────────────────────────────────────────────┘

┌─ Toolbar ──────────────────────────────────────────────────────────┐
│  📋 Commandes du jour                          [↻ Actualiser]      │
└───────────────────────────────────────────────────────────────────┘

┌─ Table ────────────────────────────────────────────────────────────┐
│ Réf.  │ Date  │ Client      │ Articles    │ Total │ Paiement │ Type │
│ ─────────────────────────────────────────────────────────────────  │
│ A1B2  │ 26/03 │ Fabien M.   │ 3x Bœuf... │ 144€  │ [Payé CB]│ Simp.│
│ C3D4  │ 26/03 │ Sophie R.   │ 2x Quiche  │ 44€   │ [Sur pl.]│ Simp.│
└───────────────────────────────────────────────────────────────────┘
```

### Les badges de statut paiement

Crée 4 variantes du composant `Badge/Payment` :

| Variante | Fond | Texte | Signification |
|----------|------|-------|---------------|
| `paid-cb` | `#E8F5E9` | `#2E7D32` | ✅ Payé par CB |
| `on-site` | `#FFF3E0` | `#E65100` | 🕐 Règlement sur place |
| `refused` | `#FFEBEE` | `#C62828` | ❌ CB refusé → sur place |
| `pending` | `#F3E5F5` | `#6A1B9A` | ⏳ En attente |

---

## Vérification finale dans Penpot

Avant de passer au handover, vérifie :

- [ ] Toutes les couleurs utilisées viennent de la palette (pas de `#FFFFFF` direct, mais `White`)
- [ ] Tous les boutons ont une taille ≥ 44 × 44 px
- [ ] Les textes ont une taille ≥ 14 px (16 px recommandé pour le corps)
- [ ] Les zones de saisie ont des labels visibles (pas juste des placeholders)
- [ ] Les composants sont nommés logiquement (`Button/Primary`, `Badge/Intent`)

---

## Astuce bonus — Penpot Community

Penpot a une galerie de composants open-source :
https://penpot.app/libraries-templates

Tu peux importer des librairies comme **Material Design 3** ou **WCAG Checker**
directement dans ton projet pour gagner du temps.

➡️ **Suite :** [06 — RGAA & Accessibilité](../06_rgaa_accessibilite/README.md)
