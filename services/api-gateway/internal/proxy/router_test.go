package proxy

import (
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/Cognition-Partner-Workshops/otterworks/services/api-gateway/internal/config"
)

func TestRouter_ReportsRouteProxiesToReportService(t *testing.T) {
	var gotPath string
	reportService := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotPath = r.URL.Path
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("report-service"))
	}))
	defer reportService.Close()
	t.Setenv("REPORT_SERVICE_URL", reportService.URL)

	var routes []Route
	for prefix, target := range config.Load().ServiceRoutes() {
		routes = append(routes, Route{Prefix: prefix, TargetURL: target})
	}
	router := NewRouter(RouterConfig{
		Routes:    routes,
		CBManager: NewCircuitBreakerManager(defaultTestConfig()),
		Logger:    zerolog.Nop(),
	})

	req := httptest.NewRequest(http.MethodGet, "/api/v1/reports/abc-123", nil)
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	require.Equal(t, http.StatusOK, rec.Code)
	body, _ := io.ReadAll(rec.Body)
	assert.Equal(t, "report-service", string(body))
	assert.Equal(t, "/api/v1/reports/abc-123", gotPath)
}
