{{- define "odl-target.labels" -}}
app.kubernetes.io/name: operational-data-layer-mongo
app.kubernetes.io/instance: {{ .Release.Name }}
run_token: {{ .Values.runToken | quote }}
{{- end -}}
