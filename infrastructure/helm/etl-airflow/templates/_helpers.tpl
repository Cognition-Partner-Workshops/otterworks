{{- define "etl-airflow.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
platform/environment: {{ .Values.global.environment | default "dev" }}
platform/team: otterworks
{{- end -}}

{{- define "etl-airflow.image" -}}
"{{ .Values.image.repository }}:{{ required "image.tag must be set (ECR uses IMMUTABLE tags)" .Values.image.tag }}"
{{- end -}}

{{- define "etl-airflow.env" -}}
env:
  {{- range $key, $value := .Values.env }}
  - name: {{ $key }}
    value: {{ $value | quote }}
  {{- end }}
envFrom:
  - configMapRef:
      name: {{ .Release.Name }}-config
      optional: true
  - secretRef:
      name: {{ .Release.Name }}-secrets
      optional: true
{{- end -}}

{{- define "etl-airflow.containerSecurityContext" -}}
securityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop: ["ALL"]
{{- end -}}
