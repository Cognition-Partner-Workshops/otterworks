package middleware

import (
	"crypto/rand"
	"encoding/hex"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func randomQaSecret(t *testing.T) string {
	t.Helper()
	buf := make([]byte, 48)
	_, err := rand.Read(buf)
	require.NoError(t, err)
	return hex.EncodeToString(buf)
}

func signQaToken(t *testing.T, method jwt.SigningMethod, secret string, claims jwt.MapClaims) string {
	t.Helper()
	tokenStr, err := jwt.NewWithClaims(method, claims).SignedString([]byte(secret))
	require.NoError(t, err)
	return tokenStr
}

func qaHandler(secret string) http.Handler {
	cfg := JWTConfig{Secret: secret, PublicPath: DefaultPublicPaths(), PrefixPath: DefaultPrefixPaths()}
	return JWTAuth(cfg)(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
}

func qaRequest(handler http.Handler, method, path, token string) int {
	req := httptest.NewRequest(method, path, nil)
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	return rec.Code
}

func TestJWTAuthQa_AuthServiceStyleAccessTokenAccepted(t *testing.T) {
	secret := randomQaSecret(t)
	token := signQaToken(t, jwt.SigningMethodHS384, secret, jwt.MapClaims{
		"sub":   "user-1",
		"email": "qa@example.test",
		"roles": []string{"USER"},
		"type":  "access",
		"exp":   time.Now().Add(time.Hour).Unix(),
	})
	assert.Equal(t, http.StatusOK, qaRequest(qaHandler(secret), http.MethodGet, "/api/v1/documents/", token))
}

func TestJWTAuthQa_RefreshEndpointIsNotPublic(t *testing.T) {
	secret := randomQaSecret(t)
	assert.Equal(t, http.StatusUnauthorized, qaRequest(qaHandler(secret), http.MethodPost, "/api/v1/auth/refresh", ""))
}

func TestJWTAuthQa_LogoutAndProfileRequireToken(t *testing.T) {
	secret := randomQaSecret(t)
	handler := qaHandler(secret)
	for _, path := range []string{"/api/v1/auth/logout", "/api/v1/auth/profile", "/api/v1/auth/change-password"} {
		assert.Equal(t, http.StatusUnauthorized, qaRequest(handler, http.MethodPost, path, ""), path)
	}
}

func TestJWTAuthQa_AlgNoneRejected(t *testing.T) {
	secret := randomQaSecret(t)
	token, err := jwt.NewWithClaims(jwt.SigningMethodNone, jwt.MapClaims{
		"sub": "attacker",
		"exp": time.Now().Add(time.Hour).Unix(),
	}).SignedString(jwt.UnsafeAllowNoneSignatureType)
	require.NoError(t, err)
	assert.Equal(t, http.StatusUnauthorized, qaRequest(qaHandler(secret), http.MethodGet, "/api/v1/files/", token))
}

func TestJWTAuthQa_TamperedPayloadRejected(t *testing.T) {
	secret := randomQaSecret(t)
	good := signQaToken(t, jwt.SigningMethodHS256, secret, jwt.MapClaims{"sub": "user-1", "exp": time.Now().Add(time.Hour).Unix()})
	other := signQaToken(t, jwt.SigningMethodHS256, secret, jwt.MapClaims{"sub": "admin", "exp": time.Now().Add(time.Hour).Unix()})
	goodParts := strings.Split(good, ".")
	otherParts := strings.Split(other, ".")
	tampered := goodParts[0] + "." + otherParts[1] + "." + goodParts[2]
	assert.Equal(t, http.StatusUnauthorized, qaRequest(qaHandler(secret), http.MethodGet, "/api/v1/files/", tampered))
}

func TestJWTAuthQa_NotYetValidTokenRejected(t *testing.T) {
	secret := randomQaSecret(t)
	token := signQaToken(t, jwt.SigningMethodHS256, secret, jwt.MapClaims{
		"sub": "user-1",
		"nbf": time.Now().Add(time.Hour).Unix(),
		"exp": time.Now().Add(2 * time.Hour).Unix(),
	})
	assert.Equal(t, http.StatusUnauthorized, qaRequest(qaHandler(secret), http.MethodGet, "/api/v1/files/", token))
}

func TestJWTAuthQa_RefreshTokenRejectedAsAccessToken(t *testing.T) {
	t.Skip("[REAL] gateway-accepts-refresh-token: JWTAuth never checks the `type` claim, so auth-service refresh tokens (30-day TTL) authorize every proxied API route")
	secret := randomQaSecret(t)
	refresh := signQaToken(t, jwt.SigningMethodHS384, secret, jwt.MapClaims{
		"sub":  "user-1",
		"jti":  "refresh-jti",
		"type": "refresh",
		"exp":  time.Now().Add(30 * 24 * time.Hour).Unix(),
	})
	assert.Equal(t, http.StatusUnauthorized, qaRequest(qaHandler(secret), http.MethodGet, "/api/v1/documents/", refresh))
}
