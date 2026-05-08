# Étape 11 — Canary Release : Déploiement Progressif

> **Prérequis :** avoir complété l'étape 07 (Kubernetes). Cluster kind actif.
>
> **Concepts clés :**
> - *"Deploy to 1% first, watch the metrics, then deploy to the world."*
> - Canary Release : déployer une nouvelle version à un petit % du trafic
> - Traffic splitting : NGINX Ingress répartit par annotations de poids
> - Progressive delivery : promotion automatique avec gates métriques
> - Rollback en 1 commande : `make canary-rollback`

---

## Problème posé

Avec le Rolling Update de l'étape 07 :

```
make k8s-rolling-update
  │
  ├── Remplace pod v1 par pod v2 (maxSurge=1)
  ├── Attend que v2 soit Ready
  └── Remplace le second pod v1 par v2

→ 100% du trafic passe à v2 en ~3 minutes
→ Si v2 a un bug subtil : 100% des utilisateurs sont impactés immédiatement
```

**Le rolling update ne distingue pas "démarrage sain" de "comportement sain".**
Un pod peut démarrer et passer les health checks, mais échouer sur des requêtes réelles.

---

## Solution : Canary Release

```
Déploiement canary :

  100% trafic
      │
      ▼
  NGINX Ingress
      │
      ├── 90% ──────────────▶ agent stable (v1, 2 replicas)
      │                         → comportement connu
      │
      └── 10% ──────────────▶ agent canary (v2, 1 replica)
                                → à surveiller

  Si métriques OK → augmenter progressivement
  Si métriques KO → rollback immédiat à 0%
```

---

## Ce qu'on ajoute dans cette étape

### Nouveaux fichiers K8s

| Fichier | Rôle |
|---|---|
| `k8s/agent-canary.yaml` | Deployment `agent-canary` (1 replica) + Service `agent-canary` |
| `k8s/ingress.yaml` | NGINX Ingress stable + ingress canary (annotation `canary-weight`) |

### Nouveaux scripts

| Script | Rôle |
|---|---|
| `scripts/canary-setup.sh` | Installe NGINX Ingress + déploie le canary à 10% |
| `scripts/canary-step.sh WEIGHT` | Change le poids + vérifie Prometheus |
| `scripts/canary-promote.sh` | Promotion automatique (10→20→40→80→100%) |
| `scripts/canary-loadgen.sh` | Charge test + compte stable vs canary |

### Modification `kind-config.yaml`

```yaml
- containerPort: 80    # NGINX Ingress HTTP
  hostPort: 8081       # → localhost:8081 = point d'entrée avec canary
- containerPort: 443
  hostPort: 8443
```

---

## Démarrage rapide

```bash
# Prérequis : cluster avec tous les services
make k8s-up

# 1. Installer NGINX Ingress + déployer canary à 10%
make canary-setup

# 2. Observer le split trafic en direct
make canary-loadgen
# → ~90 requêtes en "env: production", ~10 en "env: canary"

# 3. Promotion automatique avec vérification métriques
make canary-promote

# 4. Finaliser (remplacer l'image stable par l'image canary)
make canary-finalize

# --- OU --- rollback à tout moment
make canary-rollback
```

---

## Architecture NGINX Ingress Canary

```
localhost:8081  (hostPort → containerPort 80 du nœud kind)
      │
      ▼
NGINX Ingress Controller (DaemonSet, namespace: ingress-nginx)
      │
      │  lit les annotations sur les Ingress objects
      │
      ├── Ingress "agent-ingress" (aucune annotation canary)
      │     → path: /  →  Service "agent" (stable)
      │
      └── Ingress "agent-canary-ingress"
            annotations:
              nginx.ingress.kubernetes.io/canary: "true"
              nginx.ingress.kubernetes.io/canary-weight: "10"
            → path: /  →  Service "agent-canary"
```

**Le split est stateless** : NGINX ne track pas les sessions. Chaque requête est
indépendamment envoyée à stable (90%) ou canary (10%) selon un random.

---

## Identifier stable vs canary dans les réponses

```bash
# /health retourne {"env": "production"} (stable) ou {"env": "canary"}
curl http://localhost:8081/health
# → {"status": "ok", "service": "agent", "env": "production"}
# → {"status": "ok", "service": "agent", "env": "canary"}

# Le canary est identifié grâce à APP_ENV=canary dans agent-canary.yaml
```

---

## Changer le poids manuellement

```bash
# Passer à 20% canary
make canary-step WEIGHT=20

# Ce que fait la commande :
kubectl annotate ingress agent-canary-ingress \
    nginx.ingress.kubernetes.io/canary-weight=20 \
    --overwrite -n traiteur

# Vérification Prometheus : taux d'erreur < 5% ?
# Si OK → retourne 0 (succès)
# Si KO → retourne 1 (déclencheur rollback)
```

---

## Promotion automatique

```bash
make canary-promote
# Exécute : canary-step 10 → canary-step 20 → canary-step 40 → canary-step 80 → canary-step 100
# À chaque étape : vérifie le taux d'erreur Prometheus
# Si erreur > 5% : rollback automatique + arrêt de la promotion
```

Timeline typique :
```
T+0   : canary-step 10%  (30s) → OK
T+30  : canary-step 20%  (30s) → OK
T+60  : canary-step 40%  (30s) → OK
T+90  : canary-step 80%  (30s) → OK
T+120 : canary-step 100% → Promotion complète
T+125 : make canary-finalize → stable remplacé
```

---

## Démonstration d'un rollback automatique

```bash
# Déployer un canary volontairement cassé (Ollama inexistant → erreurs sur /api/text)
make canary-setup-broken

# Lancer la promotion automatique
make canary-promote
# → À 10% : taux d'erreur détecté > 5%
# → ROLLBACK AUTOMATIQUE à 0%
# → Le trafic revient entièrement vers le stable
```

Derrière les coulisses de `canary-setup-broken` :
```yaml
# agent-canary.yaml (version broken)
- name: OLLAMA_BASE_URL
  value: "http://nonexistent-ollama:11434"
# → /health répond 200 (ChromaDB OK)
# → /api/text retourne 500 (LLM indisponible)
# → health check passe mais le service est dégradé
# → le canary serait passé en rolling update classique !
```

C'est exactement le type de bug que le canary détecte et que le rolling update ne voit pas.

---

## Canary vs Rolling Update — Comparaison

```
Rolling Update (étape 07) :
  t=0   : 2 pods v1
  t=90s : 2 pods v2 (100% du trafic)
  → Si v2 est bugué : tous les utilisateurs affectés immédiatement
  → Rollback : kubectl rollout undo (redéploie v1, ~90s)

Canary Release (étape 11) :
  t=0   : 2 pods v1 stable + 1 pod v2 canary (10%)
  t+30s : vérification métriques → OK
  t+60s : 20% canary → vérification → OK
  ...
  t+2min: 100% canary → promotion finale
  → Si v2 est bugué : 10% des utilisateurs affectés, puis rollback 0%
  → Rollback : make canary-rollback (< 1s)
```

---

## Commandes utiles

```bash
# ── Canary workflow ────────────────────────────────────────────────────────────
make canary-setup              # NGINX Ingress + canary à 10%
make canary-setup-broken       # canary cassé (démo rollback)
make canary-status             # poids actuel + pods
make canary-loadgen            # 100 req → compte stable/canary
make canary-loadgen-continuous # observateur temps réel (Ctrl+C)
make canary-step WEIGHT=30     # passer à 30%
make canary-promote            # promotion auto (10→20→40→80→100%)
make canary-rollback           # rollback à 0% immédiat
make canary-finalize           # remplace l'image stable par canary
make canary-teardown           # supprime le canary Deployment

# ── Diagnostic ────────────────────────────────────────────────────────────────
kubectl get ingress -n traiteur                                    # état des ingress
kubectl logs -n traiteur -l app=agent-canary --tail=50            # logs canary
kubectl get events -n traiteur --sort-by='.lastTimestamp' | tail  # événements K8s
```

---

## Ce que prépare cette étape

```
Étape 12 → Sécurité : Network Policies et RBAC
  Problème : dans notre cluster, tous les pods peuvent communiquer avec tous.
             Un pod compromis peut atteindre la base de données ou l'API K8s.
  Solution : Network Policies (firewall entre pods) + RBAC (permissions minimales).
  Concepts : zero trust, principe du moindre privilège, audit logs K8s.
```
