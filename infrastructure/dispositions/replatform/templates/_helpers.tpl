{{- define "replatform.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "replatform.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "replatform.labels" -}}
app.kubernetes.io/name: {{ include "replatform.name" . | quote }}
app.kubernetes.io/instance: {{ .Release.Name | quote }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service | quote }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | quote }}
otterworks.io/disposition: "replatform"
otterworks.io/run-token: {{ required "runToken is required" .Values.runToken | quote }}
{{- end -}}

{{- define "replatform.annotations" -}}
otterworks.io/expires: {{ required "expires is required" .Values.expires | quote }}
otterworks.io/disposition-evidence: {{ required "dispositionEvidence is required" .Values.dispositionEvidence | quote }}
{{- end -}}

{{- define "replatform.validate" -}}
{{- if not (regexMatch "^[a-z][a-z0-9-]*-[0-9]{8}-[a-z0-9]{2}$" .Values.runToken) -}}
{{- fail "runToken must match <prefix>-YYYYMMDD-xx" -}}
{{- end -}}
{{- if ne .Values.service.type "ClusterIP" -}}
{{- fail "service.type must be ClusterIP; use the shared ingress-nginx LoadBalancer" -}}
{{- end -}}
{{- end -}}

{{- define "replatform.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "replatform.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}
