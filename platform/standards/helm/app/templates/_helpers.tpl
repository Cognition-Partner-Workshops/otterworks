{{- define "platform-app.name" -}}
{{- required "app is required" .Values.app | trunc 50 | trimSuffix "-" -}}
{{- end -}}

{{- define "platform-app.labels" -}}
app: {{ include "platform-app.name" . }}
owner: {{ required "owner is required" .Values.owner | quote }}
cost-center: {{ required "costCenter is required" .Values.costCenter | quote }}
app.kubernetes.io/name: {{ include "platform-app.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "platform-app.selector" -}}
app: {{ include "platform-app.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "platform-app.container" -}}
- name: {{ include "platform-app.name" . }}
  image: "{{ required "image.repository is required" .Values.image.repository }}:{{ required "image.tag is required" .Values.image.tag }}"
  imagePullPolicy: {{ .Values.image.pullPolicy }}
  {{- with .Values.cronjob.command }}
  {{- if eq $.Values.workload "cronjob" }}
  command: {{ toJson . }}
  {{- end }}
  {{- end }}
  {{- if eq .Values.workload "web" }}
  ports:
    - name: http
      containerPort: {{ .Values.containerPort }}
  {{- end }}
  env:
    {{- range $k, $v := .Values.env }}
    - name: {{ $k }}
      value: {{ $v | quote }}
    {{- end }}
    {{- range $k, $v := .Values.secretEnv }}
    - name: {{ $k }}
      valueFrom:
        secretKeyRef:
          name: {{ $v.secret }}
          key: {{ $v.key }}
    {{- end }}
  {{- if and (eq .Values.workload "web") .Values.probes.enabled }}
  readinessProbe:
    httpGet:
      path: {{ .Values.probes.path }}
      port: {{ .Values.probes.port }}
    initialDelaySeconds: {{ .Values.probes.initialDelaySeconds }}
    periodSeconds: {{ .Values.probes.periodSeconds }}
    failureThreshold: {{ .Values.probes.failureThreshold }}
  livenessProbe:
    httpGet:
      path: {{ .Values.probes.path }}
      port: {{ .Values.probes.port }}
    initialDelaySeconds: {{ add .Values.probes.initialDelaySeconds 20 }}
    periodSeconds: {{ .Values.probes.periodSeconds }}
    failureThreshold: {{ .Values.probes.failureThreshold }}
  {{- end }}
  resources:
    {{- toYaml .Values.resources | nindent 4 }}
  securityContext:
    runAsNonRoot: true
    runAsUser: {{ .Values.securityContext.runAsUser }}
    runAsGroup: {{ .Values.securityContext.runAsGroup }}
    readOnlyRootFilesystem: true
    allowPrivilegeEscalation: false
    capabilities:
      drop: ["ALL"]
  volumeMounts:
    {{- range $i, $p := .Values.writablePaths }}
    - name: writable-{{ $i }}
      mountPath: {{ $p }}
    {{- end }}
    {{- if .Values.configFiles }}
    - name: config
      mountPath: {{ .Values.configMountPath }}
      readOnly: true
    {{- end }}
{{- end -}}

{{- define "platform-app.volumes" -}}
{{- range $i, $p := .Values.writablePaths }}
- name: writable-{{ $i }}
  emptyDir: {}
{{- end }}
{{- if .Values.configFiles }}
- name: config
  configMap:
    name: {{ include "platform-app.name" . }}-config
{{- end }}
{{- end -}}

{{- define "platform-app.podSecurity" -}}
securityContext:
  runAsNonRoot: true
  fsGroup: {{ .Values.securityContext.runAsGroup }}
  seccompProfile:
    type: RuntimeDefault
automountServiceAccountToken: false
{{- end -}}
