# Étape 16 — Loki : Les 3 piliers de l'observabilité

> **Prérequis :** avoir complété l'étape 15 (Argo Rollouts). Cluster kind actif avec Prometheus + Jaeger.
>
> **Concepts clés :**
> - Les 3 piliers : Métriques → Prometheus / Traces → Jaeger / **Logs → Loki**
> - LogQL : langage de requête pour les logs (comme PromQL mais pour les chaînes)
> - Promtail : agent DaemonSet qui collecte les logs de chaque nœud
> - Derived fields : lier un `trace_id` dans un log → Jaeger en 1 clic

---

## Pourquoi Loki ?

Imaginons un incident en production :

```
14h32 — la disponibilité chute à 85%
```

Avec les 2 premiers piliers, on sait :
1. **MÉTRIQUES** (Prometheus) : "La disponibilité a chuté à 14h32, le taux d'erreur est de 15%"
2. **TRACES** (Jaeger) : "La p95 latence a spiké. La trace `abc123` montre que c'est `rag.search` qui est lent"

Mais on ne sait pas *pourquoi*. C'est là qu'intervient le 3e pilier :

3. **LOGS** (Loki) : "Les logs de l'agent à 14h32 : `ChromaDBError: collection not found after rebuild`"

**Les 3 piliers ensemble = diagnostic complet en 2 minutes.**

---

## Loki vs Elasticsearch

| | Elasticsearch | Loki |
|---|---|---|
| Indexation | Contenu complet | Labels seulement (`app`, `namespace`, `pod`) |
| RAM | 4-16 GB | 256-512 MB |
| Coût | Élevé | Minimal |
| Requêtes | Lucene | LogQL (similaire à PromQL) |
| Intégration Grafana | via plugin | Native |

Loki n'indexe **pas** le contenu des logs — il indexe seulement les labels. La recherche dans le contenu se fait par scan (rapide car filtré par label d'abord).

---

## Architecture

```
[Pods K8s]
    │
    │ stdout/stderr
    ▼
[/var/log/pods/] ← hostPath sur chaque nœud
    │
    │ lecture continue
    ▼
[Promtail DaemonSet]  ← 1 pod par nœud (lit les fichiers de log)
    │ HTTP push
    ▼
[Loki :3100]          ← stocke + indexe les labels
    ▲
    │ LogQL
[Grafana :3001]       ← visualise + corrèle avec Prometheus/Jaeger
```

Le DaemonSet est la clé : Kubernetes garantit qu'**un pod Promtail tourne sur chaque nœud**, donc aucun log n'est perdu quel que soit le nœud qui héberge l'application.

---

## LogQL — Requêtes de base

LogQL suit la même logique que PromQL : d'abord un **sélecteur de labels** (obligatoire), puis des **filtres de contenu** (optionnels).

```logql
# Tous les logs de l'agent
{app="agent", namespace="traiteur"}

# Logs contenant "error"
{app="agent"} |= "error"

# Logs ne contenant pas "debug"
{app="agent"} != "debug"

# Regex : logs RAG ou rag
{app="agent"} |~ "(?i)rag"

# Parser les logs JSON et filtrer sur un champ
{app="agent"} | json | level="error"

# Filtrer sur le trace_id (corrélation avec Jaeger)
{app="agent"} |= "abc123def456"

# Taux d'erreur agrégé (comme PromQL — utilisable dans un panel Grafana)
sum(rate({app="agent"} |= "error" [5m]))
```

---

## Ce que fait cette étape

### Nouveaux composants

**`chart/templates/loki.yaml`** — 6 ressources Kubernetes :
- `ConfigMap loki-config` : configuration Loki (tsdb, filesystem, limits)
- `Deployment loki` : serveur Loki (grafana/loki:3.1.0)
- `Service loki` : ClusterIP sur :3100 (HTTP) et :9096 (gRPC)
- `ServiceAccount promtail-sa` + `ClusterRole` + `ClusterRoleBinding` : RBAC pour lire les métadonnées des pods
- `ConfigMap promtail-config` : configuration Promtail avec pipeline JSON + extraction `trace_id`
- `DaemonSet promtail` : collecteur de logs, monté sur `/var/log/pods`

**`chart/templates/monitoring.yaml`** (mise à jour) :
```yaml
# Dans grafana-datasources ConfigMap
- name: Loki
  type: loki
  uid: loki
  url: http://loki.traiteur.svc.cluster.local:3100
  jsonData:
    derivedFields:
      - datasourceUid: jaeger
        matcherRegex: '"trace_id":"(\w+)"'
        name: TraceID
        url: "${__value.raw}"
```

Les **derived fields** sont la killer feature : quand Grafana trouve `"trace_id":"abc123"` dans un log, il ajoute automatiquement un lien vers Jaeger. Plus besoin de copier-coller.

### Paramètres ajoutés dans values.yaml

```yaml
loki:
  enabled: true

promtail:
  enabled: true   # DaemonSet : 1 pod par nœud qui lit /var/log/pods
```

---

## Démarrage rapide

```bash
# 1. Cluster déjà actif depuis étape 13 ?
make k8s-status

# 2. Déployer avec Loki activé (valeur par défaut)
make helm-install

# 3. Vérifier que Loki collecte des logs
make loki-check

# 4. Démo complète des 3 piliers
make loki-demo

# 5. Exemples de requêtes LogQL
make loki-queries

# 6. Guide Grafana Explore
make loki-grafana
```

---

## Corrélation Logs ↔ Traces ↔ Métriques dans Grafana

C'est le point culminant des étapes 02, 10 et 16 réunies :

### Scénario "diagnostic d'incident en 2 minutes"

**Étape 1 — Métriques** (`http://localhost:3001`)
- Grafana → Dashboard → panel `conversations_total`
- On voit le spike d'erreurs à 14h32

**Étape 2 — Traces** (cliquer sur "Explore in Jaeger")
- Grafana → Explore → Datasource : Jaeger
- Service : `traiteur-agent`
- On identifie la span lente : `rag.search` avec `trace_id = abc123def456`

**Étape 3 — Logs** (cliquer sur le lien `TraceID` dans les logs)
- Grafana → Explore → Datasource : Loki
- `{app="agent"} |= "abc123def456"`
- On voit le log complet : `ChromaDBError: collection not found` avec le stack trace

**Sans Loki**, on savait qu'il y avait un problème. **Avec Loki**, on sait exactement pourquoi.

### Split View (voir 2 piliers simultanément)

Dans Grafana Explore → icône "Split" en haut à droite :
- Gauche : Prometheus — `rate(conversations_total{status="error"}[5m])`
- Droite : Loki — `{app="agent"} |= "error"` avec le même time range

---

## Pipeline Promtail en détail

```yaml
pipeline_stages:
  # 1. Parser les logs JSON émis par FastAPI/Python
  - json:
      expressions:
        level: level
        msg: msg
        trace_id: trace_id   # OTel trace ID (étape 10)

  # 2. Ajouter "level" comme label Loki (permet {level="error"})
  - labels:
      level:

  # 3. Ajouter "trace_id" comme label (permet {trace_id="abc123"})
  - labels:
      trace_id:
```

Le `trace_id` extrait devient un **label Loki**. Ainsi, la requête `{trace_id="abc123"}` retrouve instantanément tous les logs d'une même trace distribuée.

---

## CI/CD

Dans `values.ci.yaml`, Loki et Promtail sont désactivés pour économiser la RAM sur les runners GitHub Actions (budget RAM limité à 7 GB) :

```yaml
loki:
  enabled: false   # économise ~256 MB RAM

promtail:
  enabled: false
```

---

## Résumé des 17 étapes

Cette étape complète le tableau de l'observabilité :

| Étape | Quoi | Pourquoi |
|-------|------|----------|
| 02 | Prometheus + Grafana | Métriques : "combien ?" |
| 10 | Jaeger + OpenTelemetry | Traces : "pourquoi est-ce lent ?" |
| **16** | **Loki + Promtail** | **Logs : "qu'est-ce qui s'est passé ?"** |

Voir `README_parcours.md` à la racine du projet pour la vision complète des 17 étapes.
