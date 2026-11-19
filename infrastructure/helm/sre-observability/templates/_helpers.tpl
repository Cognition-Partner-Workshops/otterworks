{{- define "sre-observability.rule" -}}
- alert: {{ .name }}
  expr: {{ printf "label_replace((%s), \"affected_namespace\", \"%s\", \"namespace\", \"(.*)\")" .expr (default "$1" .affectedNamespace) | quote }}
  for: {{ .duration }}
  labels:
    team: sre
    severity: {{ .severity }}
    namespace: monitoring
  annotations:
    summary: {{ .summary | quote }}
    description: {{ .description | quote }}
    runbook_url: {{ .root.Values.runbookUrl | quote }}
    affected_namespace: '{{ "{{ $labels.affected_namespace }}" }}'
{{- end -}}
