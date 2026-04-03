# ─────────────────────────────────────────────────────────────────────────────
# STT Router — Nginx reverse proxy pour Blue/Green deployment
# ─────────────────────────────────────────────────────────────────────────────
# Ce conteneur est l'élément central du Blue/Green deployment.
#
# Son rôle : être le seul point d'entrée pour les requêtes STT.
# L'agent parle toujours à stt-router:8001.
# Le router décide vers qui proxier : stt-blue (Whisper base) ou stt-green (Whisper small).
#
# Le "switch" se fait en remplaçant /etc/nginx/upstream.conf puis en faisant
# `nginx -s reload`. Nginx finit d'abord toutes les connexions en cours (graceful),
# puis les nouvelles connexions vont vers le nouvel upstream.
# → Zéro downtime, aucune requête perdue.
#
# C'est exactement le même mécanisme utilisé en production par des outils
# comme Argo Rollouts, Flagger ou HAProxy pour les blue/green deployments.
# ─────────────────────────────────────────────────────────────────────────────

FROM nginx:1.27-alpine

# Les deux configurations d'upstream (préinstallées dans l'image)
COPY upstream.blue.conf /etc/nginx/upstreams/blue.conf
COPY upstream.green.conf /etc/nginx/upstreams/green.conf

# Configuration principale nginx
COPY nginx.conf /etc/nginx/nginx.conf

# Blue est actif par défaut (c'est le "modèle en production" avant le déploiement)
RUN cp /etc/nginx/upstreams/blue.conf /etc/nginx/upstream.conf

EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:8001/health || exit 1
