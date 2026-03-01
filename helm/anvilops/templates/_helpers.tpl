{{/*
Expand the name of the chart.
*/}}
{{- define "anvilops.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
Truncates to 63 characters because some Kubernetes name fields are limited.
If release name contains chart name it will be used as a full name.
*/}}
{{- define "anvilops.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "anvilops.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to all resources.
*/}}
{{- define "anvilops.labels" -}}
helm.sh/chart: {{ include "anvilops.chart" . }}
app.kubernetes.io/name: {{ include "anvilops.name" . }}
app.kubernetes.io/part-of: {{ include "anvilops.name" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
{{- end }}

{{/*
Selector labels (name + instance only, used in matchLabels).
*/}}
{{- define "anvilops.selectorLabels" -}}
app.kubernetes.io/name: {{ include "anvilops.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Component labels — full label set including component.
Usage: {{ include "anvilops.componentLabels" (list . "api") }}
*/}}
{{- define "anvilops.componentLabels" -}}
{{- $ctx := index . 0 }}
{{- $component := index . 1 }}
helm.sh/chart: {{ include "anvilops.chart" $ctx }}
app.kubernetes.io/name: {{ include "anvilops.name" $ctx }}
app.kubernetes.io/part-of: {{ include "anvilops.name" $ctx }}
app.kubernetes.io/managed-by: {{ $ctx.Release.Service }}
app.kubernetes.io/instance: {{ $ctx.Release.Name }}
app.kubernetes.io/component: {{ $component }}
{{- if $ctx.Chart.AppVersion }}
app.kubernetes.io/version: {{ $ctx.Chart.AppVersion | quote }}
{{- end }}
{{- end }}

{{/*
Component selector labels — name + instance + component (used in matchLabels).
Usage: {{ include "anvilops.componentSelectorLabels" (list . "api") }}
*/}}
{{- define "anvilops.componentSelectorLabels" -}}
{{- $ctx := index . 0 }}
{{- $component := index . 1 }}
app.kubernetes.io/name: {{ include "anvilops.name" $ctx }}
app.kubernetes.io/instance: {{ $ctx.Release.Name }}
app.kubernetes.io/component: {{ $component }}
{{- end }}

{{/*
Pod-level security context.
Reads runAsUser, runAsGroup, and fsGroup from the component's podSecurityContext values.
Usage: {{ include "anvilops.podSecurityContext" .Values.api.podSecurityContext | nindent 8 }}
*/}}
{{- define "anvilops.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: {{ .runAsUser | default 1000 }}
runAsGroup: {{ .runAsGroup | default 1000 }}
fsGroup: {{ .fsGroup | default 1000 }}
seccompProfile:
  type: RuntimeDefault
{{- end }}

{{/*
Container-level security context (applied to every app container).
*/}}
{{- define "anvilops.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop:
    - ALL
{{- end }}

{{/*
Topology spread constraints for zone and hostname spreading.
Usage: {{ include "anvilops.topologySpreadConstraints" (list . "api") }}
*/}}
{{- define "anvilops.topologySpreadConstraints" -}}
{{- $ctx := index . 0 }}
{{- $component := index . 1 }}
- maxSkew: 1
  topologyKey: topology.kubernetes.io/zone
  whenUnsatisfiable: DoNotSchedule
  labelSelector:
    matchLabels:
      {{- include "anvilops.componentSelectorLabels" (list $ctx $component) | nindent 6 }}
- maxSkew: 1
  topologyKey: kubernetes.io/hostname
  whenUnsatisfiable: DoNotSchedule
  labelSelector:
    matchLabels:
      {{- include "anvilops.componentSelectorLabels" (list $ctx $component) | nindent 6 }}
{{- end }}
