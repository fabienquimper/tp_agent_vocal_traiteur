# 01 — Analyse des besoins : pour qui on conçoit ?

> ⏱ **Durée :** 30 min
> 🎯 **Objectif :** Définir les utilisateurs réels avant de dessiner quoi que ce soit

---

## Le principe fondamental

> *"On ne conçoit pas pour soi. On conçoit pour quelqu'un d'autre."*

C'est le piège le plus commun en développement :
**coder une interface pour quelqu'un qui ressemble à soi** (développeur, 25 ans, bac+5, habitué aux apps).

En réalité, ton utilisateur est peut-être :
- Une secrétaire de 55 ans qui utilise un smartphone pour la première fois
- Un chef cuisinier qui commande depuis un téléphone gras à 14h entre deux services
- Un stagiaire qui passe 50 commandes par jour et veut aller vite

---

## Les 3 questions à poser AVANT de dessiner

### Question 1 — Qui utilise l'app ?
Pas "le client" en général. Un vrai profil :
- Quel âge ?
- Quel niveau tech ?
- Dans quel contexte ? (bureau, mobile, stress, calme)
- Quel objectif PRÉCIS dans cette session ?

### Question 2 — Quel est leur problème actuel ?
Sans ton app, que font-ils ? Appel téléphonique ? Email ? Papier ?
Ce qu'ils font aujourd'hui, c'est la **baseline** à battre.

### Question 3 — Comment saura-t-on que c'est réussi ?
Définir une métrique :
- "La commande prend moins de 2 minutes"
- "L'utilisateur ne pose pas de question à un humain"
- "Le taux d'abandon du formulaire est < 10%"

---

## Le Persona : un outil simple, pas du tout réservé aux designers

Un persona, c'est une **fiche de personnage** fictif mais réaliste.

### Persona 1 — Sophie, la cliente pressée

```
┌─────────────────────────────────────────────────────────┐
│  👤 Sophie Renard, 42 ans                               │
│  Organisatrice d'événements d'entreprise à Dijon        │
├─────────────────────────────────────────────────────────┤
│  CONTEXTE                                               │
│  Commande des plateaux repas pour des réunions.         │
│  Souvent dans les transports ou entre deux réunions.    │
│  Utilise son iPhone pour tout.                          │
├─────────────────────────────────────────────────────────┤
│  OBJECTIF PRINCIPAL                                     │
│  Passer une commande en moins de 3 minutes              │
│  sans avoir à rappeler pour confirmer.                  │
├─────────────────────────────────────────────────────────┤
│  FRUSTRATIONS ACTUELLES                                 │
│  • "Je dois appeler, tomber sur le répondeur, rappeler" │
│  • "Je ne sais jamais si la commande est bien enreg."   │
│  • "Les formulaires en ligne sont trop longs"           │
├─────────────────────────────────────────────────────────┤
│  CE QU'ELLE DIT                                         │
│  "Je veux juste confirmer que c'est bien noté et        │
│   avoir un numéro de commande."                         │
└─────────────────────────────────────────────────────────┘
```

### Persona 2 — Marc, l'employé traiteur

```
┌─────────────────────────────────────────────────────────┐
│  👤 Marc Dupont, 38 ans                                 │
│  Gérant du Traiteur Dupont, Dijon                       │
├─────────────────────────────────────────────────────────┤
│  CONTEXTE                                               │
│  Consulte les commandes le matin avant le service.      │
│  Sur ordinateur de bureau, cuisine ou comptoir.         │
│  Pas de formation informatique particulière.            │
├─────────────────────────────────────────────────────────┤
│  OBJECTIF PRINCIPAL                                     │
│  Voir d'un coup d'œil les commandes du jour             │
│  et savoir ce qui a été payé.                           │
├─────────────────────────────────────────────────────────┤
│  FRUSTRATIONS ACTUELLES                                 │
│  • "Je dois fouiller dans les emails"                   │
│  • "Je ne sais pas si le client a payé en avance"       │
│  • "Les tableaux Excel manuels, c'est chronophage"      │
├─────────────────────────────────────────────────────────┤
│  CE QU'IL DIT                                           │
│  "Je veux voir : nom, ce qu'il a commandé,              │
│   si c'est payé, et le total. C'est tout."              │
└─────────────────────────────────────────────────────────┘
```

---

## Exercice 1 — Lire les personas dans le code

Ouvre `etape_01/ui/index.html` et `etape_01/ui/traiteur.html`.

Pour chaque interface, réponds :
1. À quel persona correspond cette page ?
2. Quelles décisions de design servent **directement** le besoin du persona ?
3. Qu'est-ce qui pourrait être amélioré pour mieux servir ce persona ?

### Exemple de réponse attendue

Pour la page chat (`index.html`) :
- ✅ Le bouton micro est grand et accessible → Sophie l'utilise en mobilité
- ✅ Le badge "Total estimé" est immédiatement visible → Sophie sait combien ça coûte
- ⚠️ Pas de numéro de confirmation visible pendant la saisie → frustration potentielle
- ❓ La bulle "Réflexion..." (15s d'attente) — est-ce acceptable pour Sophie pressée ?

---

## Exercice 2 — Le scénario d'usage

Raconte l'histoire de Sophie qui utilise l'app. Sois précis sur les étapes :

```
Sophie est dans le métro à 11h30.
Elle ouvre le site sur son iPhone.
Elle voit [...]
Elle clique/dit [...]
L'app répond [...]
Elle est satisfaite/frustrée parce que [...]
```

Ce scénario s'appelle un **user journey**. Il révèle les points de friction avant de coder.

---

## Exercice 3 — Les questions à poser au "client" fictif

Si Marc (le traiteur) était devant toi, quelles 3 questions lui poserais-tu
**avant** de concevoir le dashboard `/traiteur.html` ?

Exemples de bonnes questions :
- "Dans quel ordre regardes-tu les colonnes du tableau ?"
- "Qu'est-ce qui t'indiquerait qu'une commande est urgente ?"
- "Est-ce que tu imprimes parfois le tableau ?"

---

## Ce qu'on a appris

- Un persona = un utilisateur réel, pas un utilisateur imaginaire
- Les frustrations actuelles = les fonctionnalités prioritaires à résoudre
- On juge une interface par rapport au **besoin du persona**, pas à son esthétique

➡️ **Suite :** [02 — Les lois de design](../02_lois_de_design/README.md)
