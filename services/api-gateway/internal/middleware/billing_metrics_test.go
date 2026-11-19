package middleware

import "testing"

func TestBillingMetricLabel(t *testing.T) {
	for _, path := range []string{"/api/v1/billing", "/api/v1/billing/", "/api/v1/billing/tenants/123/rating"} {
		if got := normalizePath(path); got != "/api/v1/billing" {
			t.Errorf("normalizePath(%q) = %q", path, got)
		}
	}
	if got := normalizePath("/api/v1/billing-other"); got != "other" {
		t.Errorf("prefix boundary label = %q", got)
	}
}
