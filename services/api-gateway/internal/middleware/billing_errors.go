package middleware

import (
	"encoding/json"
	"net/http"
	"strings"
)

// WriteBillingError returns false without writing anything for non-billing paths.
func WriteBillingError(w http.ResponseWriter, r *http.Request, status int, code, message string) bool {
	if r.URL.Path != "/api/v1/billing" && !strings.HasPrefix(r.URL.Path, "/api/v1/billing/") {
		return false
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"error": map[string]string{"code": code, "message": message},
	})
	return true
}
