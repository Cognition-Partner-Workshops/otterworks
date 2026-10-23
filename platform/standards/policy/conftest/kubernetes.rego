# Platform policy for rendered Kubernetes manifests. The pipeline runs
#   conftest test --policy policy/conftest --data policy/conftest/data --namespace platform.k8s
# against `helm template` output; the Kyverno policies in policy/kyverno
# enforce the same rules at admission.
package platform.k8s

import rego.v1

workload_kinds := {"Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob", "Pod"}

pod_spec := input.spec.jobTemplate.spec.template.spec if input.kind == "CronJob"
pod_spec := input.spec if input.kind == "Pod"
pod_spec := input.spec.template.spec if {
	input.kind != "CronJob"
	input.kind != "Pod"
}

containers contains c if {
	workload_kinds[input.kind]
	some c in pod_spec.containers
}

containers contains c if {
	workload_kinds[input.kind]
	some c in pod_spec.initContainers
}

name := sprintf("%s/%s", [input.kind, input.metadata.name])

required_labels := {"app", "owner", "cost-center"}

deny contains msg if {
	workload_kinds[input.kind]
	some l in required_labels
	not input.metadata.labels[l]
	msg := sprintf("LABEL-01 %s is missing the required label %q", [name, l])
}

deny contains msg if {
	some c in containers
	not run_as_non_root(c)
	msg := sprintf("SEC-01 %s container %q must run as a non-root user (runAsNonRoot: true)", [name, c.name])
}

run_as_non_root(c) if c.securityContext.runAsNonRoot == true

run_as_non_root(c) if {
	not c.securityContext.runAsNonRoot == false
	pod_spec.securityContext.runAsNonRoot == true
}

deny contains msg if {
	some c in containers
	not c.securityContext.readOnlyRootFilesystem == true
	msg := sprintf("SEC-02 %s container %q must set readOnlyRootFilesystem: true", [name, c.name])
}

deny contains msg if {
	some c in containers
	some kind in ["requests", "limits"]
	some res in ["cpu", "memory"]
	not c.resources[kind][res]
	msg := sprintf("RES-01 %s container %q is missing resources.%s.%s", [name, c.name, kind, res])
}

long_running := {"Deployment", "StatefulSet", "DaemonSet"}

deny contains msg if {
	long_running[input.kind]
	some c in pod_spec.containers
	some probe in ["livenessProbe", "readinessProbe"]
	not c[probe]
	msg := sprintf("PROBE-01 %s container %q has no %s; every long-running service answers /health", [name, c.name, probe])
}

deny contains msg if {
	some c in containers
	not approved_image(c.image)
	msg := sprintf("REG-01 %s container %q uses image %q from outside the approved registry", [name, c.name, c.image])
}

approved_image(image) if {
	some prefix in data.registries.approved
	startswith(image, prefix)
}

deny contains msg if {
	some c in containers
	endswith(c.image, ":latest")
	msg := sprintf("REG-02 %s container %q uses the mutable tag latest", [name, c.name])
}

secret_name_pattern := `(?i)(password|passwd|secret|token|api[_-]?key|private[_-]?key|credential)`

deny contains msg if {
	some c in containers
	some e in c.env
	regex.match(secret_name_pattern, e.name)
	e.value
	msg := sprintf("SECRET-01 %s container %q sets %s as a literal; reference a secret with valueFrom.secretKeyRef", [name, c.name, e.name])
}

deny contains msg if {
	input.kind == "Secret"
	count(object.get(input, "data", {})) + count(object.get(input, "stringData", {})) > 0
	msg := sprintf("SECRET-02 Secret/%s carries values in the manifest; secrets come from the secret store", [input.metadata.name])
}

deny contains msg if {
	input.kind == "ConfigMap"
	some k, v in input.data
	regex.match(`(?i)(password|passwd|secret|token)\s*[=:]\s*\S{4,}`, v)
	msg := sprintf("SECRET-03 ConfigMap/%s key %q holds what looks like a credential", [input.metadata.name, k])
}

deny contains msg if {
	input.kind == "Service"
	input.spec.type in {"LoadBalancer", "NodePort"}
	msg := sprintf("NET-01 Service/%s is type %s; services are ClusterIP behind the shared ingress-nginx", [input.metadata.name, input.spec.type])
}
