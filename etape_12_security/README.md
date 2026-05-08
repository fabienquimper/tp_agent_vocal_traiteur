# Étape 12 — Sécurité : Network Policies et RBAC

> **Prérequis :** avoir complété l'étape 07 (Kubernetes). Cluster kind actif.
>
> **Concepts clés :**
> - *"Never trust, always verify." — Zero Trust*
> - Network Policies : firewall entre pods K8s (ingress/egress par labels)
> - RBAC : qui peut faire quoi sur quelles ressources K8s API
> - ServiceAccount : identité d'un pod vis-à-vis de l'API K8s
> - Principe du moindre privilège : seulement les permissions strictement nécessaires

---

## Problème posé

Sans politiques de sécurité, notre cluster est un réseau plat :

```
Cluster K8s (sans NetworkPolicy) :

  [agent] ────────────────────────────────▶ [ollama]   ✓ normal
  [agent] ────────────────────────────────▶ [stt]      ✓ normal
  [ollama] ───────────────────────────────▶ [agent]    ← pas de raison métier
  [agent] ────────────────────────────────▶ [grafana]  ← pas de raison métier
  [pod-compromis] ─────────────────────────▶ TOUT      ← danger !

  Chaque pod peut appeler l'API K8s avec le ServiceAccount "default"
  → Si ce SA a des droits trop larges : escalade de privilèges possible
```

**Scénario d'attaque réel :**
1. Vulnérabilité dans le modèle Ollama → attaquant prend le contrôle du pod
2. Depuis Ollama, l'attaquant appelle `http://agent:8000/api/orders` → lit les commandes clients
3. Avec le ServiceAccount default, il appelle l'API K8s et liste les Secrets
4. Il trouve le kubeconfig ou les tokens d'accès au registry → escalade

---

## Solution : Zero Trust

```
Principe : TOUT est bloqué par défaut, RIEN n'est autorisé sans règle explicite.

  NetworkPolicy "default-deny-all" → bloque tout
  NetworkPolicy "allow-agent"      → autorise exactement les flux nécessaires
  RBAC "agent-role"               → donne au pod agent UNIQUEMENT get/list ConfigMaps
```

---

## Ce qu'on ajoute dans cette étape

### Nouveaux fichiers

| Fichier | Rôle |
|---|---|
| `k8s/security/network-policies.yaml` | 8 NetworkPolicies (default-deny + allow explicites) |
| `k8s/rbac/rbac.yaml` | ServiceAccounts + Roles + Bindings |
| `scripts/security-setup.sh` | Installation kube-network-policies + application des policies |
| `scripts/security-check.sh` | Tests : flux autorisés ✓ et bloqués ✗ depuis les pods |

### Modification `k8s/agent.yaml`

```yaml
spec:
  serviceAccountName: agent-sa   # ← SA minimal (uniquement get/list ConfigMaps)
  containers: ...
```

---

## Démarrage rapide

```bash
# Prérequis : cluster kind avec services déployés
make k8s-up

# Appliquer les politiques de sécurité
make security-setup

# Vérifier que les flux sont corrects
make security-check

# Auditer les permissions du ServiceAccount agent
make rbac-audit
```

---

## Network Policies — Architecture

```
namespace: traiteur
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  [nginx-ingress] ──:8000──▶ [agent] ──:11434──▶ [ollama]        │
│                                     ──:8001───▶ [stt]           │
│                                     ──:8002───▶ [tts]           │
│                                     ──:4317───▶ [jaeger]        │
│                                                                  │
│  [prometheus] ──:8000──▶ [agent]    (scrape métriques)          │
│  [grafana] ──:9090──▶ [prometheus]                               │
│                                                                  │
│  ✗ [ollama] ──X──▶ [agent]          (bloqué)                    │
│  ✗ [agent] ──X──▶ [grafana]         (bloqué)                    │
│  ✗ [agent] ──X──▶ internet          (bloqué)                    │
│                                                                  │
│  Tous ──:53──▶ kube-dns             (DNS résolution — autorisé) │
└──────────────────────────────────────────────────────────────────┘
```

---

## RBAC — Qui peut faire quoi

```
ServiceAccount "agent-sa" (utilisé par les pods agent) :
  ✓ configmaps → get, list    (lire les données RAG)
  ✗ secrets    → (rien)       (pas de raison d'accéder aux secrets)
  ✗ pods       → (rien)       (pas de raison de gérer les pods)
  ✗ deployments→ (rien)       (pas de raison de modifier les déploiements)

ServiceAccount "prometheus-sa" (utilisé par Prometheus) :
  ✓ pods, endpoints, services → get, list, watch  (service discovery)
  ✓ /metrics (nonResourceURL) → get               (scrape métriques système)
  ✗ secrets, configmaps       → (rien)
```

### Vérification avec kubectl auth can-i

```bash
# Depuis votre terminal (impersonate le ServiceAccount agent-sa)
kubectl auth can-i get configmaps \
    --as system:serviceaccount:traiteur:agent-sa -n traiteur
# → yes  (attendu)

kubectl auth can-i get secrets \
    --as system:serviceaccount:traiteur:agent-sa -n traiteur
# → no   (attendu — moindre privilège)

kubectl auth can-i create deployments \
    --as system:serviceaccount:traiteur:agent-sa -n traiteur
# → no   (attendu)
```

---

## Note sur NetworkPolicy et kind

```
Problème : kind utilise "kindnet" comme CNI (Container Network Interface).
           kindnet ne supporte pas nativement les NetworkPolicies.

Solution  : kube-network-policies (kubernetes-sigs) est un controller userspace
            qui implémente les NetworkPolicies au-dessus de kindnet.
            Installation : kubectl apply -f (fait par security-setup.sh)

Production: Calico, Cilium, Antrea → support natif des NetworkPolicies
            + fonctionnalités avancées (L7 policies, Hubble observability, etc.)

                kindnet (kind)     Calico/Cilium (prod)
  NetworkPolicy  via controller    natif (eBPF)
  Performance    userspace (~ms)   kernel (< µs)
  Observability  basique           Hubble, Retina...
  L7 policies    non               oui (Cilium)
```

---

## Démonstrations

### 1. Vérifier que default-deny bloque tout

```bash
# AVANT d'appliquer les NetworkPolicies (tester depuis un pod)
kubectl exec -n traiteur deployment/agent -- \
    python3 -c "import urllib.request; urllib.request.urlopen('http://grafana:3000', timeout=3)"
# → connexion établie (pas de policy)

# APRÈS make security-setup
kubectl exec -n traiteur deployment/agent -- \
    python3 -c "import urllib.request; urllib.request.urlopen('http://grafana:3000', timeout=3)"
# → timeout (bloqué par default-deny + pas de règle allow agent→grafana)
```

### 2. Vérifier qu'Ollama ne peut pas appeler l'agent

```bash
kubectl exec -n traiteur deployment/ollama -- \
    curl -sf --max-time 3 http://agent:8000/health || echo "BLOQUÉ ✓"
```

### 3. Vérifier les permissions RBAC depuis l'intérieur d'un pod

```bash
kubectl exec -n traiteur deployment/agent -- \
    kubectl auth can-i get configmaps --namespace traiteur
# → yes  (SA agent-sa peut lire les ConfigMaps)

kubectl exec -n traiteur deployment/agent -- \
    kubectl auth can-i list pods --namespace traiteur
# → no   (SA agent-sa ne peut pas lister les pods)
```

### 4. Audit complet

```bash
make rbac-audit
# Affiche les permissions du SA agent-sa pour chaque ressource K8s
```

---

## Commandes utiles

```bash
# ── Sécurité ──────────────────────────────────────────────────────────────────
make security-setup    # installer kube-network-policies + appliquer policies
make security-check    # tester tous les flux (autorisés et bloqués)
make rbac-audit        # auditer les permissions du ServiceAccount agent

# ── Inspection ────────────────────────────────────────────────────────────────
kubectl get networkpolicy -n traiteur                         # liste des policies
kubectl describe networkpolicy default-deny-all -n traiteur   # détails
kubectl get serviceaccount -n traiteur                         # liste des SAs
kubectl get rolebinding -n traiteur                            # liste des bindings

# ── Debug NetworkPolicy ───────────────────────────────────────────────────────
kubectl get events -n traiteur --sort-by='.lastTimestamp'     # événements récents
kubectl logs -n kube-system -l app=kube-network-policies      # logs du controller
```
