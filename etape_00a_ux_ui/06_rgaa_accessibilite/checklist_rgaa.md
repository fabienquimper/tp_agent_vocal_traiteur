# Checklist RGAA — Interface Chatbot Traiteur

À remplir pendant l'audit de l'interface `etape_01`.
Niveau cible : **WCAG 2.1 AA** (= RGAA niveau double A).

---

## 1. Contrastes

| # | Critère | Élément à tester | Ratio attendu | Ratio mesuré | Conforme |
|---|---------|-----------------|---------------|-------------|---------|
| 1.1 | Texte corps | Texte gris `#757575` / fond blanc | ≥ 4.5:1 | ? | ☐ |
| 1.2 | Texte muted | `#757575` / fond page `#F5F5F0` | ≥ 4.5:1 | ? | ☐ |
| 1.3 | Placeholder | `#9E9E9E` / fond blanc | ≥ 4.5:1 | ? | ☐ |
| 1.4 | Badge intent | `#2E7D32` / `#E8F5E9` | ≥ 4.5:1 | ? | ☐ |
| 1.5 | Bouton payer | `#FFFFFF` / `#2E7D32` | ≥ 4.5:1 | ? | ☐ |
| 1.6 | Erreur paiement | `#C62828` / fond blanc | ≥ 4.5:1 | ? | ☐ |
| 1.7 | Texte header | `#FFFFFF` / `#2E7D32` | ≥ 4.5:1 | ? | ☐ |

**Outil :** https://webaim.org/resources/contrastchecker/

---

## 2. Alternatives textuelles

| # | Critère | Élément | Conforme |
|---|---------|---------|---------|
| 2.1 | Bouton envoi `▶` | A un `aria-label` | ☐ |
| 2.2 | Bouton micro `🎤` | A un `aria-label` | ☐ |
| 2.3 | Avatar bot `🤖` | `aria-hidden="true"` ou `aria-label` | ☐ |
| 2.4 | Logo `🍽️` | `aria-hidden="true"` (décoratif) | ☐ |
| 2.5 | Statut en ligne `●` | `aria-label="Service en ligne"` | ☐ |

---

## 3. Labels de formulaires

| # | Critère | Élément | Conforme |
|---|---------|---------|---------|
| 3.1 | Champ message | A un `<label>` ou `aria-label` | ☐ |
| 3.2 | Numéro de carte CB | A un `<label>` | ☐ |
| 3.3 | Expiry CB | A un `<label>` | ☐ |
| 3.4 | CVV CB | A un `<label>` + description aide | ☐ |
| 3.5 | Champs obligatoires | Marqués (pas seulement par couleur) | ☐ |

---

## 4. Messages dynamiques

| # | Critère | Élément | Conforme |
|---|---------|---------|---------|
| 4.1 | Barre de statut | `role="status"` + `aria-live="polite"` | ☐ |
| 4.2 | Erreur paiement | `role="alert"` ou `aria-live="assertive"` | ☐ |
| 4.3 | Confirmation commande | Annoncé aux lecteurs d'écran | ☐ |
| 4.4 | Nouveaux messages chat | `aria-live` sur la zone de chat | ☐ |

---

## 5. Navigation clavier

| # | Critère | Test | Conforme |
|---|---------|------|---------|
| 5.1 | Focus visible | Tab → indicateur visible sur chaque élément | ☐ |
| 5.2 | Ordre logique | Tab suit l'ordre visuel haut→bas | ☐ |
| 5.3 | Bouton envoi | Entrée sur le champ texte = envoi | ☐ |
| 5.4 | Formulaire CB | Tab navigue entre les 3 champs CB | ☐ |
| 5.5 | Bouton payer | Espace ou Entrée active le paiement | ☐ |
| 5.6 | Pas de piège | Escape ou Tab peut sortir du formulaire CB | ☐ |

---

## 6. Couleur seule

| # | Critère | Élément | Conforme |
|---|---------|---------|---------|
| 6.1 | Badges paiement | Texte + couleur (pas couleur seule) | ☐ |
| 6.2 | Erreur champ CB | Texte d'erreur (pas seulement bordure rouge) | ☐ |
| 6.3 | Statut service | Texte + indicateur coloré | ☐ |

---

## 7. Redimensionnement texte

| # | Critère | Test | Conforme |
|---|---------|------|---------|
| 7.1 | Zoom 200% | Le texte reste lisible, pas de chevauchement | ☐ |
| 7.2 | Taille min | Aucun texte < 12px (idéal ≥ 14px) | ☐ |
| 7.3 | Retour à la ligne | Les longs textes se découpent (pas overflow hidden) | ☐ |

---

## Score et prochaines étapes

```
Score : __ / 27 critères conformes

< 20 : Corrections prioritaires avant livraison
20-25 : Bon niveau, quelques ajustements
> 25 : Interface accessible (RGAA AA)
```

### Corrections prioritaires (si < 20)

1. Ajouter `aria-label` sur les boutons icônes (impact fort, rapide)
2. Corriger les contrastes hors seuil (changer la couleur du texte muted)
3. Associer les labels aux inputs (for/id ou aria-label)
4. Ajouter `role="status"` sur la barre de statut

### Commande pour un audit automatique rapide

```bash
# Depuis la racine du projet, si l'app tourne sur localhost:3000 :
npx axe-cli http://localhost:3000 --include main
npx axe-cli http://localhost:3000/traiteur.html --include main
```
