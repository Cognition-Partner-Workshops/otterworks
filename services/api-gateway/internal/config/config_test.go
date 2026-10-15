package config

import (
	"strings"
	"testing"
)

func TestValidateRejectsMissingSecret(t *testing.T) {
	for _, secret := range []string{"", "   "} {
		cfg := &Config{JWTSecret: secret}
		if err := cfg.Validate(); err == nil || !strings.Contains(err.Error(), "JWT_SECRET") {
			t.Fatalf("Validate(%q) = %v, want JWT_SECRET required error", secret, err)
		}
	}
}

func TestValidateRejectsKnownDefaultSecrets(t *testing.T) {
	for secret := range knownDefaultJWTSecrets {
		cfg := &Config{JWTSecret: secret}
		if err := cfg.Validate(); err == nil || !strings.Contains(err.Error(), "publicly known default") {
			t.Errorf("Validate(%q) = %v, want known-default rejection", secret, err)
		}
	}
}

func TestValidateRejectsKnownDefaultPeerSecret(t *testing.T) {
	cfg := &Config{
		JWTSecret:     "a-randomly-generated-deployment-secret-0123456789",
		JWTPeerSecret: "otterworks-local-dev-jwt-secret-change-me-in-production",
	}
	if err := cfg.Validate(); err == nil || !strings.Contains(err.Error(), "JWT_PEER_SECRET") {
		t.Fatalf("Validate() = %v, want JWT_PEER_SECRET rejection", err)
	}
}

func TestValidateAcceptsRandomSecret(t *testing.T) {
	cfg := &Config{JWTSecret: "a-randomly-generated-deployment-secret-0123456789"}
	if err := cfg.Validate(); err != nil {
		t.Fatalf("Validate() = %v, want nil", err)
	}
	cfg.JWTPeerSecret = "the-peer-deployments-randomly-generated-secret-987"
	if err := cfg.Validate(); err != nil {
		t.Fatalf("Validate() with peer secret = %v, want nil", err)
	}
}

func TestLoadHasNoJWTSecretFallback(t *testing.T) {
	t.Setenv("JWT_SECRET", "")
	if got := Load().JWTSecret; got != "" {
		t.Fatalf("Load().JWTSecret = %q, want empty when JWT_SECRET is empty", got)
	}
}
