package proxy

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"

	"github.com/Cognition-Partner-Workshops/otterworks/services/api-gateway/internal/middleware"
)

func TestSetIdentityHeaders_FromValidatedClaims(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/api/v1/reports/1", nil)
	req.Header.Set("X-User-ID", "spoofed-user")
	req.Header.Set("X-User-Roles", "ADMIN")

	claims := &middleware.JWTClaims{UserID: "user-7", Roles: []string{"USER", "ADMIN"}}
	claims.Subject = "user-7"

	setIdentityHeaders(req, claims)

	assert.Equal(t, "user-7", req.Header.Get("X-User-ID"))
	assert.Equal(t, "USER,ADMIN", req.Header.Get("X-User-Roles"))
}

func TestSetIdentityHeaders_StripsClientHeadersWithoutClaims(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/api/v1/reports/1", nil)
	req.Header.Set("X-User-ID", "spoofed-user")
	req.Header.Set("X-User-Roles", "ADMIN")

	setIdentityHeaders(req, nil)

	assert.Empty(t, req.Header.Get("X-User-ID"))
	assert.Empty(t, req.Header.Get("X-User-Roles"))
}

func TestSetIdentityHeaders_NoRolesClaimLeavesRolesHeaderUnset(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/api/v1/reports/1", nil)
	req.Header.Set("X-User-Roles", "ADMIN")

	setIdentityHeaders(req, &middleware.JWTClaims{UserID: "user-9"})

	assert.Equal(t, "user-9", req.Header.Get("X-User-ID"))
	assert.Empty(t, req.Header.Get("X-User-Roles"))
}
