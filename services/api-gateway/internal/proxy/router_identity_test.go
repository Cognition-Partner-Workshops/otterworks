package proxy

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/rs/zerolog"
)

func newTestRouter(t *testing.T, backend *httptest.Server) http.Handler {
	t.Helper()
	return NewRouter(RouterConfig{
		Routes:    []Route{{Prefix: "/api/v1/search", TargetURL: backend.URL}},
		CBManager: NewCircuitBreakerManager(CircuitBreakerConfig{MaxRequests: 1, Interval: time.Minute, Timeout: time.Second, FailureRatio: 0.5}),
		Logger:    zerolog.Nop(),
	})
}

func TestClientSuppliedIdentityHeadersAreStripped(t *testing.T) {
	var gotUser, gotRoles string
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotUser = r.Header.Get(HeaderUserID)
		gotRoles = r.Header.Get(HeaderUserRoles)
		w.WriteHeader(http.StatusOK)
	}))
	defer backend.Close()

	req := httptest.NewRequest(http.MethodGet, "/api/v1/search/query", nil)
	req.Header.Set(HeaderUserID, "spoofed-user")
	req.Header.Set(HeaderUserRoles, "admin")
	rec := httptest.NewRecorder()
	newTestRouter(t, backend).ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", rec.Code)
	}
	if gotUser != "" || gotRoles != "" {
		t.Fatalf("spoofed identity reached backend: user=%q roles=%q", gotUser, gotRoles)
	}
}

func TestInternalOnlySearchRoutesAreNotProxied(t *testing.T) {
	hit := false
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hit = true
	}))
	defer backend.Close()

	for _, path := range []string{
		"/api/v1/search/reindex",
		"/api/v1/search/index/document",
		"/api/v1/search/index/document/abc",
	} {
		rec := httptest.NewRecorder()
		newTestRouter(t, backend).ServeHTTP(rec, httptest.NewRequest(http.MethodPost, path, nil))
		if rec.Code != http.StatusNotFound {
			t.Fatalf("%s: status = %d, want 404", path, rec.Code)
		}
	}
	if hit {
		t.Fatal("internal-only route was proxied to the backend")
	}
}
