package proxy

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/rs/zerolog"
)

func TestProxyStripsClientSuppliedUserID(t *testing.T) {
	var seen []string
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = r.Header.Values("X-User-ID")
		w.WriteHeader(http.StatusOK)
	}))
	defer backend.Close()

	router := NewRouter(RouterConfig{
		Routes:    []Route{{Prefix: "/api/v1/search", TargetURL: backend.URL}},
		CBManager: NewCircuitBreakerManager(defaultTestConfig()),
		Logger:    zerolog.Nop(),
	})

	req := httptest.NewRequest(http.MethodPost, "/api/v1/search/reindex", nil)
	req.Header.Set("X-User-ID", "spoofed-admin")
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", rec.Code)
	}
	if len(seen) != 0 {
		t.Fatalf("backend received client-supplied X-User-ID %q", seen)
	}
}
