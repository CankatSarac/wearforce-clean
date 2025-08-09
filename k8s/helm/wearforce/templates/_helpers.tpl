{{/*
Expand the name of the chart.
*/}}
{{- define "wearforce.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "wearforce.fullname" -}}
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
{{- define "wearforce.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "wearforce.labels" -}}
helm.sh/chart: {{ include "wearforce.chart" . }}
{{ include "wearforce.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/environment: {{ .Values.global.environment }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "wearforce.selectorLabels" -}}
app.kubernetes.io/name: {{ include "wearforce.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Service labels
*/}}
{{- define "wearforce.serviceLabels" -}}
{{ include "wearforce.labels" . }}
app.kubernetes.io/component: {{ .component | default "service" }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "wearforce.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "wearforce.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Generate the image name
*/}}
{{- define "wearforce.image" -}}
{{- $registry := .Values.global.image.registry | default "ghcr.io" }}
{{- $repository := .Values.global.image.repository | default "wearforce" }}
{{- $service := .service }}
{{- $tag := .Values.global.image.tag | default .Chart.AppVersion }}
{{- printf "%s/%s/%s:%s" $registry $repository $service $tag }}
{{- end }}

{{/*
Generate common environment variables
*/}}
{{- define "wearforce.commonEnv" -}}
- name: ENVIRONMENT
  value: {{ .Values.global.environment | quote }}
- name: SERVICE_NAME
  value: {{ .service | quote }}
- name: NAMESPACE
  valueFrom:
    fieldRef:
      fieldPath: metadata.namespace
- name: POD_NAME
  valueFrom:
    fieldRef:
      fieldPath: metadata.name
- name: POD_IP
  valueFrom:
    fieldRef:
      fieldPath: status.podIP
- name: NODE_NAME
  valueFrom:
    fieldRef:
      fieldPath: spec.nodeName
- name: LOG_LEVEL
  value: {{ .Values.global.logLevel | default "info" | quote }}
{{- if .Values.global.serviceMesh.enabled }}
- name: SERVICE_MESH_ENABLED
  value: "true"
- name: SERVICE_MESH_TYPE
  value: {{ .Values.global.serviceMesh.type | quote }}
{{- end }}
{{- if .Values.global.tracing.enabled }}
- name: TRACING_ENABLED
  value: "true"
- name: JAEGER_AGENT_HOST
  value: {{ .Values.global.tracing.jaegerAgent.host | default "jaeger-agent" | quote }}
- name: JAEGER_AGENT_PORT
  value: {{ .Values.global.tracing.jaegerAgent.port | default "6831" | quote }}
{{- end }}
{{- if .Values.global.metrics.enabled }}
- name: METRICS_ENABLED
  value: "true"
- name: METRICS_PORT
  value: {{ .Values.global.metrics.port | default "9090" | quote }}
{{- end }}
{{- end }}

{{/*
Generate database connection environment
*/}}
{{- define "wearforce.databaseEnv" -}}
{{- if .Values.infrastructure.postgresql.enabled }}
- name: DATABASE_HOST
  value: {{ printf "%s-postgresql" (include "wearforce.fullname" .) | quote }}
- name: DATABASE_PORT
  value: "5432"
- name: DATABASE_NAME
  value: {{ .Values.infrastructure.postgresql.auth.database | quote }}
- name: DATABASE_USERNAME
  value: {{ .Values.infrastructure.postgresql.auth.username | quote }}
- name: DATABASE_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ printf "%s-postgresql" (include "wearforce.fullname" .) }}
      key: password
- name: DATABASE_URL
  value: "postgresql://$(DATABASE_USERNAME):$(DATABASE_PASSWORD)@$(DATABASE_HOST):$(DATABASE_PORT)/$(DATABASE_NAME)"
{{- end }}
{{- end }}

{{/*
Generate Redis connection environment
*/}}
{{- define "wearforce.redisEnv" -}}
{{- if .Values.infrastructure.redis.enabled }}
- name: REDIS_HOST
  value: {{ printf "%s-redis-master" (include "wearforce.fullname" .) | quote }}
- name: REDIS_PORT
  value: "6379"
{{- if .Values.infrastructure.redis.auth.enabled }}
- name: REDIS_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ printf "%s-redis" (include "wearforce.fullname" .) }}
      key: redis-password
- name: REDIS_URL
  value: "redis://:$(REDIS_PASSWORD)@$(REDIS_HOST):$(REDIS_PORT)/0"
{{- else }}
- name: REDIS_URL
  value: "redis://$(REDIS_HOST):$(REDIS_PORT)/0"
{{- end }}
{{- end }}
{{- end }}

{{/*
Generate Qdrant connection environment
*/}}
{{- define "wearforce.qdrantEnv" -}}
{{- if .Values.infrastructure.qdrant.enabled }}
- name: QDRANT_HOST
  value: {{ printf "%s-qdrant" (include "wearforce.fullname" .) | quote }}
- name: QDRANT_PORT
  value: "6333"
- name: QDRANT_URL
  value: "http://$(QDRANT_HOST):$(QDRANT_PORT)"
{{- end }}
{{- end }}

{{/*
Generate resource limits and requests
*/}}
{{- define "wearforce.resources" -}}
{{- if .resources }}
resources:
  {{- if .resources.limits }}
  limits:
    {{- if .resources.limits.cpu }}
    cpu: {{ .resources.limits.cpu | quote }}
    {{- end }}
    {{- if .resources.limits.memory }}
    memory: {{ .resources.limits.memory | quote }}
    {{- end }}
    {{- if .resources.limits.nvidia\.com/gpu }}
    nvidia.com/gpu: {{ index .resources.limits "nvidia.com/gpu" | quote }}
    {{- end }}
  {{- end }}
  {{- if .resources.requests }}
  requests:
    {{- if .resources.requests.cpu }}
    cpu: {{ .resources.requests.cpu | quote }}
    {{- end }}
    {{- if .resources.requests.memory }}
    memory: {{ .resources.requests.memory | quote }}
    {{- end }}
    {{- if .resources.requests.nvidia\.com/gpu }}
    nvidia.com/gpu: {{ index .resources.requests "nvidia.com/gpu" | quote }}
    {{- end }}
  {{- end }}
{{- end }}
{{- end }}

{{/*
Generate security context
*/}}
{{- define "wearforce.securityContext" -}}
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop:
      - ALL
  seccompProfile:
    type: RuntimeDefault
{{- end }}

{{/*
Generate pod security context
*/}}
{{- define "wearforce.podSecurityContext" -}}
securityContext:
  fsGroup: 1000
  fsGroupChangePolicy: "OnRootMismatch"
  seccompProfile:
    type: RuntimeDefault
{{- end }}

{{/*
Generate node affinity rules
*/}}
{{- define "wearforce.nodeAffinity" -}}
{{- if .nodeAffinity }}
nodeAffinity:
  {{- toYaml .nodeAffinity | nindent 2 }}
{{- else }}
nodeAffinity:
  preferredDuringSchedulingIgnoredDuringExecution:
  - weight: 100
    preference:
      matchExpressions:
      - key: node.kubernetes.io/instance-type
        operator: In
        values:
        - m5.large
        - m5.xlarge
        - m5.2xlarge
        - c5.large
        - c5.xlarge
        - c5.2xlarge
{{- end }}
{{- end }}

{{/*
Generate pod anti-affinity rules
*/}}
{{- define "wearforce.podAntiAffinity" -}}
podAntiAffinity:
  preferredDuringSchedulingIgnoredDuringExecution:
  - weight: 100
    podAffinityTerm:
      labelSelector:
        matchExpressions:
        - key: app.kubernetes.io/name
          operator: In
          values:
          - {{ include "wearforce.name" . }}
        - key: app.kubernetes.io/component
          operator: In
          values:
          - {{ .component }}
      topologyKey: kubernetes.io/hostname
{{- end }}

{{/*
Generate volume mounts for temporary storage
*/}}
{{- define "wearforce.tempVolumeMounts" -}}
- name: tmp
  mountPath: /tmp
- name: var-cache
  mountPath: /var/cache
- name: var-log
  mountPath: /var/log
{{- end }}

{{/*
Generate volumes for temporary storage
*/}}
{{- define "wearforce.tempVolumes" -}}
- name: tmp
  emptyDir: {}
- name: var-cache
  emptyDir: {}
- name: var-log
  emptyDir: {}
{{- end }}

{{/*
Generate service monitor labels
*/}}
{{- define "wearforce.serviceMonitorLabels" -}}
{{ include "wearforce.labels" . }}
release: prometheus-operator
{{- end }}

{{/*
Generate deployment strategy
*/}}
{{- define "wearforce.deploymentStrategy" -}}
{{- if eq .Values.global.deployment.strategy "canary" }}
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0
{{- else if eq .Values.global.deployment.strategy "blue-green" }}
strategy:
  type: Recreate
{{- else }}
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 25%
    maxUnavailable: 25%
{{- end }}
{{- end }}

{{/*
Generate health check probes
*/}}
{{- define "wearforce.healthProbes" -}}
{{- if .healthcheck.enabled }}
livenessProbe:
  httpGet:
    path: {{ .healthcheck.path | default "/health" }}
    port: http
    scheme: HTTP
  initialDelaySeconds: {{ .healthcheck.initialDelaySeconds | default 30 }}
  periodSeconds: {{ .healthcheck.periodSeconds | default 10 }}
  timeoutSeconds: {{ .healthcheck.timeoutSeconds | default 5 }}
  failureThreshold: {{ .healthcheck.failureThreshold | default 3 }}
  successThreshold: 1
readinessProbe:
  httpGet:
    path: {{ .healthcheck.readinessPath | default .healthcheck.path | default "/ready" }}
    port: http
    scheme: HTTP
  initialDelaySeconds: {{ .healthcheck.readinessInitialDelaySeconds | default 5 }}
  periodSeconds: {{ .healthcheck.readinessPeriodSeconds | default 5 }}
  timeoutSeconds: {{ .healthcheck.readinessTimeoutSeconds | default 3 }}
  failureThreshold: {{ .healthcheck.readinessFailureThreshold | default 3 }}
  successThreshold: 1
startupProbe:
  httpGet:
    path: {{ .healthcheck.startupPath | default .healthcheck.path | default "/health" }}
    port: http
    scheme: HTTP
  initialDelaySeconds: {{ .healthcheck.startupInitialDelaySeconds | default 10 }}
  periodSeconds: {{ .healthcheck.startupPeriodSeconds | default 10 }}
  timeoutSeconds: {{ .healthcheck.startupTimeoutSeconds | default 5 }}
  failureThreshold: {{ .healthcheck.startupFailureThreshold | default 30 }}
  successThreshold: 1
{{- end }}
{{- end }}