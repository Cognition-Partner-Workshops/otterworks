package proxy

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"net/http"
)

const (
	// UserIDHeader carries the authenticated user's id to backend services.
	UserIDHeader = "X-User-ID"
	// SignatureHeader carries hex(HMAC-SHA256(INTERNAL_AUTH_SECRET, X-User-ID)).
	// A backend verifies it before trusting X-User-ID, so the header is only
	// meaningful when it was set by a gateway holding the shared secret.
	SignatureHeader = "X-Gateway-Signature"
)

// SignIdentity returns the attestation signature for userID.
func SignIdentity(secret, userID string) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(userID))
	return hex.EncodeToString(mac.Sum(nil))
}

// AttestIdentity sets the identity header and its signature on an outbound request.
func AttestIdentity(h http.Header, secret, userID string) {
	h.Set(UserIDHeader, userID)
	h.Set(SignatureHeader, SignIdentity(secret, userID))
}
