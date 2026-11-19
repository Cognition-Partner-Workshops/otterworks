package proxy

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestBillingGatewayErrors(t *testing.T) {
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t.Error("unavailable backend should not receive a request")
	}))
	backend.Close()
	for _, prefix := range []string{"/api/v1/billing", "/api/v1/billingX", "/api/v1/files"} {
		for _, failure := range []string{"proxy", "circuit", "not_found"} {
			t.Run(prefix+"/"+failure, func(t *testing.T) {
				manager := NewCircuitBreakerManager(CircuitBreakerConfig{Timeout: time.Minute})
				routes := []Route{{Prefix: prefix, TargetURL: backend.URL}}
				status, code, message := http.StatusBadGateway, "internal", "service unavailable"
				want := fmt.Sprintf("{\"error\":\"service unavailable\",\"target\":%q}\n", prefix)
				if failure == "circuit" {
					manager.Get(prefix).setState(StateOpen, time.Now())
					status, message = http.StatusServiceUnavailable, "service temporarily unavailable"
					want = fmt.Sprintf("{\"error\":\"service temporarily unavailable\",\"reason\":\"circuit breaker open\",\"service\":%q}\n", prefix)
				}
				if failure == "not_found" {
					routes = nil
					status, code, message = http.StatusNotFound, "not_found", "route not found"
					want = "{\"error\":\"route not found\"}\n"
				}
				if prefix == "/api/v1/billing" {
					want = fmt.Sprintf("{\"error\":{\"code\":%q,\"message\":%q}}\n", code, message)
				}
				router := NewRouter(RouterConfig{Routes: routes, CBManager: manager, Logger: zerolog.Nop()})
				rec := httptest.NewRecorder()
				router.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, prefix+"/plans", nil))
				assert.Equal(t, status, rec.Code)
				assert.Equal(t, "application/json", rec.Header().Get("Content-Type"))
				assert.Equal(t, want, rec.Body.String())
			})
		}
	}
}
