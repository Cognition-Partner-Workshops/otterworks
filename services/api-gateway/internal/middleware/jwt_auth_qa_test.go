package middleware

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func qaGatewayConfig() JWTConfig {
	return JWTConfig{
		Secret:              testSecret,
		PublicPath:          DefaultPublicPaths(),
		PrefixPath:          DefaultPrefixPaths(),
		ProtectedPrefixPath: []string{"/api/v1/auth", "/api/v1/files", "/api/v1/documents"},
	}
}

func qaServe(cfg JWTConfig, method, path, authHeader string) (*httptest.ResponseRecorder, bool) {
	reached := false
	handler := JWTAuth(cfg)(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		reached = true
		w.WriteHeader(http.StatusOK)
	}))
	req := httptest.NewRequest(method, path, nil)
	if authHeader != "" {
		req.Header.Set("Authorization", authHeader)
	}
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	return rec, reached
}

func qaSignMap(t *testing.T, method jwt.SigningMethod, key interface{}, claims jwt.MapClaims) string {
	t.Helper()
	tokenStr, err := jwt.NewWithClaims(method, claims).SignedString(key)
	require.NoError(t, err)
	return tokenStr
}

func qaAuthServiceClaims(tokenType string, expiresIn time.Duration) jwt.MapClaims {
	now := time.Now()
	return jwt.MapClaims{
		"sub":   "11111111-2222-3333-4444-555555555555",
		"email": "qa@otterworks.dev",
		"name":  "QA",
		"roles": []string{"USER"},
		"type":  tokenType,
		"iat":   now.Unix(),
		"exp":   now.Add(expiresIn).Unix(),
	}
}

func TestQA_AuthServiceAccessTokenIsAcceptedAndClaimsPropagate(t *testing.T) {
	tokenStr := qaSignMap(t, jwt.SigningMethodHS256, []byte(testSecret), qaAuthServiceClaims("access", time.Hour))
	var captured *JWTClaims
	handler := JWTAuth(qaGatewayConfig())(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		captured = GetJWTClaims(r.Context())
		w.WriteHeader(http.StatusOK)
	}))
	req := httptest.NewRequest(http.MethodGet, "/api/v1/auth/profile", nil)
	req.Header.Set("Authorization", "Bearer "+tokenStr)
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	assert.Equal(t, http.StatusOK, rec.Code)
	require.NotNil(t, captured)
	assert.Equal(t, "11111111-2222-3333-4444-555555555555", captured.Subject)
	assert.Equal(t, "qa@otterworks.dev", captured.Email)
	assert.Equal(t, []string{"USER"}, captured.Roles)
}

func TestQA_HS512TokensFromAuthServiceAreAccepted(t *testing.T) {
	longSecret := "test-jwt-secret-otterworks-must-be-at-least-64-bytes-long-for-hs512-signing!!"
	cfg := qaGatewayConfig()
	cfg.Secret = longSecret
	tokenStr := qaSignMap(t, jwt.SigningMethodHS512, []byte(longSecret), qaAuthServiceClaims("access", time.Hour))
	rec, reached := qaServe(cfg, http.MethodGet, "/api/v1/files/list", "Bearer "+tokenStr)
	assert.Equal(t, http.StatusOK, rec.Code)
	assert.True(t, reached)
}

func TestQA_LoginAndRegisterArePublicForAnyMethod(t *testing.T) {
	for _, path := range []string{"/api/v1/auth/login", "/api/v1/auth/register"} {
		for _, method := range []string{http.MethodPost, http.MethodOptions} {
			rec, reached := qaServe(qaGatewayConfig(), method, path, "")
			assert.Equal(t, http.StatusOK, rec.Code, "%s %s", method, path)
			assert.True(t, reached)
		}
	}
}

func TestQA_AuthEndpointsOtherThanLoginRegisterRequireToken(t *testing.T) {
	for _, path := range []string{
		"/api/v1/auth/profile",
		"/api/v1/auth/logout",
		"/api/v1/auth/refresh",
		"/api/v1/auth/change-password",
		"/api/v1/auth/users",
		"/api/v1/auth/login/../profile",
		"/api/v1/auth/register/extra",
	} {
		rec, reached := qaServe(qaGatewayConfig(), http.MethodPost, path, "")
		assert.Equal(t, http.StatusUnauthorized, rec.Code, path)
		assert.False(t, reached, path)
	}
}

func TestQA_UnauthorizedResponseIsJSONWithoutTokenEcho(t *testing.T) {
	rec, _ := qaServe(qaGatewayConfig(), http.MethodGet, "/api/v1/auth/profile", "Bearer secret-garbage-value")
	assert.Equal(t, http.StatusUnauthorized, rec.Code)
	assert.Equal(t, "application/json", rec.Header().Get("Content-Type"))
	var body map[string]interface{}
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &body))
	assert.NotContains(t, rec.Body.String(), "secret-garbage-value")
}

func TestQA_AlgNoneTokenIsRejected(t *testing.T) {
	tokenStr := qaSignMap(t, jwt.SigningMethodNone, jwt.UnsafeAllowNoneSignatureType, qaAuthServiceClaims("access", time.Hour))
	rec, reached := qaServe(qaGatewayConfig(), http.MethodGet, "/api/v1/files/list", "Bearer "+tokenStr)
	assert.Equal(t, http.StatusUnauthorized, rec.Code)
	assert.False(t, reached)
}

func TestQA_TamperedPayloadIsRejected(t *testing.T) {
	good := qaSignMap(t, jwt.SigningMethodHS256, []byte(testSecret), qaAuthServiceClaims("access", time.Hour))
	forged := qaSignMap(t, jwt.SigningMethodHS256, []byte("attacker-secret"), jwt.MapClaims{
		"sub": "admin", "roles": []string{"ADMIN"}, "exp": time.Now().Add(time.Hour).Unix(),
	})
	goodParts := splitJWT(good)
	forgedParts := splitJWT(forged)
	tampered := goodParts[0] + "." + forgedParts[1] + "." + goodParts[2]
	rec, reached := qaServe(qaGatewayConfig(), http.MethodGet, "/api/v1/files/list", "Bearer "+tampered)
	assert.Equal(t, http.StatusUnauthorized, rec.Code)
	assert.False(t, reached)
}

func TestQA_JustExpiredTokenIsRejected(t *testing.T) {
	tokenStr := qaSignMap(t, jwt.SigningMethodHS256, []byte(testSecret), qaAuthServiceClaims("access", -time.Second))
	rec, reached := qaServe(qaGatewayConfig(), http.MethodGet, "/api/v1/documents", "Bearer "+tokenStr)
	assert.Equal(t, http.StatusUnauthorized, rec.Code)
	assert.False(t, reached)
}

func TestQA_NotYetValidTokenIsRejected(t *testing.T) {
	claims := qaAuthServiceClaims("access", time.Hour)
	claims["nbf"] = time.Now().Add(10 * time.Minute).Unix()
	tokenStr := qaSignMap(t, jwt.SigningMethodHS256, []byte(testSecret), claims)
	rec, reached := qaServe(qaGatewayConfig(), http.MethodGet, "/api/v1/documents", "Bearer "+tokenStr)
	assert.Equal(t, http.StatusUnauthorized, rec.Code)
	assert.False(t, reached)
}

func TestQA_BearerSchemeVariants(t *testing.T) {
	tokenStr := qaSignMap(t, jwt.SigningMethodHS256, []byte(testSecret), qaAuthServiceClaims("access", time.Hour))
	cases := map[string]int{
		"Bearer " + tokenStr: http.StatusOK,
		"bearer " + tokenStr: http.StatusOK,
		"BEARER " + tokenStr: http.StatusOK,
		"Basic " + tokenStr:  http.StatusUnauthorized,
		tokenStr:             http.StatusUnauthorized,
		"Bearer":             http.StatusUnauthorized,
		"Bearer ":            http.StatusUnauthorized,
	}
	for header, want := range cases {
		rec, _ := qaServe(qaGatewayConfig(), http.MethodGet, "/api/v1/files/list", header)
		assert.Equal(t, want, rec.Code, "header %q", header)
	}
}

func TestQA_PeerSecretFallbackStillRejectsUnknownKeys(t *testing.T) {
	cfg := qaGatewayConfig()
	cfg.PeerSecret = "peer-deployment-secret"
	peerToken := qaSignMap(t, jwt.SigningMethodHS256, []byte("peer-deployment-secret"), qaAuthServiceClaims("access", time.Hour))
	strangerToken := qaSignMap(t, jwt.SigningMethodHS256, []byte("stranger-secret"), qaAuthServiceClaims("access", time.Hour))

	rec, _ := qaServe(cfg, http.MethodGet, "/api/v1/files/list", "Bearer "+peerToken)
	assert.Equal(t, http.StatusOK, rec.Code)
	rec, _ = qaServe(cfg, http.MethodGet, "/api/v1/files/list", "Bearer "+strangerToken)
	assert.Equal(t, http.StatusUnauthorized, rec.Code)
}

// [REAL] The gateway ignores the auth-service "type" claim, so a long-lived (30 day)
// refresh token is accepted as an access token on every proxied route.
func TestQA_RefreshTokenIsNotAcceptedAsAccessToken(t *testing.T) {
	refreshClaims := jwt.MapClaims{
		"sub":  "11111111-2222-3333-4444-555555555555",
		"jti":  "refresh-jti",
		"type": "refresh",
		"iat":  time.Now().Unix(),
		"exp":  time.Now().Add(30 * 24 * time.Hour).Unix(),
	}
	tokenStr := qaSignMap(t, jwt.SigningMethodHS256, []byte(testSecret), refreshClaims)
	rec, reached := qaServe(qaGatewayConfig(), http.MethodGet, "/api/v1/files/list", "Bearer "+tokenStr)
	assert.Equal(t, http.StatusUnauthorized, rec.Code, "[REAL] refresh token accepted as access token by gateway")
	assert.False(t, reached)
}

func splitJWT(token string) []string {
	parts := make([]string, 0, 3)
	start := 0
	for i := 0; i < len(token); i++ {
		if token[i] == '.' {
			parts = append(parts, token[start:i])
			start = i + 1
		}
	}
	return append(parts, token[start:])
}
