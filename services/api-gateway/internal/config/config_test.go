package config

import "testing"

func TestBillingRoute(t *testing.T) {
	t.Setenv("LEGACY_BILLING_URL", "http://test-billing:8096")
	if got := Load().ServiceRoutes()["/api/v1/billing"]; got != "http://test-billing:8096" {
		t.Fatalf("billing route = %q", got)
	}
}
