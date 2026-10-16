package middleware

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

type fixedLatency time.Duration

func (f fixedLatency) MobileLatency(context.Context) time.Duration { return time.Duration(f) }

func runMobileLatency(t *testing.T, source LatencySource, method, path, ua string) (time.Duration, bool) {
	t.Helper()
	var slept time.Duration
	proxied := false
	h := mobileLatency(source, func(_ context.Context, d time.Duration) { slept += d })(
		http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
			proxied = true
			w.WriteHeader(http.StatusOK)
		}))
	req := httptest.NewRequest(method, path, nil)
	req.Header.Set("User-Agent", ua)
	h.ServeHTTP(httptest.NewRecorder(), req)
	return slept, proxied
}

func TestMobileLatencyDelaysNativeFileListReads(t *testing.T) {
	for _, ua := range []string{iosAppUA, androidAppUA} {
		for _, path := range []string{"/api/v1/files", "/api/v1/files/", "/api/v1/files?folder_id=abc"} {
			slept, proxied := runMobileLatency(t, fixedLatency(3*time.Second), http.MethodGet, path, ua)
			assert.Equal(t, 3*time.Second, slept, "%s %s", ua, path)
			assert.True(t, proxied)
		}
	}
	slept, _ := runMobileLatency(t, fixedLatency(3*time.Second), http.MethodHead, "/api/v1/files", iosAppUA)
	assert.Equal(t, 3*time.Second, slept)
}

func TestMobileLatencyLeavesBrowsersAlone(t *testing.T) {
	slept, proxied := runMobileLatency(t, fixedLatency(3*time.Second), http.MethodGet, "/api/v1/files", safariUA)
	assert.Zero(t, slept)
	assert.True(t, proxied)
}

func TestMobileLatencyOnlyTouchesFileListReads(t *testing.T) {
	cases := []struct{ method, path string }{
		{http.MethodPost, "/api/v1/files/upload"},
		{http.MethodPost, "/api/v1/files"},
		{http.MethodGet, "/api/v1/files/3f1c2a9e-1b2c-4d5e-8f90-0123456789ab"},
		{http.MethodGet, "/api/v1/files/shared"},
		{http.MethodGet, "/api/v1/folders"},
		{http.MethodGet, "/api/v1/documents"},
	}
	for _, tc := range cases {
		slept, proxied := runMobileLatency(t, fixedLatency(3*time.Second), tc.method, tc.path, iosAppUA)
		assert.Zero(t, slept, "%s %s", tc.method, tc.path)
		assert.True(t, proxied)
	}
}

func TestMobileLatencyFlagOff(t *testing.T) {
	slept, proxied := runMobileLatency(t, fixedLatency(0), http.MethodGet, "/api/v1/files", iosAppUA)
	assert.Zero(t, slept)
	assert.True(t, proxied)
	slept, _ = runMobileLatency(t, nil, http.MethodGet, "/api/v1/files", iosAppUA)
	assert.Zero(t, slept)
}

func TestSleepCtxReturnsOnCancel(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	start := time.Now()
	sleepCtx(ctx, 5*time.Second)
	assert.Less(t, time.Since(start), time.Second)
}
