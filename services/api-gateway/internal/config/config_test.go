package config

import (
	"net"
	"testing"

	"github.com/stretchr/testify/require"
)

func TestLoadTrustedProxies(t *testing.T) {
	t.Setenv("JWT_SECRET", "test-secret")
	t.Setenv("TRUSTED_PROXIES", "10.0.0.0/8, 192.0.2.10")

	cfg := Load()

	require.NoError(t, cfg.Validate())
	require.Len(t, cfg.TrustedProxies, 2)
	require.True(t, cfg.TrustedProxies[0].Contains(net.ParseIP("10.1.2.3")))
	require.True(t, cfg.TrustedProxies[1].Contains(net.ParseIP("192.0.2.10")))
}

func TestLoadRejectsInvalidTrustedProxy(t *testing.T) {
	t.Setenv("JWT_SECRET", "test-secret")
	t.Setenv("TRUSTED_PROXIES", "10.0.0.0/8,not-a-network")

	cfg := Load()

	require.ErrorContains(t, cfg.Validate(), "TRUSTED_PROXIES")
}

func TestParseTrustedProxiesDefaultsToTrustNoOne(t *testing.T) {
	trustedProxies, err := ParseTrustedProxies("")

	require.NoError(t, err)
	require.Empty(t, trustedProxies)
}
