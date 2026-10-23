package config

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestServiceRoutes_ReportsRouteMapsToReportService(t *testing.T) {
	cfg := Load()

	target, ok := cfg.ServiceRoutes()["/api/v1/reports"]
	require.True(t, ok, "/api/v1/reports must be routed by the gateway")
	assert.Equal(t, cfg.ReportServiceURL, target)
	assert.Equal(t, "http://report-service:8091", target)
}

func TestServiceRoutes_ReportsRouteHonoursReportServiceURL(t *testing.T) {
	t.Setenv("REPORT_SERVICE_URL", "http://reports.example.internal:9000")

	cfg := Load()

	assert.Equal(t, "http://reports.example.internal:9000", cfg.ServiceRoutes()["/api/v1/reports"])
}
