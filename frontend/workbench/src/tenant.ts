const TENANT_PATTERN = /^[a-z0-9][a-z0-9-]{0,30}$/;

export function isValidTenantId(value: string): boolean {
  return TENANT_PATTERN.test(value);
}

export function tenantUrl(url: string, tenantId: string): string {
  if (!tenantId || !isValidTenantId(tenantId)) return url;
  try {
    const parsed = new URL(url);
    const isApi = /^api-t-[^.]+(?:\.demo)?\.otterworks\.app$/i.test(parsed.hostname);
    const isWeb = /^t-[^.]+(?:\.demo)?\.otterworks\.app$/i.test(parsed.hostname);
    if (!isApi && !isWeb) return url;
    parsed.hostname = `${isApi ? "api-t" : "t"}-${tenantId}.demo.otterworks.app`;
    return parsed.toString();
  } catch {
    return url;
  }
}
