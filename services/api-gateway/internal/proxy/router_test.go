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

// newTestProxy returns a router proxying /api/v1/test to a backend that echoes
// the identity headers it received, plus a function to read what was captured.
func newTestProxy(t *testing.T) (http.Handler, func() http.Header) {
	t.Helper()
	var captured http.Header
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		captured = r.Header.Clone()
		w.WriteHeader(http.StatusOK)
	}))
	t.Cleanup(backend.Close)

	router := NewRouter(RouterConfig{
		Routes: []Route{{Prefix: "/api/v1/test", TargetURL: backend.URL}},
		CBManager: NewCircuitBreakerManager(CircuitBreakerConfig{
			MaxRequests:  1,
			Interval:     time.Minute,
			Timeout:      time.Minute,
			FailureRatio: 0.5,
		}),
		Logger: zerolog.Nop(),
	})
	return router, func() http.Header { return captured }
}

func withClaims(req *http.Request, claims *middleware.JWTClaims) *http.Request {
	// Run the request through JWTAuth so the claims land in the context the
	// same way they do in production, rather than reaching into the private key.
	const secret = "router-test-secret"
	tokenStr, err := jwt.NewWithClaims(jwt.SigningMethodHS256, claims).SignedString([]byte(secret))
	if err != nil {
		panic(err)
	}
	req.Header.Set("Authorization", "Bearer "+tokenStr)
	var out *http.Request
	middleware.JWTAuth(middleware.JWTConfig{Secret: secret})(http.HandlerFunc(func(_ http.ResponseWriter, r *http.Request) {
		out = r
	})).ServeHTTP(httptest.NewRecorder(), req)
	if out == nil {
		panic("JWTAuth rejected the test token")
	}
	return out
}

func TestProxyDirector_StripsClientSuppliedIdentityHeadersWithoutClaims(t *testing.T) {
	router, captured := newTestProxy(t)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/test/anything", nil)
	req.Header.Set(HeaderUserID, "spoofed-admin-0000")
	req.Header.Set(HeaderUserRoles, "ADMIN")
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	require.Equal(t, http.StatusOK, rec.Code)
	assert.Empty(t, captured().Values(HeaderUserID), "client X-User-ID must not reach the backend")
	assert.Empty(t, captured().Values(HeaderUserRoles), "client X-User-Roles must not reach the backend")
}

func TestProxyDirector_OverwritesClientIdentityHeadersFromClaims(t *testing.T) {
	router, captured := newTestProxy(t)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/test/anything", nil)
	req.Header.Set(HeaderUserID, "spoofed-admin-0000")
	req.Header.Set(HeaderUserRoles, "ADMIN")
	req = withClaims(req, &middleware.JWTClaims{
		Roles:            []string{"USER"},
		RegisteredClaims: jwt.RegisteredClaims{Subject: "11111111-1111-1111-1111-111111111111"},
	})
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	require.Equal(t, http.StatusOK, rec.Code)
	assert.Equal(t, []string{"11111111-1111-1111-1111-111111111111"}, captured().Values(HeaderUserID))
	assert.Equal(t, []string{"USER"}, captured().Values(HeaderUserRoles))
}

func TestProxyDirector_FallsBackToUserIDClaimAndJoinsRoles(t *testing.T) {
	router, captured := newTestProxy(t)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/test/anything", nil)
	req = withClaims(req, &middleware.JWTClaims{
		UserID: "22222222-2222-2222-2222-222222222222",
		Roles:  []string{"ADMIN", "USER"},
	})
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	require.Equal(t, http.StatusOK, rec.Code)
	assert.Equal(t, "22222222-2222-2222-2222-222222222222", captured().Get(HeaderUserID))
	assert.Equal(t, "ADMIN,USER", captured().Get(HeaderUserRoles))
}
