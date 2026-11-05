package middleware

import (
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/stretchr/testify/require"
)

func TestBankingSignalsPreserveResponses(t *testing.T) {
	user := JWTClaims{RegisteredClaims: jwt.RegisteredClaims{Subject: "A"}, Roles: []string{"USER"}}
	valid := generateTestToken(t, testSecret, user)
	peer := generateTestToken(t, "peer", user)
	admin := generateTestToken(t, testSecret, JWTClaims{Roles: []string{"aDmIn"}})
	expired := generateTestToken(t, testSecret, JWTClaims{RegisteredClaims: jwt.RegisteredClaims{ExpiresAt: jwt.NewNumericDate(time.Now().Add(-time.Hour))}})
	fallback := generateTestToken(t, testSecret, JWTClaims{UserID: "A"})
	events := map[string][]string{
		"payment_route_call":     {"anonymous", "authenticated"},
		"payment_amount_invalid": {"non_positive", "precision"},
		"auth_id_mismatch":       {"mismatch", "unauthenticated"},
		"admin_route_non_admin":  {"admin_api", "bank_users"},
	}
	for _, tc := range []struct {
		name, method, path, body, token string
		authID                          *string
		want                            []string
	}{
		{name: "anonymous 404", method: "POST", path: "/transaction/fund-transfer", want: []string{"payment_route_call/anonymous"}},
		{name: "authenticated 404", method: "POST", path: "/api/v1/transaction/fund-transfer", token: valid, body: `{"amount":10.50}`, want: []string{"payment_route_call/authenticated"}},
		{name: "peer", method: "PUT", path: "/utility-payment", token: peer, body: `{"amount":"-100000"}`, want: []string{"payment_route_call/authenticated", "payment_amount_invalid/non_positive"}},
		{name: "precision", method: "PATCH", path: "/api/v1/utility-payment", token: valid, body: `{"amount":0.005}`, want: []string{"payment_route_call/authenticated", "payment_amount_invalid/precision"}},
		{name: "zero", method: "POST", path: "/fund-transfer", body: `{"amount":0}`, want: []string{"payment_route_call/anonymous", "payment_amount_invalid/non_positive"}},
		{name: "expired", method: "POST", path: "/fund-transfer", token: expired, want: []string{"payment_route_call/anonymous"}},
		{name: "malformed", method: "POST", path: "/fund-transfer", token: "invalid", want: []string{"payment_route_call/anonymous"}},
		{name: "non JSON", method: "POST", path: "/fund-transfer", body: "not JSON", want: []string{"payment_route_call/anonymous"}},
		{name: "oversized", method: "POST", path: "/fund-transfer", body: `{"amount":0,"padding":"` + strings.Repeat("x", paymentBodyLimit) + `"}`, want: []string{"payment_route_call/anonymous"}},
		{name: "non payment", method: "POST", path: "/unknown", body: `{"amount":-0.005}`},
		{name: "GET ignores amount", method: "GET", path: "/fund-transfer", body: `{"amount":0}`, want: []string{"payment_route_call/anonymous"}},
		{name: "matching ID", method: "GET", path: "/api/v1/documents", token: valid, authID: stringPointer("A")},
		{name: "fallback ID", method: "GET", path: "/api/v1/documents", token: fallback, authID: stringPointer("A")},
		{name: "mismatching ID", method: "GET", path: "/api/v1/documents", token: valid, authID: stringPointer("B"), want: []string{"auth_id_mismatch/mismatch"}},
		{name: "anonymous ID public", method: "GET", path: "/health", authID: stringPointer("B"), want: []string{"auth_id_mismatch/unauthenticated"}},
		{name: "invalid ID token", method: "GET", path: "/unknown", token: "bad", authID: stringPointer("B"), want: []string{"auth_id_mismatch/unauthenticated"}},
		{name: "empty supplied ID", method: "GET", path: "/unknown", token: valid, authID: stringPointer(""), want: []string{"auth_id_mismatch/mismatch"}},
		{name: "admin", method: "GET", path: "/api/v1/admin/users", token: admin},
		{name: "admin bank users", method: "GET", path: "/bank-users", token: admin},
		{name: "ordinary admin call", method: "GET", path: "/api/v1/admin/users", token: valid, want: []string{"admin_route_non_admin/admin_api"}},
		{name: "anonymous admin call", method: "GET", path: "/api/v1/admin/users", want: []string{"admin_route_non_admin/admin_api"}},
		{name: "ordinary bank users", method: "GET", path: "/bank-users", token: valid, want: []string{"admin_route_non_admin/bank_users"}},
		{name: "public bypass bank users", method: "GET", path: "/health/bank-users", want: []string{"admin_route_non_admin/bank_users"}},
	} {
		t.Run(tc.name, func(t *testing.T) {
			cfg := JWTConfig{Secret: testSecret, PeerSecret: "peer", PublicPath: DefaultPublicPaths(), PrefixPath: DefaultPrefixPaths(), ProtectedPrefixPath: []string{"/api/v1/documents", "/api/v1/admin"}}
			next := JWTAuth(cfg)(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				body, err := io.ReadAll(r.Body)
				require.NoError(t, err)
				w.WriteHeader(404)
				_, _ = w.Write(body)
			}))
			request := func() *http.Request {
				r := httptest.NewRequest(tc.method, tc.path, strings.NewReader(tc.body))
				if tc.token != "" {
					r.Header.Set("Authorization", "Bearer "+tc.token)
				}
				if tc.authID != nil {
					r.Header.Set("X-Auth-Id", *tc.authID)
				}
				return r
			}
			control := httptest.NewRecorder()
			next.ServeHTTP(control, request())
			before := map[string]float64{}
			for event, reasons := range events {
				for _, reason := range reasons {
					before[event+"/"+reason] = counterValue(securityEvents.WithLabelValues(event, reason))
				}
			}
			response := httptest.NewRecorder()
			ObserveBankingSignals(cfg)(next).ServeHTTP(response, request())
			require.Equal(t, control.Code, response.Code)
			require.Equal(t, control.Body.String(), response.Body.String())
			require.Equal(t, control.Header(), response.Header())
			for event, reasons := range events {
				for _, reason := range reasons {
					key := event + "/" + reason
					delta := 0.0
					for _, wanted := range tc.want {
						if wanted == key {
							delta++
						}
					}
					require.Equal(t, before[key]+delta, counterValue(securityEvents.WithLabelValues(event, reason)), key)
				}
			}
		})
	}
}

func stringPointer(s string) *string { return &s }

func TestExactPaymentDecimals(t *testing.T) {
	for _, tc := range []struct {
		amount                 string
		nonPositive, precision bool
	}{
		{"10.50", false, false}, {"10.500", false, true}, {"0", true, false},
		{"-100000", true, false}, {"-0.005", true, true}, {"5e-3", false, true},
		{"500e-2", false, false}, {"0.005e1", false, false}, {"-0", true, false},
		{"1e-99999999999999999999999", false, true}, {"1e99999999999999999999999", false, false},
		{"0.000000000000000000000001", false, true}, {"9007199254740993.01", false, false},
		{"null", false, false}, {"NaN", false, false}, {"", false, false}, {".", false, false},
	} {
		t.Run(tc.amount, func(t *testing.T) {
			nonPositive, precision := invalidPaymentAmount(tc.amount)
			require.Equal(t, tc.nonPositive, nonPositive)
			require.Equal(t, tc.precision, precision)
		})
	}
}

type failingPaymentBody struct{ closed bool }

func (*failingPaymentBody) Read(p []byte) (int, error) {
	return copy(p, `{"amount":0}`), io.ErrUnexpectedEOF
}
func (b *failingPaymentBody) Close() error { b.closed = true; return nil }

func TestPaymentBodyReadErrorPreserved(t *testing.T) {
	body := &failingPaymentBody{}
	r := httptest.NewRequest("POST", "/fund-transfer", nil)
	r.Body = body
	counter := securityEvents.WithLabelValues("payment_amount_invalid", "non_positive")
	before := counterValue(counter)
	observePaymentAmount(r)
	data, err := io.ReadAll(r.Body)
	require.True(t, errors.Is(err, io.ErrUnexpectedEOF))
	require.Equal(t, `{"amount":0}`, string(data))
	require.Equal(t, before, counterValue(counter))
	require.NoError(t, r.Body.Close())
	require.True(t, body.closed)
}

func TestBankingObservationBeforeLimiter(t *testing.T) {
	limiter := &RateLimiter{buckets: make(map[string]*TokenBucket), rps: 0, now: time.Now}
	counter := securityEvents.WithLabelValues("payment_route_call", "anonymous")
	before := counterValue(counter)
	h := ObserveBankingSignals(JWTConfig{})(limiter.Handler(http.NotFoundHandler()))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, httptest.NewRequest("POST", "/fund-transfer", nil))
	require.Equal(t, 429, w.Code)
	require.Equal(t, before+1, counterValue(counter))
}
