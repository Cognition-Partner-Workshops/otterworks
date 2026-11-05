package middleware

import (
	"bytes"
	"encoding/json"
	"io"
	"math/big"
	"net/http"
	"regexp"
	"strings"
)

const paymentBodyLimit = 64 * 1024

var decimalPattern = regexp.MustCompile(`^([+-]?)([0-9]*)(?:\.([0-9]*))?(?:[eE]([+-]?[0-9]+))?$`)

type observedBody struct {
	io.Reader
	io.Closer
}

type observedReadError struct{ err error }

func (r *observedReadError) Read([]byte) (int, error) {
	if r.err == nil {
		return 0, io.EOF
	}
	err := r.err
	r.err = nil
	return 0, err
}

func ObserveBankingSignals(cfg JWTConfig) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			payment := strings.Contains(r.URL.Path, "/fund-transfer") || strings.Contains(r.URL.Path, "/utility-payment")
			adminAPI := strings.HasPrefix(r.URL.Path, "/api/v1/admin")
			bankUsers := strings.Contains(r.URL.Path, "/bank-users")
			authIDs, hasAuthID := r.Header[http.CanonicalHeaderKey("X-Auth-Id")]
			if payment || adminAPI || bankUsers || hasAuthID {
				var claims *JWTClaims
				if token := extractBearerToken(r); token != "" {
					var err error
					claims, err = validateToken(token, cfg.Secret)
					if err != nil && cfg.PeerSecret != "" {
						claims, err = validateToken(token, cfg.PeerSecret)
					}
					if err != nil {
						claims = nil
					}
				}
				if payment {
					reason := "anonymous"
					if claims != nil {
						reason = "authenticated"
					}
					securityEvents.WithLabelValues("payment_route_call", reason).Inc()
					if r.Method == http.MethodPost || r.Method == http.MethodPut || r.Method == http.MethodPatch {
						observePaymentAmount(r)
					}
				}
				if hasAuthID {
					if claims == nil {
						securityEvents.WithLabelValues("auth_id_mismatch", "unauthenticated").Inc()
					} else {
						subject := claims.Subject
						if subject == "" {
							subject = claims.UserID
						}
						for _, id := range authIDs {
							if id != subject {
								securityEvents.WithLabelValues("auth_id_mismatch", "mismatch").Inc()
								break
							}
						}
					}
				}
				admin := false
				if claims != nil {
					for _, role := range claims.Roles {
						admin = admin || strings.EqualFold(role, "ADMIN")
					}
				}
				if !admin {
					if adminAPI {
						securityEvents.WithLabelValues("admin_route_non_admin", "admin_api").Inc()
					}
					if bankUsers {
						securityEvents.WithLabelValues("admin_route_non_admin", "bank_users").Inc()
					}
				}
			}
			next.ServeHTTP(w, r)
		})
	}
}

func observedJSONBody(r *http.Request) map[string]json.RawMessage {
	if r.Body == nil {
		return nil
	}
	body := r.Body
	prefix, err := io.ReadAll(io.LimitReader(body, paymentBodyLimit+1))
	readers := []io.Reader{bytes.NewReader(prefix)}
	if err != nil {
		readers = append(readers, &observedReadError{err: err})
	}
	readers = append(readers, body)
	r.Body = &observedBody{Reader: io.MultiReader(readers...), Closer: body}
	if err != nil || len(prefix) > paymentBodyLimit {
		return nil
	}
	var object map[string]json.RawMessage
	if json.Unmarshal(prefix, &object) != nil {
		return nil
	}
	return object
}

func observePaymentAmount(r *http.Request) {
	object := observedJSONBody(r)
	raw, exists := object["amount"]
	if !exists {
		return
	}
	amount := string(raw)
	if len(raw) > 0 && raw[0] == '"' {
		if json.Unmarshal(raw, &amount) != nil {
			return
		}
	}
	nonPositive, precision := invalidPaymentAmount(strings.TrimSpace(amount))
	if nonPositive {
		securityEvents.WithLabelValues("payment_amount_invalid", "non_positive").Inc()
	}
	if precision {
		securityEvents.WithLabelValues("payment_amount_invalid", "precision").Inc()
	}
}

func invalidPaymentAmount(amount string) (bool, bool) {
	parts := decimalPattern.FindStringSubmatch(amount)
	if parts == nil || parts[2]+parts[3] == "" {
		return false, false
	}
	zero := strings.Trim(parts[2]+parts[3], "0") == ""
	exponent := new(big.Int)
	if parts[4] != "" {
		exponent.SetString(parts[4], 10)
	}
	scale := big.NewInt(int64(len(parts[3])))
	scale.Sub(scale, exponent)
	return zero || parts[1] == "-", scale.Cmp(big.NewInt(2)) > 0
}
