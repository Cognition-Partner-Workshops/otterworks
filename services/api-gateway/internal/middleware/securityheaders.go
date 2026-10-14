package middleware

import "net/http"

// securityHeaders are the browser hardening headers the gateway sets on every
// response. The gateway only serves JSON APIs and websocket upgrades, so the
// CSP forbids loading or framing anything.
var securityHeaders = map[string]string{
	"X-Content-Type-Options":    "nosniff",
	"X-Frame-Options":           "DENY",
	"Content-Security-Policy":   "default-src 'none'; frame-ancestors 'none'",
	"Referrer-Policy":           "no-referrer",
	"Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}

// SecurityHeaders sets the baseline security headers before any other handler
// runs, so short-circuited responses (429, 401, CORS preflight, 404) carry them too.
func SecurityHeaders(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		h := w.Header()
		for name, value := range securityHeaders {
			h.Set(name, value)
		}
		next.ServeHTTP(w, r)
	})
}

// StripSecurityHeaders removes a backend's own copies of the gateway-owned
// security headers so a proxied response carries exactly one value for each.
// Without this the reverse proxy appends the backend's values to the gateway's,
// and browsers ignore conflicting values such as "DENY, SAMEORIGIN".
func StripSecurityHeaders(h http.Header) {
	for name := range securityHeaders {
		h.Del(name)
	}
}
