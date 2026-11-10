package config

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestServiceRoutes_SettingsRoutesToAuthService(t *testing.T) {
	cfg := &Config{AuthServiceURL: "http://auth-service:8081", NotificationServiceURL: "http://notification-service:8086"}

	routes := cfg.ServiceRoutes()

	assert.Equal(t, cfg.AuthServiceURL, routes["/api/v1/settings"])
}

func TestLoad_AuthServiceURLFromEnv(t *testing.T) {
	t.Setenv("AUTH_SERVICE_URL", "http://auth.test:9999")

	cfg := Load()

	assert.Equal(t, "http://auth.test:9999", cfg.ServiceRoutes()["/api/v1/settings"])
}
