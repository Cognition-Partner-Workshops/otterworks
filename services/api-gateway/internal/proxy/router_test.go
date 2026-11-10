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

const routerTestSecret = "router-test-secret"

// notification-service identifies the caller solely by X-User-ID and returns 400 without it.
func TestRouter_ForwardsJWTSubjectAsUserIDHeader(t *testing.T) {
	var gotUserID, gotQuery string
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotUserID = r.Header.Get("X-User-ID")
		gotQuery = r.URL.RawQuery
		w.WriteHeader(http.StatusOK)
	}))
	defer backend.Close()

	router := NewRouter(RouterConfig{
		Routes:    []Route{{Prefix: "/api/v1/notifications", TargetURL: backend.URL}},
		CBManager: NewCircuitBreakerManager(defaultTestConfig()),
		Logger:    zerolog.Nop(),
	})
	handler := middleware.JWTAuth(middleware.JWTConfig{
		Secret:              routerTestSecret,
		ProtectedPrefixPath: []string{"/api/v1/notifications"},
	})(router)

	token, err := jwt.NewWithClaims(jwt.SigningMethodHS256, middleware.JWTClaims{
		RegisteredClaims: jwt.RegisteredClaims{
			Subject:   "user-123",
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(time.Hour)),
		},
	}).SignedString([]byte(routerTestSecret))
	require.NoError(t, err)

	for _, path := range []string{
		"/api/v1/notifications/unread-count",
		"/api/v1/notifications?page=1&pageSize=20",
	} {
		gotUserID, gotQuery = "", ""
		req := httptest.NewRequest(http.MethodGet, path, nil)
		req.Header.Set("Authorization", "Bearer "+token)
		req.Header.Set("X-User-ID", "spoofed")
		rec := httptest.NewRecorder()

		handler.ServeHTTP(rec, req)

		assert.Equal(t, http.StatusOK, rec.Code, path)
		assert.Equal(t, "user-123", gotUserID, path)
		assert.Equal(t, req.URL.RawQuery, gotQuery, path)
	}
}
