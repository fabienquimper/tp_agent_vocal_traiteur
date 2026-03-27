# 06 — RGAA & Accessibilité : le seul point design qui est technique

> ⏱ **Durée :** 30 min
> 🎯 **Objectif :** Vérifier que l'interface passe les critères RGAA niveau AA — mesurables et obligatoires

---

## Pourquoi l'accessibilité intéresse les développeurs

L'accessibilité n'est pas une option esthétique. C'est :
- **Légalement obligatoire** pour les services publics (RGAA = loi française)
- **Indispensable pour le RNCP** : le jury évalue si l'interface est accessible
- **Pragmatiquement bénéfique** : ce qui aide les malvoyants aide aussi quelqu'un en plein soleil ou fatigué

> *"L'accessibilité n'est pas une fonctionnalité — c'est la qualité de base."*

**Le RGAA** (Référentiel Général d'Amélioration de l'Accessibilité) est la déclinaison française des WCAG 2.1. Il définit 4 principes :
- **P**erceptible (l'info est visible/audible)
- **U**tilisable (navigable au clavier, sans temps limité)
- **C**ompréhensible (langage clair, erreurs explicites)
- **R**obuste (compatible avec les lecteurs d'écran)

---

## Critère 1 — Contraste des couleurs (WCAG 1.4.3)

### La règle

Pour du texte normal (< 18pt) : **ratio minimum 4.5:1**
Pour du texte grand (≥ 18pt ou 14pt gras) : **ratio minimum 3:1**
Pour les composants UI (boutons, inputs) : **ratio minimum 3:1**

### Comment calculer

Formule : `(L1 + 0.05) / (L2 + 0.05)` où L1 > L2 sont les luminances relatives.

**Outils :**
- WebAIM Contrast Checker : https://webaim.org/resources/contrastchecker/
- Plugin Penpot : "Stark" ou "A11y - Color Contrast Checker"
- DevTools Chrome : Inspector → Accessibility → Color

### Audit de la palette actuelle

```
Texte blanc (#FFFFFF) sur fond vert primary (#2E7D32) :
  Luminance #FFFFFF = 1.0
  Luminance #2E7D32 = 0.075 (environ)
  Ratio = (1.0 + 0.05) / (0.075 + 0.05) = 8.4:1  ✅ (≥ 4.5)

Texte muted (#757575) sur fond blanc (#FFFFFF) :
  Ratio ≈ 4.6:1  ✅ (juste au-dessus du seuil)

Texte muted (#757575) sur fond gris page (#F5F5F0) :
  À calculer → probablement < 4.5:1 ⚠️

Badge intent : texte #2E7D32 sur fond #E8F5E9 :
  Ratio ≈ 3.0:1  ⚠️ (ok pour grand texte, limite pour petit texte)

Texte erreur #C62828 sur fond blanc :
  Ratio ≈ 5.9:1  ✅
```

### Exercice — Audit complet

Calcule le ratio de contraste pour ces combinaisons de l'app :

| Élément | Texte | Fond | Ratio calculé | Conforme ? |
|---------|-------|------|--------------|------------|
| Placeholder input | `#9E9E9E` | `#FFFFFF` | ? | ? |
| Hint paiement | `#757575` | `#FFFDE7` | ? | ? |
| Texte bulle user | `#212121` | `#FFF8E1` | ? | ? |
| Label badge total | `#2E7D32` | `#E8F5E9` | ? | ? |
| Texte sur bouton payer | `#FFFFFF` | `#2E7D32` | ? | ? |

---

## Critère 2 — Labels des formulaires (WCAG 1.3.1)

### La règle

**Chaque champ de formulaire doit avoir un label explicite** associé programmatiquement.

❌ **Interdit :**
```html
<!-- Le placeholder disparaît quand l'utilisateur tape → l'utilisateur oublie quoi saisir -->
<input type="text" placeholder="Votre message" />

<!-- Pas de label → lecteur d'écran dit "champ de saisie" sans contexte -->
<input type="text" />
```

✅ **Correct :**
```html
<!-- Label visible associé par for/id -->
<label for="message">Votre message</label>
<input id="message" type="text" />

<!-- Ou label imbriqué -->
<label>
  Numéro de carte
  <input type="text" inputmode="numeric" autocomplete="cc-number" />
</label>

<!-- Ou aria-label si label visuel impossible -->
<input type="text" aria-label="Message à envoyer" placeholder="Tapez ici..." />
```

### Audit de l'interface existante

Ouvre `etape_01/ui/index.html` et trouve :

```javascript
// Exercice : cherche ces éléments
document.querySelectorAll('input, button, textarea').forEach(el => {
  const hasLabel = el.labels?.length > 0 || el.getAttribute('aria-label');
  console.log(el.outerHTML, hasLabel ? '✅' : '❌ SANS LABEL');
});
```

**Problèmes probables à trouver :**
- `<input id="textInput" placeholder="Votre message...">` → a-t-il un `<label>` ?
- `<button id="sendBtn">▶</button>` → l'icône ▶ n'est pas un label accessible
- `<button id="micBtn">🎤</button>` → un emoji n'est pas un label

**Solutions :**
```html
<!-- Bouton avec texte visible -->
<button id="sendBtn" aria-label="Envoyer le message">▶</button>

<!-- Ou texte masqué visuellement mais présent pour les lecteurs d'écran -->
<button id="micBtn">
  🎤
  <span class="sr-only">Démarrer l'enregistrement vocal</span>
</button>
```

```css
/* Classe "screen-reader only" : visible par les SR, invisible à l'écran */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
```

---

## Critère 3 — Navigation au clavier (WCAG 2.1.1)

### La règle

Toute l'interface doit être utilisable **sans souris**, avec Tab, Entrée et Espace.

### Test pratique

1. Ouvre l'app dans Chrome
2. Débranche la souris
3. Appuie sur Tab → est-ce que le focus passe logiquement de haut en bas ?
4. Sur le formulaire CB → Tab navigue-t-il entre les champs dans le bon ordre ?
5. Sur un bouton → Entrée l'active-t-il ?

**Problème fréquent : focus invisible**

```css
/* Ne JAMAIS faire ça : */
* { outline: none; }  /* ← Supprime l'indicateur de focus = interface inutilisable au clavier */

/* Faire ça à la place : */
:focus-visible {
  outline: 3px solid #2E7D32;
  outline-offset: 2px;
  border-radius: 4px;
}
```

---

## Critère 4 — Textes alternatifs (WCAG 1.1.1)

### La règle

Toute image ou icône porteuse de sens doit avoir un équivalent texte.

**Dans notre app :**

```html
<!-- Logo : doit avoir un alt -->
<img src="logo.png" alt="Traiteur Dupont" />

<!-- Icône décorative : alt vide pour que le SR l'ignore -->
<span aria-hidden="true">🍽️</span>

<!-- Avatar bot : rôle et label -->
<div class="avatar" role="img" aria-label="Assistant virtuel">🤖</div>

<!-- Indicateur statut : état annoncé -->
<span class="status-dot online"
      role="status"
      aria-label="Service en ligne"></span>
```

---

## Critère 5 — Messages d'état (WCAG 4.1.3)

Les messages importants (succès, erreur, chargement) doivent être annoncés aux lecteurs d'écran **sans déplacer le focus**.

```html
<!-- Zone de statut : les changements sont annoncés automatiquement -->
<div id="statusBar"
     role="status"
     aria-live="polite"
     aria-atomic="true">
  Transcription en cours...
</div>

<!-- Erreur : annonce immédiate (assertive) -->
<div role="alert" aria-live="assertive">
  Erreur de connexion. Veuillez réessayer.
</div>

<!-- Résultat de paiement : annonce douce (polite) -->
<div role="status" aria-live="polite">
  Paiement accepté. Commande n°A1B2C3D4 confirmée.
</div>
```

---

## La checklist rapide (à imprimer)

```
CHECKLIST RGAA — Interface Chatbot Traiteur
Version : niveau AA (minimum requis)

CONTRASTES
[ ] Texte normal sur fond : ratio ≥ 4.5:1
[ ] Texte grand (≥ 18pt) : ratio ≥ 3:1
[ ] Boutons, inputs, icônes : ratio ≥ 3:1

FORMULAIRES
[ ] Chaque input a un <label> associé (for/id ou imbriqué)
[ ] Pas de placeholder comme seul label
[ ] Les messages d'erreur identifient le champ fautif
[ ] Les champs obligatoires sont indiqués (pas seulement par la couleur)

NAVIGATION CLAVIER
[ ] Tab passe sur tous les éléments interactifs
[ ] Ordre de tabulation logique (haut → bas, gauche → droite)
[ ] Focus visible (pas de outline: none sans remplacement)
[ ] Pas de "piège clavier" (impossible de sortir d'un composant)

LECTEURS D'ÉCRAN
[ ] Les boutons icônes ont un aria-label
[ ] Les images décoratives ont alt="" ou aria-hidden="true"
[ ] Les messages de statut utilisent role="status" ou aria-live
[ ] Les erreurs utilisent role="alert"

COULEUR
[ ] L'information n'est pas transmise uniquement par la couleur
  (ex: les badges de paiement ont aussi du texte, pas seulement une couleur)
```

---

## Outils de test automatique

Ces outils détectent ~30-40% des problèmes d'accessibilité automatiquement :

- **axe DevTools** (extension Chrome) : audit en 1 clic
- **Lighthouse** (intégré Chrome DevTools) : rapport complet
- **WAVE** (extension) : visualisation des problèmes sur la page
- **Stark** (plugin Penpot/Figma) : contraste et simulation daltonisme

> ⚠️ Les 60-70% restants ne peuvent être détectés que par test humain
> (navigation clavier, test avec lecteur d'écran NVDA/VoiceOver).

➡️ **Suite :** [07 — Handover : du design au code](../07_handover_code/README.md)
