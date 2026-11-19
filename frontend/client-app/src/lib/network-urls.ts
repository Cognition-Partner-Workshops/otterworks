export function resolveNetworkUrls(
  platform: string,
  apiOverride?: string,
  collabOverride?: string,
  webProtocol = "http:",
) {
  const native = platform !== "web";
  const host = platform === "android" ? "10.0.2.2" : "localhost";
  return {
    api: native ? apiOverride || `http://${host}:8080/api/v1` : "/api/v1",
    collab: collabOverride || `${native || webProtocol !== "https:" ? "ws" : "wss"}://${host}:8085`,
  };
}
