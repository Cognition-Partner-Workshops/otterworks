package middleware

import (
	"context"
	"net/http"
	"time"
)

// LatencySource returns the delay to inject for a native-app file list read.
type LatencySource interface {
	MobileLatency(ctx context.Context) time.Duration
}

// FileListRoute is the file-service listing the Files screen loads.
const FileListRoute = "/api/v1/files"

// MobileLatency delays native-app reads of the file list by the duration the
// chaos flag holds (scripts/bug-catalog.yaml: mobile-latency) before the
// request is proxied. Browsers, writes and every other route pass straight
// through.
func MobileLatency(source LatencySource) func(http.Handler) http.Handler {
	return mobileLatency(source, sleepCtx)
}

func mobileLatency(source LatencySource, sleep func(context.Context, time.Duration)) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if source != nil && isRead(r.Method) && RouteFor(r.URL.Path) == FileListRoute && IsNativeApp(r.UserAgent()) {
				if d := source.MobileLatency(r.Context()); d > 0 {
					sleep(r.Context(), d)
				}
			}
			next.ServeHTTP(w, r)
		})
	}
}

func isRead(method string) bool {
	return method == http.MethodGet || method == http.MethodHead
}

func sleepCtx(ctx context.Context, d time.Duration) {
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-t.C:
	case <-ctx.Done():
	}
}
