{{/*
Archive read-path env (migration/CONTRACTS.md §10.4). Rendered only when archive.store is
set, so tenants without ARCHIVE_STORE keep the golden behaviour (feature off, 404 + hint).
Credentials come from the Secret named by archive.credentialsSecret, never from values;
store=snowflake takes only SNOWFLAKE_PAT from archive.snowflake.tokenSecret (ldm-snowflake) and keeps
the tenant's PostgreSQL control plane (PG_*) when archive.postgresql.host is set.
*/}}
{{- define "archive.env" }}
{{- with .Values.archive -}}
{{- if .store -}}
- name: ARCHIVE_STORE
  value: {{ .store | quote }}
{{- if .namespace }}
- name: LDM_NAMESPACE
  value: {{ .namespace | quote }}
{{- end }}
{{- if eq .store "db2" }}
- name: DB2_HOST
  value: {{ .db2.host | quote }}
- name: DB2_PORT
  value: {{ .db2.port | quote }}
- name: DB2_DATABASE
  value: {{ .db2.database | quote }}
- name: DB2_USER
  valueFrom:
    secretKeyRef:
      name: {{ .credentialsSecret }}
      key: DB2_USER
- name: DB2_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .credentialsSecret }}
      key: DB2_PASSWORD
{{- end }}
{{- if .sourceProvider }}
- name: LDM_SOURCE_PROVIDER
  value: {{ .sourceProvider | quote }}
{{- end }}
{{- if or (eq .store "postgresql") (and (eq .store "snowflake") .postgresql.host) }}
- name: PG_HOST
  value: {{ .postgresql.host | quote }}
- name: PG_PORT
  value: {{ .postgresql.port | quote }}
- name: PG_DATABASE
  value: {{ .postgresql.database | quote }}
- name: PG_SSLMODE
  value: {{ .postgresql.sslmode | quote }}
- name: PG_USER
  valueFrom:
    secretKeyRef:
      name: {{ .credentialsSecret }}
      key: PG_USER
- name: PG_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .credentialsSecret }}
      key: PG_PASSWORD
{{- end }}
{{- if eq .store "snowflake" }}
- name: SNOWFLAKE_ACCOUNT
  value: {{ required "archive.snowflake.account is required for store=snowflake" .snowflake.account | quote }}
- name: SNOWFLAKE_USER
  value: {{ required "archive.snowflake.user is required for store=snowflake" .snowflake.user | quote }}
- name: SNOWFLAKE_ROLE
  value: {{ .snowflake.role | quote }}
- name: SNOWFLAKE_WAREHOUSE
  value: {{ .snowflake.warehouse | quote }}
- name: SNOWFLAKE_DATABASE
  value: {{ required "archive.snowflake.database is required for store=snowflake" .snowflake.database | quote }}
- name: SNOWFLAKE_PAT
  valueFrom:
    secretKeyRef:
      name: {{ .snowflake.tokenSecret }}
      key: SNOWFLAKE_PAT
{{- end }}
{{- if eq .store "azuresql" }}
- name: AZSQL_SERVER
  value: {{ .azuresql.server | quote }}
- name: AZSQL_DATABASE
  value: {{ .azuresql.database | quote }}
- name: AZSQL_AUTH
  value: {{ .azuresql.auth | quote }}
{{- if eq .azuresql.auth "sql" }}
- name: AZSQL_USER
  valueFrom:
    secretKeyRef:
      name: {{ .credentialsSecret }}
      key: AZSQL_USER
- name: AZSQL_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .credentialsSecret }}
      key: AZSQL_PASSWORD
{{- else }}
- name: AZURE_CLIENT_ID
  valueFrom:
    secretKeyRef:
      name: {{ .credentialsSecret }}
      key: AZURE_CLIENT_ID
{{- end }}
{{- end }}
{{- end }}
{{- end }}
{{- end -}}
