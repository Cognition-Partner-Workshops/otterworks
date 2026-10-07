package proxy

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/Cognition-Partner-Workshops/otterworks/services/api-gateway/internal/middleware"
)

const testSecret = "router-test-secret-0123456789abcdef0123456789abcdef"

func newIdentityTestServer(t *testing.T) (http.Handler, *string) {
	t.Helper()
	seen := new(string)
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		*seen = r.Header.Get("X-User-ID")
		w.WriteHeader(http.StatusOK)
	}))
	t.Cleanup(backend.Close)

	router := NewRouter(RouterConfig{
		Routes:    []Route{{Prefix: "/api/v1/search", TargetURL: backend.URL}},
		CBManager: NewCircuitBreakerManager(defaultTestConfig()),
		Logger:    zerolog.Nop(),
	})
	auth := middleware.JWTAuth(middleware.JWTConfig{
		Secret:     testSecret,
		PublicPath: []string{"/api/v1/search/public"},
	})
	return auth(router), seen
}

func TestRouter_StripsSpoofedUserIDOnUnauthenticatedRoute(t *testing.T) {
	handler, seen := newIdentityTestServer(t)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/search/public", nil)
	req.Header.Set("X-User-ID", "victim")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	require.Equal(t, http.StatusOK, rec.Code)
	assert.Empty(t, *seen)
}

func TestRouter_OverwritesSpoofedUserIDWithTokenSubject(t *testing.T) {
	handler, seen := newIdentityTestServer(t)

	claims := middleware.JWTClaims{RegisteredClaims: jwt.RegisteredClaims{
		Subject:   "attacker",
		ExpiresAt: jwt.NewNumericDate(time.Now().Add(time.Hour)),
	}}
	token, err := jwt.NewWithClaims(jwt.SigningMethodHS256, claims).SignedString([]byte(testSecret))
	require.NoError(t, err)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/search/?q=x", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("X-User-ID", "victim")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	require.Equal(t, http.StatusOK, rec.Code)
	assert.Equal(t, "attacker", *seen)
}
