# 08 — Projet Penpot complet — Interface Traiteur Dupont

Ce dossier contient les **fichiers de design de référence** correspondant à l'interface de l'étape 01.

## Contenu

| Fichier | Description | Format | Dimensions |
|---------|-------------|--------|-----------|
| `chat_mobile.svg` | Interface chat (page principale) | SVG | 390 × 844 px (iPhone 14) |
| `dashboard_desktop.svg` | Tableau de bord traiteur | SVG | 1280 × 800 px |
| `design_system.svg` | Atomes, couleurs, typographie | SVG | 1440 × 960 px |

---

## Comment importer dans Penpot

### Méthode 1 — Import direct SVG (recommandée)

1. Ouvre Penpot → ton projet "Traiteur Dupont"
2. Crée une nouvelle page (ex : "Chat mobile — référence")
3. Menu **Assets** (panneau gauche) → **"Import"** → sélectionne le fichier `.svg`
4. Le design apparaît comme un groupe dans Penpot
5. Dégroupe (Ctrl+G annulé) pour accéder aux éléments individuels

### Méthode 2 — Drag & Drop

Fais glisser le fichier `.svg` directement dans la fenêtre Penpot.
Penpot l'importe automatiquement sur la page active.

### Méthode 3 — Ouvrir dans le navigateur d'abord

Les SVG s'ouvrent directement dans Chrome / Firefox.
Tu peux les consulter comme référence visuelle **sans Penpot**.
```
Ouvrir Chrome → Ctrl+O → sélectionne le fichier .svg
```

---

## Comment utiliser ces fichiers dans Penpot

### Utilisation 1 — "Calque de référence" (Tracing)

1. Importe le SVG sur ta page Penpot
2. Règle l'**opacité à 30%** (panneau droit → Opacity)
3. Verrouille le calque (clic droit → Lock)
4. Dessine par-dessus pour reproduire le design

### Utilisation 2 — Extraction des valeurs

En sélectionnant chaque élément du SVG importé dans Penpot :
- Panneau droit → tu vois les couleurs exactes, tailles, rayons
- Copie les valeurs pour les utiliser dans tes propres composants

### Utilisation 3 — Point de départ à modifier

Importe le SVG, dégroupe, modifie les couleurs ou la disposition.
Par exemple : essaie une variante avec un fond sombre (dark mode).

---

## Structure du design

### Palette de couleurs (extraite de `style.css`)

```
Primaire   #2E7D32  ████  Header, boutons, badges succès
Accent     #FF8F00  ████  Alertes, paiement sur place
Bot bg     #E8F5E9  ████  Fond bulles agent
User bg    #FFF3E0  ████  Fond bulles utilisateur
Payment    #FFFDE7  ████  Fond formulaire CB
Page bg    #F5F5F0  ████  Fond général
Texte      #212121  ████  Texte principal
Muted      #757575  ████  Texte secondaire
Erreur     #C62828  ████  Messages d'erreur
```

### Typographie

```
Police    : Segoe UI / system-ui
Titres    : 700 (Bold), 16-18px
Corps     : 400 (Regular), 14-16px
Labels    : 400 (Regular), 12px
Code/mono : monospace, 12-14px
```

### Espacement (grille 8px)

```
4px  — entre un icône et son texte
8px  — padding interne des badges
12px — gap entre avatar et bulle
16px — padding des bulles, sections
24px — padding des zones principales
```

---

## Exercices suggérés avec ces fichiers

### Exercice A — Audit comparatif (30 min)

1. Ouvre `chat_mobile.svg` dans le navigateur
2. Ouvre l'app réelle sur `http://localhost:3000`
3. Note les différences entre le design SVG et l'implémentation réelle
4. Quelles simplifications ont été faites en passant au code ?

### Exercice B — Variante dark mode (45 min)

1. Importe `chat_mobile.svg` dans Penpot
2. Duplique la page
3. Change les couleurs pour un dark mode cohérent
4. Vérifie les contrastes RGAA avec le plugin Stark

### Exercice C — Responsive desktop (45 min)

1. Le `chat_mobile.svg` est en 390px de large
2. Comment l'interface s'adapterait-elle à 1280px ?
3. Redesigne la version desktop dans Penpot
4. Compare avec `dashboard_desktop.svg` pour t'inspirer

### Exercice D — Amélioration UX (30 min)

En regardant le design, identifie **3 améliorations UX** possibles :
- Appuie-toi sur les lois du module 02 (Hick, Miller, Fitts)
- Dessine ta version améliorée dans Penpot
- Justifie chaque changement avec la loi correspondante
