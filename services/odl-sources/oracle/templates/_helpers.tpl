{{- define "odl.loader" -}}
metadata:
  labels:
    run_token: {{ .root.Values.runToken | quote }}
    odl/loader: "true"
    ldm/db2-client: "true"
spec:
  restartPolicy: Never
  serviceAccountName: odl-source-loader
  containers:
    - name: load
      image: {{ .root.Values.seedImage | quote }}
      imagePullPolicy: Always
      {{- if eq .source "crm" }}
      command: [python, /app/scripts/seed.py, --crm]
      {{- else }}
      command: [python, -m, odl_sources.load, {{ .source }}]
      {{- end }}
      envFrom:
        - configMapRef: {name: odl-source-settings}
        {{- if eq .source "crm" }}
        - secretRef: {name: odl-postgres}
        {{- else if eq .source "oracle" }}
        - secretRef: {name: odl-oracle}
        {{- end }}
      env:
        - {name: ORACLE_DSN, value: "oracle:1521/FREEPDB1"}
      resources:
        requests: {cpu: 100m, memory: 128Mi}
        limits: {cpu: "1", memory: 512Mi}
{{- end -}}
