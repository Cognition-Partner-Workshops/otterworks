package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/require"

	"github.com/Cognition-Partner-Workshops/otterworks/services/api-gateway/internal/config"
	"github.com/Cognition-Partner-Workshops/otterworks/services/api-gateway/internal/middleware"
	"github.com/Cognition-Partner-Workshops/otterworks/services/api-gateway/internal/proxy"
)

func TestODLRouteRequiresJWTAndPreservesPath(t *testing.T) {
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		require.Equal(t, "/api/v1/odl/customers", r.URL.Path)
		require.Equal(t, "C0000003", r.URL.Query().Get("db2_cust_no"))
		require.Equal(t, "reader", r.Header.Get("X-User-ID"))
		w.WriteHeader(http.StatusOK)
	}))
	defer backend.Close()
	t.Setenv("ODL_SERVICE_URL", backend.URL)
	var routes []proxy.Route
	for prefix, target := range config.Load().ServiceRoutes() {
		routes = append(routes, proxy.Route{Prefix: prefix, TargetURL: target})
	}
	const secret = "odl-test-signing-key"
	handler := middleware.JWTAuth(middleware.JWTConfig{
		Secret: secret, PublicPath: middleware.DefaultPublicPaths(),
		PrefixPath: middleware.DefaultPrefixPaths(), ProtectedPrefixPath: routePrefixes(routes),
	})(proxy.NewRouter(proxy.RouterConfig{
		Routes: routes, Logger: zerolog.Nop(),
		CBManager: proxy.NewCircuitBreakerManager(proxy.CircuitBreakerConfig{}),
	}))
	for _, token := range []string{"", "invalid"} {
		for _, path := range []string{"/api/v1/odl", "/api/v1/odl/customers", "/api/v1/odl/parity/latest", "/api/v1/odl/parity/run.csv"} {
			req := httptest.NewRequest(http.MethodGet, path, nil)
			if token != "" {
				req.Header.Set("Authorization", "Bearer "+token)
			}
			rec := httptest.NewRecorder()
			handler.ServeHTTP(rec, req)
			require.Equal(t, http.StatusUnauthorized, rec.Code)
		}
	}
	token, err := jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.RegisteredClaims{
		Subject: "reader", ExpiresAt: jwt.NewNumericDate(time.Now().Add(time.Minute)),
	}).SignedString([]byte(secret))
	require.NoError(t, err)
	req := httptest.NewRequest(http.MethodGet, "/api/v1/odl/customers?db2_cust_no=C0000003", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	require.Equal(t, http.StatusOK, rec.Code)
}
