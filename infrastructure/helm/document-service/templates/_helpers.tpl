{{/*
Namespace the incident rules and dashboard are scoped to.
*/}}
{{- define "document-service.monitoringNamespace" -}}
{{- .Values.monitoring.namespaceLabel | default .Release.Namespace -}}
{{- end -}}

{{/*
Scope a PromQL expression to one namespace by adding a namespace matcher to
every otterworks_*, http_* and ALERTS selector. Selectors with braces get the
matcher prepended; bare metric names get a new brace block.
Usage: include "document-service.scopeExpr" (dict "expr" $expr "namespace" $ns)
*/}}
{{- define "document-service.scopeExpr" -}}
{{- $m := printf "namespace=%q" .namespace -}}
{{- $expr := regexReplaceAll `\b((?:http|otterworks)_[a-z0-9_]+|job:[a-z0-9_:]+|ALERTS)\{` .expr (printf "${1}{%s, " $m) -}}
{{- regexReplaceAll `\b((?:http|otterworks)_[a-z0-9_]+|job:[a-z0-9_:]+)\b([^{a-z0-9_:]|$)` $expr (printf "${1}{%s}${2}" $m) -}}
{{- end -}}

{{/*
UID of the per-namespace incident dashboard. Grafana UIDs are limited to 40
chars, so longer ones keep a readable prefix plus a hash of the full UID.
*/}}
{{- define "document-service.dashboardUid" -}}
{{- include "document-service.grafanaUid" (.Values.monitoring.dashboard.uid | default (printf "ir-%s" .Release.Namespace)) -}}
{{- end -}}

{{/*
UID of the per-namespace KYC upload latency dashboard (monitoring.kycUploadSlo).
*/}}
{{- define "document-service.kycDashboardUid" -}}
{{- include "document-service.grafanaUid" (.Values.monitoring.kycUploadSlo.dashboardUid | default (printf "kyc-%s" .Release.Namespace)) -}}
{{- end -}}

{{- define "document-service.grafanaUid" -}}
{{- $uid := . -}}
{{- if gt (len $uid) 40 -}}
{{- $uid = printf "%s-%s" ($uid | trunc 31 | trimSuffix "-") ($uid | sha256sum | trunc 8) -}}
{{- end -}}
{{- $uid -}}
{{- end -}}

{{/*
Rule groups of a files/*.yml rule file with every selector scoped to the
monitoring namespace, a static namespace label on each rule and the dashboard /
traces links rewritten to monitoring.links. Takes (dict "root" $ "file" path
"dashboardUid" uid) and returns YAML.
*/}}
{{- define "document-service.scopedRuleGroups" -}}
{{- $root := .root -}}
{{- $dashboardUid := .dashboardUid -}}
{{- $ns := include "document-service.monitoringNamespace" $root -}}
{{- $links := $root.Values.monitoring.links -}}
{{- $src := $root.Files.Get .file | fromYaml -}}
{{- $groups := list -}}
{{- range $group := $src.groups -}}
{{- $rules := list -}}
{{- range $rule := $group.rules -}}
{{- $r := deepCopy $rule -}}
{{- $_ := set $r "expr" (include "document-service.scopeExpr" (dict "expr" $rule.expr "namespace" $ns)) -}}
{{- $labels := mergeOverwrite (deepCopy ($rule.labels | default dict)) ($root.Values.monitoring.rules.extraLabels | default dict) (dict "namespace" $ns) -}}
{{- $_ := set $r "labels" $labels -}}
{{- $ann := deepCopy ($rule.annotations | default dict) -}}
{{- if and $links.grafana (hasKey $ann "dashboard_url") -}}
{{- $_ := set $ann "dashboard_url" (printf "%s/d/%s" (trimSuffix "/" $links.grafana) $dashboardUid) -}}
{{- end -}}
{{- if and $links.jaeger (hasKey $ann "traces_url") -}}
{{- $_ := set $ann "traces_url" (replace "http://localhost:16686" (trimSuffix "/" $links.jaeger) $ann.traces_url) -}}
{{- end -}}
{{- $_ := set $r "annotations" $ann -}}
{{- $rules = append $rules $r -}}
{{- end -}}
{{- $g := deepCopy $group -}}
{{- $_ := set $g "rules" $rules -}}
{{- $groups = append $groups $g -}}
{{- end -}}
{{- toYaml $groups -}}
{{- end -}}

{{/*
A files/*.json Grafana dashboard with the given uid, the namespace in its
title, every query scoped to the monitoring namespace and Jaeger links
rewritten to monitoring.links. Takes (dict "root" $ "file" path "uid" uid)
and returns pretty JSON.
*/}}
{{- define "document-service.scopedDashboard" -}}
{{- $root := .root -}}
{{- $ns := include "document-service.monitoringNamespace" $root -}}
{{- $links := $root.Values.monitoring.links -}}
{{- $ds := dict "type" "prometheus" "uid" $root.Values.monitoring.dashboard.datasourceUid -}}
{{- $d := $root.Files.Get .file | fromJson -}}
{{- $_ := set $d "uid" .uid -}}
{{- $_ := set $d "title" (printf "%s (%s)" $d.title $ns) -}}
{{- range $a := $d.annotations.list -}}
{{- if hasKey $a "expr" -}}
{{- $_ := set $a "datasource" $ds -}}
{{- $_ := set $a "expr" (include "document-service.scopeExpr" (dict "expr" $a.expr "namespace" $ns)) -}}
{{- end -}}
{{- end -}}
{{- range $p := $d.panels -}}
{{- if hasKey $p "datasource" -}}
{{- $_ := set $p "datasource" $ds -}}
{{- end -}}
{{- range $t := ($p.targets | default list) -}}
{{- $_ := set $t "datasource" $ds -}}
{{- if hasKey $t "expr" -}}
{{- $_ := set $t "expr" (include "document-service.scopeExpr" (dict "expr" $t.expr "namespace" $ns)) -}}
{{- end -}}
{{- end -}}
{{- if and $links.jaeger $p.options (hasKey $p.options "content") -}}
{{- $_ := set $p.options "content" (replace "http://localhost:16686" (trimSuffix "/" $links.jaeger) $p.options.content) -}}
{{- end -}}
{{- end -}}
{{- toPrettyJson $d -}}
{{- end -}}
