package proxy

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/golang-jwt/jwt/v5"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/Cognition-Partner-Workshops/otterworks/services/api-gateway/internal/middleware"
)

const testInternalSecret = "test-internal-auth-secret"

// backendRecorder is a fake backend that records the headers it received.
func backendRecorder(t *testing.T) (*httptest.Server, *http.Header) {
	t.Helper()
	var seen http.Header
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = r.Header.Clone()
		w.WriteHeader(http.StatusOK)
	}))
	t.Cleanup(srv.Close)
	return srv, &seen
}

func newTestRouter(t *testing.T, backendURL string, claims *middleware.JWTClaims) http.Handler {
	t.Helper()
	cbManager := NewCircuitBreakerManager(CircuitBreakerConfig{MaxRequests: 5, FailureRatio: 0.6})
	router := NewRouter(RouterConfig{
		Routes:             []Route{{Prefix: "/api/v1/files", TargetURL: backendURL}},
		CBManager:          cbManager,
		Logger:             zerolog.Nop(),
		InternalAuthSecret: testInternalSecret,
	})
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if claims != nil {
			r = r.WithContext(middleware.WithJWTClaims(r.Context(), claims))
		}
		router.ServeHTTP(w, r)
	})
}

func expectedSignature(userID string) string {
	mac := hmac.New(sha256.New, []byte(testInternalSecret))
	mac.Write([]byte(userID))
	return hex.EncodeToString(mac.Sum(nil))
}

func TestDirector_AttestsIdentityFromJWTClaims(t *testing.T) {
	backend, seen := backendRecorder(t)
	claims := &middleware.JWTClaims{RegisteredClaims: jwt.RegisteredClaims{Subject: "user-123"}}
	handler := newTestRouter(t, backend.URL, claims)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/files", nil)
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	require.Equal(t, http.StatusOK, rec.Code)
	assert.Equal(t, "user-123", seen.Get(UserIDHeader))
	assert.Equal(t, expectedSignature("user-123"), seen.Get(SignatureHeader))
}

func TestDirector_StripsClientSuppliedIdentityHeaders(t *testing.T) {
	backend, seen := backendRecorder(t)
	claims := &middleware.JWTClaims{RegisteredClaims: jwt.RegisteredClaims{Subject: "real-user"}}
	handler := newTestRouter(t, backend.URL, claims)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/files", nil)
	req.Header.Set(UserIDHeader, "victim-user")
	req.Header.Set(SignatureHeader, expectedSignature("victim-user"))
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	require.Equal(t, http.StatusOK, rec.Code)
	assert.Equal(t, "real-user", seen.Get(UserIDHeader))
	assert.Equal(t, expectedSignature("real-user"), seen.Get(SignatureHeader))
	assert.Len(t, seen.Values(UserIDHeader), 1)
	assert.Len(t, seen.Values(SignatureHeader), 1)
}

func TestDirector_NoClaimsForwardsNoIdentity(t *testing.T) {
	backend, seen := backendRecorder(t)
	handler := newTestRouter(t, backend.URL, nil)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/files", nil)
	req.Header.Set(UserIDHeader, "victim-user")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	require.Equal(t, http.StatusOK, rec.Code)
	assert.Empty(t, seen.Get(UserIDHeader))
	assert.Empty(t, seen.Get(SignatureHeader))
}

func TestSignIdentity_IsDeterministicAndKeyed(t *testing.T) {
	assert.Equal(t, SignIdentity("k", "u"), SignIdentity("k", "u"))
	assert.NotEqual(t, SignIdentity("k", "u"), SignIdentity("other", "u"))
	assert.NotEqual(t, SignIdentity("k", "u"), SignIdentity("k", "v"))
}
