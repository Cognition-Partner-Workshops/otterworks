# Platform policy for Dockerfiles. The pipeline runs
#   conftest test --parser dockerfile --policy policy/conftest --data <standards> --namespace platform.dockerfile Dockerfile
package platform.dockerfile

import rego.v1

# conftest hands over the instruction list directly; `conftest parse` wraps it
# in an outer list, so accept both shapes.
instructions := input[0] if is_array(input[0])

instructions := input if not is_array(input[0])

froms := [i | some i in instructions; i.Cmd == "from"]

stage_names contains lower(i.Value[2]) if {
	some i in froms
	count(i.Value) == 3
}

approved contains img.image if some img in data.base_images

deny contains msg if {
	some i in froms
	ref := i.Value[0]
	not stage_names[lower(ref)]
	not approved[ref]
	msg := sprintf("BASE-01 FROM %s is not an approved base image pinned by digest (see platform/standards/base-images.yaml)", [ref])
}

final_stage := max({i.Stage | some i in instructions})

final_users := [u | some u in instructions; u.Cmd == "user"; u.Stage == final_stage]

deny contains "BASE-02 the final stage never sets USER; images run as a numeric non-root user" if {
	count(final_users) == 0
}

deny contains msg if {
	u := final_users[count(final_users) - 1]
	user := split(u.Value[0], ":")[0]
	not non_root_numeric(user)
	msg := sprintf("BASE-02 the final stage runs as USER %s; use a numeric uid other than 0", [u.Value[0]])
}

non_root_numeric(user) if {
	to_number(user) > 0
}

deny contains msg if {
	some i in instructions
	i.Cmd in {"env", "arg"}
	some v in i.Value
	regex.match(`(?i)(password|passwd|secret|token|api[_-]?key)`, v)
	msg := sprintf("SECRET-04 %s %v bakes a credential name into the image; pass it at runtime from the secret store", [upper(i.Cmd), i.Value])
}
