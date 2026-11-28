package migration.local

import rego.v1

deny contains msg if {
	not input.kind in {"Deployment", "Service", "NetworkPolicy"}
	msg := sprintf("Unexpected resource in local migration sandbox: %s", [input.kind])
}

deny contains "Services must be internal ClusterIP without external IPs" if {
	input.kind == "Service"
	input.spec.type != "ClusterIP"
}

deny contains "Services must not have external IPs" if {
	input.kind == "Service"
	count(object.get(input.spec, "externalIPs", [])) > 0
}

deny contains "Sandbox image must be loaded locally, never pulled" if {
	input.kind == "Deployment"
	some container in input.spec.template.spec.containers
	container.imagePullPolicy != "Never"
}

deny contains "Sandbox does not accept credential references" if {
	input.kind == "Deployment"
	some container in input.spec.template.spec.containers
	some env in container.env
	env.valueFrom.secretKeyRef
}
