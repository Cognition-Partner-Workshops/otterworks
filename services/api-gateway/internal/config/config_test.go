package config

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func testConfig() *Config {
	return &Config{
		AuthServiceURL:         "http://auth",
		FileServiceURL:         "http://file",
		DocumentServiceURL:     "http://document",
		CollabServiceURL:       "http://collab",
		NotificationServiceURL: "http://notification",
		SearchServiceURL:       "http://search",
		AnalyticsServiceURL:    "http://analytics",
		AdminServiceURL:        "http://admin",
		AuditServiceURL:        "http://audit",
		ReportServiceURL:       "http://report",
	}
}

func TestServiceRoutes_ReportsPrefixMapsToReportService(t *testing.T) {
	routes := testConfig().ServiceRoutes()

	target, ok := routes["/api/v1/reports"]
	assert.True(t, ok, "/api/v1/reports must be routed")
	assert.Equal(t, "http://report", target)
}

func TestServiceRoutes_CompleteRouteTable(t *testing.T) {
	expected := map[string]string{
		"/api/v1/auth":          "http://auth",
		"/api/v1/files":         "http://file",
		"/api/v1/folders":       "http://file",
		"/api/v1/documents":     "http://document",
		"/api/v1/templates":     "http://document",
		"/api/v1/collab":        "http://collab",
		"/socket.io":            "http://collab",
		"/api/v1/notifications": "http://notification",
		"/api/v1/preferences":   "http://notification",
		"/api/v1/search":        "http://search",
		"/api/v1/analytics":     "http://analytics",
		"/api/v1/admin":         "http://admin",
		"/api/v1/audit":         "http://audit",
		"/api/v1/reports":       "http://report",
		"/api/v1/settings":      "http://auth",
	}

	assert.Equal(t, expected, testConfig().ServiceRoutes())
}

func TestLoad_ReportServiceURLDefaultAndOverride(t *testing.T) {
	t.Setenv("REPORT_SERVICE_URL", "http://report-service.otterworks-x:8091")
	assert.Equal(t, "http://report-service.otterworks-x:8091", Load().ServiceRoutes()["/api/v1/reports"])
}

func TestLoad_ReportServiceURLDefault(t *testing.T) {
	assert.Equal(t, "http://report-service:8091", Load().ReportServiceURL)
}
