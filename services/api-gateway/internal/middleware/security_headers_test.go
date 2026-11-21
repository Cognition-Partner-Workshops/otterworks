package middleware

import (
	"crypto/tls"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestSecurityHeaders(t *testing.T) {
	for _, status := range []int{200, 204, 401, 404, 429, 500, 502} {
		t.Run(http.StatusText(status), func(t *testing.T) {
			handler := SecurityHeaders(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(status)
			}))
			for _, secure := range []bool{false, true} {
				req := httptest.NewRequest(http.MethodGet, "/api/v1/documents/", nil)
				if secure {
					req.TLS = &tls.ConnectionState{}
				}
				rec := httptest.NewRecorder()
				handler.ServeHTTP(rec, req)
				assert.Equal(t, status, rec.Code)
				assert.Equal(t, "nosniff", rec.Header().Get("X-Content-Type-Options"))
				assert.Equal(t, "DENY", rec.Header().Get("X-Frame-Options"))
				assert.Contains(t, rec.Header().Get("Content-Security-Policy"), "frame-ancestors 'none'")
				assert.Equal(t, "no-referrer", rec.Header().Get("Referrer-Policy"))
				assert.Equal(t, "max-age=31536000", rec.Header().Get("Strict-Transport-Security"))
			}
		})
	}
}
