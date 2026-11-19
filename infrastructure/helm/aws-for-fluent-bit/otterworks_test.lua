dofile(arg[1] or "infrastructure/helm/aws-for-fluent-bit/otterworks.lua")

local function check(record, expected_group)
  local code, timestamp, result = route_record("kube.test", 123, record)
  if expected_group == nil then
    assert(code == -1)
  else
    assert(code == 2 and timestamp == 123)
    assert(result.cw_group == expected_group, result.cw_group)
  end
  return result
end

check({kubernetes = {namespace_name = "otterworks-main", container_name = "document-service"}, log = "plain startup line"}, "otterworks-main/document-service")
check({kubernetes = {namespace_name = "otterworks-main", container_name = "api-gateway"}, log = "startup"}, "otterworks-main/api-gateway")
check({kubernetes = {namespace_name = "otterworks-main", container_name = "worker"}, message = "error", level = "error"}, "otterworks-main/worker")
local access = check({kubernetes = {namespace_name = "ingress-nginx", container_name = "controller"}, namespace = "otterworks-main", request_time = "0.25", path = "/files/123", user_agent = "Mozilla/5"}, "otterworks-main/ingress-nginx")
assert(access.duration_ms == 250 and access.route == "/files/:id" and access.client == "web")
check({})
check({kubernetes = {}})
check({kubernetes = {namespace_name = "kube-system", container_name = "coredns"}})
check({kubernetes = {namespace_name = "otterworks-main"}})
check({kubernetes = {namespace_name = "ingress-nginx", container_name = "controller"}, namespace = "default", request_time = "1"})
check({kubernetes = {namespace_name = "ingress-nginx", container_name = "controller"}, namespace = "otterworks-main"})
local malformed = check({kubernetes = {namespace_name = "ingress-nginx", container_name = "controller"}, namespace = "otterworks-main", request_time = "invalid"}, "otterworks-main/ingress-nginx")
assert(malformed.duration_ms == nil)
print("PASS: tenant application, startup, error, ingress, empty and excluded log routing")
