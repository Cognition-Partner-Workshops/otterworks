package proxy

import (
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/require"

	"github.com/Cognition-Partner-Workshops/otterworks/services/api-gateway/internal/middleware"
)

func TestProxyDirectorRemovesSpoofedUserID(t *testing.T) {
	const secret = "proxy-test-jwt-secret"
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.WriteString(w, r.Header.Get("X-User-ID"))
	}))
	defer backend.Close()

	router := NewRouter(RouterConfig{
		Routes: []Route{{
			Prefix:    "/api/v1/search",
			TargetURL: backend.URL,
		}},
		CBManager: NewCircuitBreakerManager(CircuitBreakerConfig{
			MaxRequests:  1,
			Interval:     time.Minute,
			Timeout:      time.Second,
			FailureRatio: 0.5,
		}),
		Logger: zerolog.Nop(),
	})
	tests := []struct {
		name     string
		token    string
		wantUser string
	}{
		{
			name:     "removes inbound user id without claims",
			wantUser: "",
		},
		{
			name:     "uses authenticated subject instead of inbound user id",
			token:    proxyTestToken(t, secret, "authenticated-user"),
			wantUser: "authenticated-user",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, "/api/v1/search/", nil)
			req.Header.Set("X-User-ID", "spoofed-user")
			var testHandler http.Handler = router
			if tt.token != "" {
				req.Header.Set("Authorization", "Bearer "+tt.token)
				req.Header.Set("Connection", "X-User-ID")
				testHandler = middleware.JWTAuth(middleware.JWTConfig{
					Secret:     secret,
					PrefixPath: middleware.DefaultPrefixPaths(),
				})(router)
			}

			rec := httptest.NewRecorder()
			testHandler.ServeHTTP(rec, req)

			require.Equal(t, http.StatusOK, rec.Code)
			require.Equal(t, tt.wantUser, rec.Body.String())
		})
	}
}

func proxyTestToken(t *testing.T, secret, subject string) string {
	t.Helper()
	claims := middleware.JWTClaims{
		RegisteredClaims: jwt.RegisteredClaims{
			Subject:   subject,
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(time.Hour)),
		},
	}
	token, err := jwt.NewWithClaims(jwt.SigningMethodHS256, claims).SignedString([]byte(secret))
	require.NoError(t, err)
	return token
}
