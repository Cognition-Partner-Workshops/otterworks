package config

import "testing"

func TestBillingRoute(t *testing.T) {
	t.Setenv("LEGACY_BILLING_URL", "http://test-billing:8096")
	if got := Load().ServiceRoutes()["/api/v1/billing"]; got != "http://test-billing:8096" {
		t.Fatalf("billing route = %q", got)
	}
}

func TestODLRoute(t *testing.T) {
	t.Setenv("ODL_SERVICE_URL", "http://test-odl:8098")
	if got := Load().ServiceRoutes()["/api/v1/odl"]; got != "http://test-odl:8098" {
		t.Fatalf("ODL route = %q", got)
	}
}
