package proxy

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"

	"github.com/Cognition-Partner-Workshops/otterworks/services/api-gateway/internal/middleware"
)

func TestRouter_GatewaySecurityHeadersReplaceBackendCopies(t *testing.T) {
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Frame-Options", "SAMEORIGIN")
		w.Header().Set("Content-Security-Policy", "default-src *")
		w.Header().Set("X-Backend", "kept")
		w.WriteHeader(http.StatusOK)
	}))
	defer backend.Close()

	router := NewRouter(RouterConfig{
		Routes:    []Route{{Prefix: "/api/v1/documents", TargetURL: backend.URL}},
		CBManager: NewCircuitBreakerManager(defaultTestConfig()),
		Logger:    zerolog.Nop(),
	})
	handler := middleware.SecurityHeaders(router)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/documents/", nil)
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	assert.Equal(t, http.StatusOK, rec.Code)
	assert.Equal(t, []string{"DENY"}, rec.Header().Values("X-Frame-Options"))
	assert.Equal(t, []string{"default-src 'none'; frame-ancestors 'none'"}, rec.Header().Values("Content-Security-Policy"))
	assert.Equal(t, "nosniff", rec.Header().Get("X-Content-Type-Options"))
	assert.Equal(t, "kept", rec.Header().Get("X-Backend"))
}
