package proxy

import (
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/Cognition-Partner-Workshops/otterworks/services/api-gateway/internal/config"
	"github.com/Cognition-Partner-Workshops/otterworks/services/api-gateway/internal/middleware"
)

const testJWTSecret = "router-test-secret"

type recordedRequest struct {
	Path   string
	UserID string
}

type upstream struct {
	srv  *httptest.Server
	mu   sync.Mutex
	reqs []recordedRequest
}

func newUpstream(t *testing.T) *upstream {
	u := &upstream{}
	u.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		u.mu.Lock()
		u.reqs = append(u.reqs, recordedRequest{Path: r.URL.Path, UserID: r.Header.Get("X-User-ID")})
		u.mu.Unlock()
		w.WriteHeader(http.StatusOK)
	}))
	t.Cleanup(u.srv.Close)
	return u
}

func (u *upstream) requests() []recordedRequest {
	u.mu.Lock()
	defer u.mu.Unlock()
	return append([]recordedRequest(nil), u.reqs...)
}

// newGateway wires the gateway the way cmd/server does: routes from
// config.ServiceRoutes(), JWT protection on every route prefix, then the proxy.
func newGateway(t *testing.T, report, other *upstream) http.Handler {
	t.Helper()
	cfg := &config.Config{
		AuthServiceURL:         other.srv.URL,
		FileServiceURL:         other.srv.URL,
		DocumentServiceURL:     other.srv.URL,
		CollabServiceURL:       other.srv.URL,
		NotificationServiceURL: other.srv.URL,
		SearchServiceURL:       other.srv.URL,
		AnalyticsServiceURL:    other.srv.URL,
		AdminServiceURL:        other.srv.URL,
		AuditServiceURL:        other.srv.URL,
		ReportServiceURL:       report.srv.URL,
	}

	var routes []Route
	var prefixes []string
	for prefix, target := range cfg.ServiceRoutes() {
		routes = append(routes, Route{Prefix: prefix, TargetURL: target})
		prefixes = append(prefixes, prefix)
	}

	router := NewRouter(RouterConfig{
		Routes:    routes,
		CBManager: NewCircuitBreakerManager(defaultTestConfig()),
		Logger:    zerolog.Nop(),
	})

	return middleware.JWTAuth(middleware.JWTConfig{
		Secret:              testJWTSecret,
		PublicPath:          middleware.DefaultPublicPaths(),
		PrefixPath:          middleware.DefaultPrefixPaths(),
		ProtectedPrefixPath: prefixes,
	})(router)
}

func signedToken(t *testing.T, subject string) string {
	t.Helper()
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.RegisteredClaims{
		Subject:   subject,
		ExpiresAt: jwt.NewNumericDate(time.Now().Add(time.Hour)),
	})
	s, err := token.SignedString([]byte(testJWTSecret))
	require.NoError(t, err)
	return s
}

func TestRouter_ReportsPathsForwardToReportService(t *testing.T) {
	report, other := newUpstream(t), newUpstream(t)
	gw := newGateway(t, report, other)
	token := signedToken(t, "user-42")

	paths := []string{
		"/api/v1/reports",
		"/api/v1/reports/scheduled",
		"/api/v1/reports/reconciliation",
		"/api/v1/reports/reconciliation/run-1",
		"/api/v1/reports/reconciliation/run-1.csv",
		"/api/v1/reports/archive/documents/doc-1",
	}
	for _, p := range paths {
		req := httptest.NewRequest(http.MethodGet, p, nil)
		req.Header.Set("Authorization", "Bearer "+token)
		rec := httptest.NewRecorder()
		gw.ServeHTTP(rec, req)
		assert.Equal(t, http.StatusOK, rec.Code, "%s should be forwarded, got body %s", p, rec.Body.String())
	}

	got := report.requests()
	require.Len(t, got, len(paths))
	for i, p := range paths {
		assert.Equal(t, p, got[i].Path)
		assert.Equal(t, "user-42", got[i].UserID)
	}
	assert.Empty(t, other.requests(), "report traffic must not reach any other upstream")
}

func TestRouter_ReportsRequiresJWT(t *testing.T) {
	report, other := newUpstream(t), newUpstream(t)
	gw := newGateway(t, report, other)

	for _, auth := range []string{"", "Bearer not-a-jwt"} {
		req := httptest.NewRequest(http.MethodGet, "/api/v1/reports/scheduled", nil)
		if auth != "" {
			req.Header.Set("Authorization", auth)
		}
		rec := httptest.NewRecorder()
		gw.ServeHTTP(rec, req)
		assert.Equal(t, http.StatusUnauthorized, rec.Code, "auth=%q", auth)
	}
	assert.Empty(t, report.requests())
}

func TestRouter_UnknownPrefixStill404s(t *testing.T) {
	report, other := newUpstream(t), newUpstream(t)
	gw := newGateway(t, report, other)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/reportsx/scheduled", nil)
	req.Header.Set("Authorization", "Bearer "+signedToken(t, "user-42"))
	rec := httptest.NewRecorder()
	gw.ServeHTTP(rec, req)

	assert.Equal(t, http.StatusNotFound, rec.Code)
	assert.Empty(t, report.requests())
	assert.Empty(t, other.requests())
}
