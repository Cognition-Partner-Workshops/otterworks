package middleware

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

const (
	safariUA     = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
	iosAppUA     = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 OtterWorksApp/ios"
	androidAppUA = "Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/AP1A; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/124.0.0.0 Mobile Safari/537.36 OtterWorksApp/android"
)

func TestClientFromUserAgent(t *testing.T) {
	cases := map[string]string{
		safariUA:                ClientWeb,
		iosAppUA:                ClientIOS,
		androidAppUA:            ClientAndroid,
		"OtterWorksApp/ios":     ClientIOS,
		"OtterWorksApp/desktop": ClientOther,
		"curl/8.5.0":            ClientOther,
		"":                      ClientOther,
	}
	for ua, want := range cases {
		assert.Equal(t, want, ClientFromUserAgent(ua), ua)
	}
}

func TestIsNativeApp(t *testing.T) {
	assert.True(t, IsNativeApp(iosAppUA))
	assert.True(t, IsNativeApp(androidAppUA))
	assert.False(t, IsNativeApp(safariUA))
}

func TestRouteFor(t *testing.T) {
	cases := map[string]string{
		"":                     "/",
		"/":                    "/",
		"/api/v1/files":        "/api/v1/files",
		"/api/v1/files/":       "/api/v1/files",
		"/api/v1/files/shared": "/api/v1/files/shared",
		"/api/v1/files/3f1c2a9e-1b2c-4d5e-8f90-0123456789ab":          "/api/v1/files/:id",
		"/api/v1/files/3f1c2a9e-1b2c-4d5e-8f90-0123456789ab/download": "/api/v1/files/:id/download",
		"/api/v1/documents/42":                     "/api/v1/documents/:id",
		"/api/v1/reports/65f0c0ffee0123456789abcd": "/api/v1/reports/:id",
	}
	for path, want := range cases {
		assert.Equal(t, want, RouteFor(path), path)
	}
}
