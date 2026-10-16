-- Routes api-gateway and ingress-nginx access log records to their tenant's
-- CloudWatch log group and drops everything else.
--
-- api-gateway records already carry method, route, status, duration_ms and
-- client (services/api-gateway/internal/middleware/logging.go). ingress-nginx
-- records carry the upstream namespace and request_time in seconds
-- (infrastructure/helm/ingress-nginx/values-logging.yaml); this adds the same
-- route, duration_ms and client fields so both containers query alike.

local function client_for(ua)
  if ua == nil then return "other" end
  local platform = string.match(ua, "OtterWorksApp/(%a+)")
  if platform ~= nil then
    platform = string.lower(platform)
    if platform == "ios" or platform == "android" then return platform end
    return "other"
  end
  if string.sub(ua, 1, 8) == "Mozilla/" then return "web" end
  return "other"
end

local function is_id(seg)
  if string.match(seg, "^%x%x%x%x%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%x%x%x%x%x%x%x%x$") then return true end
  if string.match(seg, "^%d+$") then return true end
  if #seg >= 24 and string.match(seg, "^%x+$") then return true end
  return false
end

local function route_for(path)
  if path == nil or path == "" or path == "/" then return "/" end
  path = string.gsub(path, "/$", "")
  local out = {}
  for seg in string.gmatch(path, "([^/]*)/?") do
    if seg ~= "" then
      if is_id(seg) then seg = ":id" end
      table.insert(out, seg)
    end
  end
  return "/" .. table.concat(out, "/")
end

function route_record(tag, timestamp, record)
  local k8s = record["kubernetes"] or {}
  local container = k8s["container_name"]
  local namespace

  if container == "api-gateway" then
    namespace = k8s["namespace_name"]
    if record["route"] == nil then return -1, 0, 0 end -- startup / non-access lines
    record["cw_container"] = "api-gateway"
  elseif container == "controller" and k8s["namespace_name"] == "ingress-nginx" then
    namespace = record["namespace"]
    if namespace == nil or record["request_time"] == nil then return -1, 0, 0 end
    local seconds = tonumber(record["request_time"])
    if seconds ~= nil then record["duration_ms"] = seconds * 1000 end
    record["route"] = route_for(record["path"])
    record["client"] = client_for(record["user_agent"])
    record["cw_container"] = "ingress-nginx"
  else
    return -1, 0, 0
  end

  if namespace == nil or string.match(namespace, "^otterworks%-") == nil then
    return -1, 0, 0
  end
  record["cw_namespace"] = namespace
  record["cw_group"] = namespace .. "/" .. record["cw_container"]
  return 2, timestamp, record
end
