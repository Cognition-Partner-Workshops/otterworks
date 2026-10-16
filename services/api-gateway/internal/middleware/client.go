package middleware

import (
	"regexp"
	"strings"
)

// NativeAppToken is the User-Agent token the Capacitor shells append
// (appendUserAgent in frontend/client-app/capacitor.config.ts).
const NativeAppToken = "OtterWorksApp"

// Client values logged on every access log line.
const (
	ClientWeb     = "web"
	ClientIOS     = "ios"
	ClientAndroid = "android"
	ClientOther   = "other"
)

// ClientFromUserAgent classifies a request by the app that sent it. The
// native shells are WKWebView / Android WebView and so also carry "Mozilla/";
// the app token is checked first.
func ClientFromUserAgent(ua string) string {
	if i := strings.Index(ua, NativeAppToken+"/"); i >= 0 {
		platform := ua[i+len(NativeAppToken)+1:]
		if j := strings.IndexAny(platform, " ;)"); j >= 0 {
			platform = platform[:j]
		}
		switch strings.ToLower(platform) {
		case ClientIOS:
			return ClientIOS
		case ClientAndroid:
			return ClientAndroid
		}
		return ClientOther
	}
	if strings.HasPrefix(ua, "Mozilla/") {
		return ClientWeb
	}
	return ClientOther
}

// IsNativeApp reports whether the User-Agent carries the native app token.
func IsNativeApp(ua string) bool {
	return strings.Contains(ua, NativeAppToken)
}

var (
	uuidSegment    = regexp.MustCompile(`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$`)
	numericSegment = regexp.MustCompile(`^[0-9]+$`)
	hexIDSegment   = regexp.MustCompile(`^[0-9a-fA-F]{24,}$`)
)

// RouteFor collapses a request path into a low-cardinality route template by
// replacing id-shaped segments with ":id" and dropping a trailing slash, so
// /api/v1/files/<uuid> logs as /api/v1/files/:id and /api/v1/files/ as
// /api/v1/files.
func RouteFor(path string) string {
	if path == "" || path == "/" {
		return "/"
	}
	segments := strings.Split(strings.TrimSuffix(path, "/"), "/")
	for i, s := range segments {
		if uuidSegment.MatchString(s) || numericSegment.MatchString(s) || hexIDSegment.MatchString(s) {
			segments[i] = ":id"
		}
	}
	return strings.Join(segments, "/")
}
