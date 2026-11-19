package proxy

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/Cognition-Partner-Workshops/otterworks/services/api-gateway/internal/config"
	"github.com/Cognition-Partner-Workshops/otterworks/services/api-gateway/internal/middleware"
)

const routerTestSecret = "router-test-secret"

type capturedRequest struct {
	method string
	path   string
	userID string
	body   string
}

// newGateway wires the configured service routes behind JWT auth the same way cmd/server does,
// with the auth service pointed at authURL.
func newGateway(t *testing.T, authURL string) http.Handler {
	t.Helper()
	cfg := config.Load()
	cfg.AuthServiceURL = authURL

	var routes []Route
	prefixes := make([]string, 0)
	for prefix, target := range cfg.ServiceRoutes() {
		routes = append(routes, Route{Prefix: prefix, TargetURL: target})
		prefixes = append(prefixes, prefix)
	}

	proxyRouter := NewRouter(RouterConfig{
		Routes:    routes,
		CBManager: NewCircuitBreakerManager(defaultTestConfig()),
		Logger:    zerolog.Nop(),
	})
	return middleware.JWTAuth(middleware.JWTConfig{
		Secret:              routerTestSecret,
		PublicPath:          middleware.DefaultPublicPaths(),
		PrefixPath:          middleware.DefaultPrefixPaths(),
		ProtectedPrefixPath: prefixes,
	})(proxyRouter)
}

func newAuthBackend(t *testing.T) (*httptest.Server, *[]capturedRequest) {
	t.Helper()
	var captured []capturedRequest
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		captured = append(captured, capturedRequest{
			method: r.Method,
			path:   r.URL.Path,
			userID: r.Header.Get("X-User-ID"),
			body:   string(body),
		})
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"notificationEmail":true,"notificationInApp":true,"notificationDesktop":false}`))
	}))
	t.Cleanup(srv.Close)
	return srv, &captured
}

func signToken(t *testing.T, subject string) string {
	t.Helper()
	claims := middleware.JWTClaims{RegisteredClaims: jwt.RegisteredClaims{
		Subject:   subject,
		ExpiresAt: jwt.NewNumericDate(time.Now().Add(time.Hour)),
	}}
	token, err := jwt.NewWithClaims(jwt.SigningMethodHS256, claims).SignedString([]byte(routerTestSecret))
	require.NoError(t, err)
	return token
}

func TestRouter_SettingsProxiesToAuthServiceWithUserID(t *testing.T) {
	backend, captured := newAuthBackend(t)
	gateway := newGateway(t, backend.URL)
	token := signToken(t, "user-123")

	tests := []struct {
		method string
		body   string
	}{
		{http.MethodGet, ""},
		{http.MethodPatch, `{"notificationDesktop":true}`},
	}
	for _, tc := range tests {
		t.Run(tc.method, func(t *testing.T) {
			*captured = nil
			req := httptest.NewRequest(tc.method, "/api/v1/settings", strings.NewReader(tc.body))
			req.Header.Set("Authorization", "Bearer "+token)
			req.Header.Set("Content-Type", "application/json")
			rec := httptest.NewRecorder()

			gateway.ServeHTTP(rec, req)

			assert.Equal(t, http.StatusOK, rec.Code, rec.Body.String())
			require.Len(t, *captured, 1)
			got := (*captured)[0]
			assert.Equal(t, tc.method, got.method)
			assert.Equal(t, "/api/v1/settings", got.path)
			assert.Equal(t, "user-123", got.userID)
			assert.Equal(t, tc.body, got.body)
		})
	}
}

func TestRouter_SettingsRequiresJWT(t *testing.T) {
	backend, captured := newAuthBackend(t)
	gateway := newGateway(t, backend.URL)

	for _, method := range []string{http.MethodGet, http.MethodPatch} {
		t.Run(method, func(t *testing.T) {
			req := httptest.NewRequest(method, "/api/v1/settings", nil)
			rec := httptest.NewRecorder()

			gateway.ServeHTTP(rec, req)

			assert.Equal(t, http.StatusUnauthorized, rec.Code)
		})
	}
	assert.Empty(t, *captured, "unauthenticated settings requests must not reach the auth service")
}
