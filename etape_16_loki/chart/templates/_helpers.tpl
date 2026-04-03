{{/*
_helpers.tpl — Fonctions réutilisables (partials Helm)
──────────────────────────────────────────────────────
Les "named templates" (define/include) évitent la répétition dans les templates.
Ils sont définis dans des fichiers préfixés par "_" (non rendus comme manifestes K8s).

Usage dans un template :
  {{ include "traiteur.labels" . }}
  {{ include "traiteur.selectorLabels" "agent" }}
*/}}

{{/*
Nom du chart (utilisé dans les labels)
*/}}
{{- define "traiteur.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Labels communs appliqués à TOUTES les ressources
→ permettent de retrouver toutes les ressources d'un release Helm
  kubectl get all -l helm.sh/chart=traiteur-1.0.0
*/}}
{{- define "traiteur.labels" -}}
helm.sh/chart: {{ include "traiteur.chart" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}

{{/*
Labels de sélection pour un service donné (stable entre les upgrades)
Argument : nom du service (ex: "agent", "ollama", "stt-blue")
→ utilisés dans selector.matchLabels ET podSelector
*/}}
{{- define "traiteur.selectorLabels" -}}
app: {{ . }}
{{- end }}

{{/*
Environnement courant (depuis values.agent.env.appEnv)
Utilisé pour afficher des messages différents selon l'env
*/}}
{{- define "traiteur.environment" -}}
{{- .Values.agent.env.appEnv | default "production" }}
{{- end }}

{{/*
URL Ollama — mock en CI, réelle sinon
Si ollama.enabled=false et qu'on est en CI, pointer vers le mock
*/}}
{{- define "traiteur.ollamaUrl" -}}
{{- if .Values.ollama.enabled -}}
http://ollama:11434
{{- else -}}
http://ollama:11434
{{- end -}}
{{- end }}

{{/*
Image complète d'un service : repository:tag
Exemples :
  {{ include "traiteur.image" .Values.agent.image }}  → "traiteur-agent:latest"
  {{ include "traiteur.image" .Values.ollama.image }}  → "ollama/ollama:latest"
*/}}
{{- define "traiteur.image" -}}
{{- printf "%s:%s" .repository (.tag | default "latest") }}
{{- end }}
