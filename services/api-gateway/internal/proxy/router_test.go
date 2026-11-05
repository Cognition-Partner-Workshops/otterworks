package proxy

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/Cognition-Partner-Workshops/otterworks/services/api-gateway/internal/config"
)

func TestSearchRoutesPreserveRequestURI(t *testing.T) {
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, http.MethodGet, r.Method)
		w.Write([]byte(r.RequestURI))
	}))
	defer backend.Close()
	cfg := config.Config{SearchServiceURL: backend.URL}
	prefixes := []string{"/api/v1/search", "/api/v1/insights/search"}
	for _, reverse := range []bool{false, true} {
		var routes []Route
		for i := range prefixes {
			if reverse {
				i = len(prefixes) - 1 - i
			}
			prefix := prefixes[i]
			target := cfg.ServiceRoutes()[prefix]
			require.Equal(t, backend.URL, target)
			routes = append(routes, Route{Prefix: prefix, TargetURL: target})
		}
		router := NewRouter(RouterConfig{
			Routes: routes, CBManager: NewCircuitBreakerManager(defaultTestConfig()), Logger: zerolog.Nop(),
		})
		for _, uri := range []string{
			"/api/v1/insights/search/accounts/00000000-0000-4000-8000-000000000101/top?item_type=term&window_end_date=2026-11-01",
			"/api/v1/search?q=budget",
		} {
			rec := httptest.NewRecorder()
			router.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, uri, nil))
			assert.Equal(t, http.StatusOK, rec.Code)
			assert.Equal(t, uri, rec.Body.String())
		}
	}
}
