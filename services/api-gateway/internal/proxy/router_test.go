package proxy

import (
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/rs/zerolog"
)

func TestPublicRequestCannotForwardSpoofedIdentity(t *testing.T) {
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("X-User-ID"); got != "" {
			t.Errorf("backend received spoofed identity: %q", got)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer backend.Close()
	logger := zerolog.New(io.Discard)
	cfg := RouterConfig{CBManager: NewCircuitBreakerManager(CircuitBreakerConfig{}), Logger: logger}
	handler := newProxyHandler(Route{Prefix: "/api/v1/auth", TargetURL: backend.URL}, cfg)
	req := httptest.NewRequest(http.MethodGet, "/api/v1/auth/public", nil)
	req.Header.Set("X-User-ID", "victim")
	handler(httptest.NewRecorder(), req)
}
