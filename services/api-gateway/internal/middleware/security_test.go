package middleware

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/prometheus/client_golang/prometheus"
	dto "github.com/prometheus/client_model/go"
	"github.com/stretchr/testify/require"
)

func counterValue(c prometheus.Counter) float64 {
	m := &dto.Metric{}
	_ = c.Write(m)
	return m.GetCounter().GetValue()
}

func TestSecurityJWTRejections(t *testing.T) {
	expired := generateTestToken(t, testSecret, JWTClaims{RegisteredClaims: jwt.RegisteredClaims{ExpiresAt: jwt.NewNumericDate(time.Now().Add(-time.Hour))}})
	bad := generateTestToken(t, "wrong", JWTClaims{})
	unsigned, err := jwt.NewWithClaims(jwt.SigningMethodNone, JWTClaims{}).SignedString(jwt.UnsafeAllowNoneSignatureType)
	require.NoError(t, err)
	for _, tc := range []struct{ token, reason string }{
		{"", "missing"}, {"garbage", "malformed"}, {expired, "expired"}, {bad, "bad_signature"}, {unsigned, "alg_not_allowed"},
	} {
		t.Run(tc.reason, func(t *testing.T) {
			c := securityEvents.WithLabelValues("jwt_rejected", tc.reason)
			before := counterValue(c)
			r := httptest.NewRequest("GET", "/private", nil)
			if tc.token != "" {
				r.Header.Set("Authorization", "Bearer "+tc.token)
			}
			w := httptest.NewRecorder()
			JWTAuth(JWTConfig{Secret: testSecret})(http.HandlerFunc(func(http.ResponseWriter, *http.Request) { t.Fatal("rejected token reached backend") })).ServeHTTP(w, r)
			require.Equal(t, 401, w.Code)
			require.Equal(t, before+1, counterValue(c))
		})
	}
}

func TestIdentityObservationPreservesHeadersAndPeerJWT(t *testing.T) {
	c := securityEvents.WithLabelValues("identity_header_injected", "client_supplied")
	before := counterValue(c)
	token := generateTestToken(t, "peer", JWTClaims{})
	bad := securityEvents.WithLabelValues("jwt_rejected", "bad_signature")
	rejections := counterValue(bad)
	handler := JWTAuth(JWTConfig{Secret: testSecret, PeerSecret: "peer"})(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		require.Equal(t, "injected", r.Header.Get("X-User-ID"))
		require.Equal(t, "admin", r.Header.Get("X-User-Roles"))
		w.WriteHeader(204)
	}))
	for _, supplied := range []bool{false, true} {
		r := httptest.NewRequest("GET", "/private", nil)
		r.Header.Set("Authorization", "Bearer "+token)
		if supplied {
			r.Header.Set("X-User-ID", "injected")
			r.Header.Set("X-User-Roles", "admin")
			w := httptest.NewRecorder()
			handler.ServeHTTP(w, r)
			require.Equal(t, 204, w.Code)
		} else {
			JWTAuth(JWTConfig{PublicPath: []string{"/private"}})(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {})).ServeHTTP(httptest.NewRecorder(), r)
		}
	}
	require.Equal(t, before+1, counterValue(c))
	require.Equal(t, rejections, counterValue(bad))
}

func TestLoginMetrics(t *testing.T) {
	for _, tc := range []struct {
		status  int
		outcome string
	}{{200, "success"}, {204, "success"}, {401, "failure"}, {400, "failure"}, {429, "throttled"}, {500, "error"}, {302, "error"}} {
		c := authLogin.WithLabelValues(tc.outcome)
		before := counterValue(c)
		h := Metrics(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(tc.status) }))
		h.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("POST", "/api/v1/auth/login", nil))
		require.Equal(t, before+1, counterValue(c))
		h.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", "/api/v1/auth/login", nil))
		require.Equal(t, before+1, counterValue(c))
	}
}

func TestLimiterObservation(t *testing.T) {
	rl := &RateLimiter{buckets: make(map[string]*TokenBucket), rps: 1, now: func() time.Time { return time.Unix(100, 0) }}
	clients, rejected := counterValue(limiterClients), counterValue(limiterRejections)
	h := Metrics(rl.Handler(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(204) })))
	for i, ip := range []string{"192.0.2.1", "192.0.2.1", "192.0.2.2"} {
		r := httptest.NewRequest("POST", "/api/v1/auth/login", nil)
		r.RemoteAddr = ip
		w := httptest.NewRecorder()
		h.ServeHTTP(w, r)
		if i == 1 {
			require.Equal(t, 429, w.Code)
		} else {
			require.Equal(t, 204, w.Code)
		}
	}
	require.Equal(t, clients+2, counterValue(limiterClients))
	require.Equal(t, rejected+1, counterValue(limiterRejections))
}
