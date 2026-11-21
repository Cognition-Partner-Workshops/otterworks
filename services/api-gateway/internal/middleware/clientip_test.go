package middleware

import (
	"net"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/require"
)

func mustTrustedProxyNetwork(t *testing.T, value string) []*net.IPNet {
	t.Helper()
	_, network, err := net.ParseCIDR(value)
	require.NoError(t, err)
	return []*net.IPNet{network}
}

func TestClientIPUntrustedPeerIgnoresForwardingHeaders(t *testing.T) {
	handler := ClientIP(mustTrustedProxyNetwork(t, "10.0.0.0/8"))(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(r.RemoteAddr))
	}))

	req := httptest.NewRequest(http.MethodGet, "/", nil)
	req.RemoteAddr = "198.51.100.10:1234"
	req.Header.Set("X-Forwarded-For", "203.0.113.20")
	req.Header.Set("X-Real-IP", "203.0.113.21")
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	require.Equal(t, http.StatusOK, rec.Code)
	require.Equal(t, "198.51.100.10", rec.Body.String())
}

func TestClientIPTrustedPeerUsesRightmostUntrustedForwardedIP(t *testing.T) {
	handler := ClientIP(mustTrustedProxyNetwork(t, "10.0.0.0/8"))(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(r.RemoteAddr))
	}))

	req := httptest.NewRequest(http.MethodGet, "/", nil)
	req.RemoteAddr = "10.0.0.2:1234"
	req.Header.Set("X-Forwarded-For", "203.0.113.50, 198.51.100.7, 10.0.0.3")
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	require.Equal(t, "198.51.100.7", rec.Body.String())
}

func TestClientIPTrustedPeerFallsBackToRealIPWhenForwardedChainHasNoClient(t *testing.T) {
	handler := ClientIP(mustTrustedProxyNetwork(t, "10.0.0.0/8"))(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(r.RemoteAddr))
	}))

	req := httptest.NewRequest(http.MethodGet, "/", nil)
	req.RemoteAddr = "10.0.0.2:1234"
	req.Header.Set("X-Forwarded-For", "not-an-ip, 10.0.0.3")
	req.Header.Set("X-Real-IP", "198.51.100.9")
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	require.Equal(t, "198.51.100.9", rec.Body.String())
}

func TestClientIPTrustedPeerFallsBackToPeerForInvalidRealIP(t *testing.T) {
	handler := ClientIP(mustTrustedProxyNetwork(t, "10.0.0.0/8"))(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(r.RemoteAddr))
	}))

	req := httptest.NewRequest(http.MethodGet, "/", nil)
	req.RemoteAddr = "10.0.0.2:1234"
	req.Header.Set("X-Forwarded-For", "10.0.0.3")
	req.Header.Set("X-Real-IP", "not-an-ip")
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	require.Equal(t, "10.0.0.2", rec.Body.String())
}

func TestRateLimiterWithClientIPCannotBeBypassedByRotatingXFF(t *testing.T) {
	rateLimiter := NewRateLimiter(1)
	handler := ClientIP(mustTrustedProxyNetwork(t, "10.0.0.0/8"))(rateLimiter.Handler(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
	})))

	req := httptest.NewRequest(http.MethodGet, "/", nil)
	req.RemoteAddr = "10.0.0.2:1234"
	req.Header.Set("X-Forwarded-For", "203.0.113.10, 198.51.100.7, 10.0.0.3")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	require.Equal(t, http.StatusOK, rec.Code, "first request should be allowed")

	req = httptest.NewRequest(http.MethodGet, "/", nil)
	req.RemoteAddr = "10.0.0.2:1234"
	req.Header.Set("X-Forwarded-For", "203.0.113.11, 198.51.100.7, 10.0.0.3")
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	require.Equal(t, http.StatusTooManyRequests, rec.Code)
}
