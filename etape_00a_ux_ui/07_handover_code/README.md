# 07 — Handover : du design au code

> ⏱ **Durée :** 45 min
> 🎯 **Objectif :** Exporter les specs de design depuis Penpot et les intégrer dans l'app réelle

---

## C'est quoi le "handover" ?

Dans une équipe professionnelle, le designer remet ses specs au développeur.
Ce transfert s'appelle le **handover** (passation).

Sans handover : *"Le bouton est vert"* → le développeur choisit n'importe quel vert.
Avec handover : *"Le bouton est `#2E7D32`, police Inter Bold 14px, padding 12px 24px, rayon 22px"*.

Dans notre cas, tu es à la fois designer et développeur — mais la rigueur du handover reste utile pour ne pas tâtonner.

---

## Exporter depuis Penpot

### Inspecter un composant

1. Clique sur un composant dans Penpot
2. Panneau droit → onglet **"Inspect"** (pas "Design")
3. Tu vois : dimensions, couleurs, typographie, espacements

### Obtenir le CSS

Penpot génère du CSS correspondant à chaque élément.

**Exemple pour le bouton primaire :**

Dans Penpot Inspect, tu verras :
```css
/* Généré par Penpot */
.button-primary {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 120px;
  height: 44px;
  background: #2E7D32;
  border-radius: 22px;
  font-family: 'Segoe UI', sans-serif;
  font-weight: 700;
  font-size: 14px;
  color: #FFFFFF;
}
```

Ce CSS est directement utilisable dans `style.css`.

### Exporter les assets

- Images/icônes : clic droit → "Export" → PNG ou SVG
- Couleurs : Assets panel → copier les hex codes
- Typographie : Assets panel → voir les styles de texte

---

## De Penpot à `style.css` : la correspondance

Voici comment les décisions Penpot se traduisent dans le code de l'app.

### Variables CSS (design tokens)

```css
/* style.css — ce qui devrait être en variables */
:root {
  /* Couleurs — viennent de la palette Penpot */
  --primary:       #2E7D32;   /* Primary-500 dans Penpot */
  --primary-light: #4CAF50;   /* Primary-400 */
  --primary-bg:    #E8F5E9;   /* Primary-100 */
  --accent:        #FF8F00;   /* Accent-500 */
  --accent-bg:     #FFF3E0;   /* Accent-100 */
  --text:          #212121;   /* Gray-900 */
  --text-muted:    #757575;   /* Gray-600 */
  --border:        #EEEEEE;   /* Gray-200 */
  --bg:            #F5F5F0;   /* Gray-50 */
  --error:         #C62828;

  /* Typographie */
  --font-family: 'Segoe UI', system-ui, sans-serif;
  --font-size-sm:  12px;
  --font-size-md:  14px;
  --font-size-lg:  16px;

  /* Espacements (basés sur une grille de 8px) */
  --space-xs:  4px;
  --space-sm:  8px;
  --space-md:  16px;
  --space-lg:  24px;
  --space-xl:  32px;

  /* Formes */
  --radius-sm:  4px;
  --radius-md:  8px;
  --radius-lg:  12px;
  --radius-pill: 22px;

  /* Ombres */
  --shadow-sm: 0 1px 3px rgba(0,0,0,.08);
  --shadow-md: 0 2px 8px rgba(0,0,0,.12);
}
```

### Le bouton primaire : Penpot → CSS

**Dans Penpot :**
- Rectangle 120×44, rayon 22, fond `#2E7D32`
- Texte "Envoyer", blanc, Segoe UI, 14px, Bold

**Dans style.css :**
```css
.btn-primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-sm) var(--space-lg);  /* 8px 24px */
  min-height: 44px;                           /* Fitts : taille minimale */
  background: var(--primary);
  color: #FFFFFF;
  border: none;
  border-radius: var(--radius-pill);
  font-family: var(--font-family);
  font-size: var(--font-size-md);
  font-weight: 700;
  cursor: pointer;
  transition: background 0.2s ease;
}

.btn-primary:hover {
  background: var(--primary-light);
}

.btn-primary:focus-visible {
  outline: 3px solid var(--primary);
  outline-offset: 2px;
}

.btn-primary:disabled {
  background: #9E9E9E;
  cursor: not-allowed;
}
```

### La bulle de message bot : Penpot → CSS + HTML

**Dans Penpot :**
- Groupe : avatar (32×32, cercle gris) + bubble (max 280px, fond blanc, ombre)

**Dans style.css :**
```css
.message {
  display: flex;
  align-items: flex-start;
  gap: var(--space-sm);
  margin-bottom: var(--space-md);
}

.message.bot {
  flex-direction: row;        /* avatar à gauche */
}

.message.user {
  flex-direction: row-reverse; /* pas d'avatar, message à droite */
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;             /* ne rétrécit pas */
  font-size: 18px;
}

.bubble {
  max-width: 75%;
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  font-size: var(--font-size-lg);
  line-height: 1.5;
}

.message.bot .bubble {
  background: var(--primary-bg);
  border-top-left-radius: var(--radius-sm); /* "pointe" en haut gauche */
}

.message.user .bubble {
  background: var(--accent-bg);
  border-top-right-radius: var(--radius-sm);
}
```

---

## Exercice — Améliorer le style.css existant

### Étape 1 : Ajouter les variables manquantes

Ouvre `etape_01/ui/style.css` et vérifie que ces variables existent.
Si certaines sont codées en dur dans les composants, remplace-les par les variables.

```bash
# Cherche les couleurs codées en dur (hors variables)
grep -n "#[0-9A-Fa-f]\{6\}" style.css | grep -v "^.*--"
# Tout ce qui apparaît = couleur à transformer en variable
```

### Étape 2 : Ajouter les attributs d'accessibilité manquants

À partir de l'audit du module 06, corrige dans `index.html` :

```html
<!-- AVANT -->
<button id="sendBtn">▶</button>
<button id="micBtn" id="micLabel">🎤</button>
<input id="textInput" placeholder="Votre message..." />

<!-- APRÈS -->
<button id="sendBtn" aria-label="Envoyer le message">▶</button>

<button id="micBtn" aria-label="Démarrer l'enregistrement vocal"
        aria-pressed="false">
  🎤
  <span id="micLabel" class="sr-only">Maintenir pour parler</span>
</button>

<div class="input-wrapper">
  <label for="textInput" class="sr-only">Votre message</label>
  <input id="textInput"
         type="text"
         placeholder="Votre message..."
         autocomplete="off"
         aria-describedby="statusBar" />
</div>
```

### Étape 3 : Ajouter les aria-live manquants

```html
<!-- Status bar : annonce les changements aux lecteurs d'écran -->
<div id="statusBar"
     role="status"
     aria-live="polite"
     aria-atomic="true"></div>
```

---

## Récapitulatif : ce que le handover t'apporte

| Sans handover | Avec handover |
|---------------|---------------|
| `color: green` (quel vert ?) | `color: var(--primary)` = `#2E7D32` |
| `font-size: 13px` (trop petit RGAA) | `font-size: var(--font-size-md)` = 14px |
| `border-radius: 5px` (chiffre magique) | `border-radius: var(--radius-sm)` = 4px |
| `height: 40px` (trop petit Fitts) | `min-height: 44px` |
| Pas de `:focus-visible` | Outline 3px vert au focus |

**Le handover transforme des choix arbitraires en décisions documentées.**

---

## Bilan du module 00a

Tu as maintenant :
1. **Identifié** tes utilisateurs réels (personas)
2. **Compris** les lois qui expliquent les choix de design
3. **Décomposé** l'interface en atomes/molécules/organismes
4. **Généré** des wireframes avec l'IA en 5 minutes
5. **Maquetté** les 3 écrans dans Penpot
6. **Audité** l'accessibilité RGAA
7. **Traduit** les specs de design en code CSS/HTML

➡️ **Tu es prêt(e) pour l'étape 01 — développer l'application.**

---

## Pour aller plus loin

- RGAA officiel : https://accessibilite.numerique.gouv.fr
- WCAG 2.1 Quick Reference : https://www.w3.org/WAI/WCAG21/quickref/
- Checklist A11y : https://www.a11yproject.com/checklist/
- Penpot docs : https://help.penpot.app
- Design tokens : https://designtokens.org
- Laws of UX : https://lawsofux.com
