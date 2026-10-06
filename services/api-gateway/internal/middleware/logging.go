package middleware

import (
	"net/http"
	"time"

	"github.com/go-chi/chi/v5/middleware"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
)

// Logger returns an HTTP middleware that writes one JSON access log line per
// request. method, route, status, duration_ms and client are the fields the
// CloudWatch Logs Insights queries in docs/observability/mobile-latency.md
// group by.
func Logger(logger zerolog.Logger) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			start := time.Now()
			ww := middleware.NewWrapResponseWriter(w, r.ProtoMajor)

			next.ServeHTTP(ww, r)

			duration := time.Since(start)
			requestID := GetRequestID(r.Context())

			var event *zerolog.Event
			status := ww.Status()
			switch {
			case status >= 500:
				event = logger.Error()
			case status >= 400:
				event = logger.Warn()
			default:
				event = logger.Info()
			}

			ua := r.UserAgent()
			event.
				Str("request_id", requestID).
				Str("method", r.Method).
				Str("route", RouteFor(r.URL.Path)).
				Str("path", r.URL.Path).
				Str("query", r.URL.RawQuery).
				Int("status", status).
				Int("bytes", ww.BytesWritten()).
				Float64("duration_ms", float64(duration.Microseconds())/1000).
				Dur("latency_ms", duration).
				Str("remote_addr", r.RemoteAddr).
				Str("client", ClientFromUserAgent(ua)).
				Str("user_agent", ua).
				Str("protocol", r.Proto).
				Msg("request completed")
		})
	}
}

// SetLogLevel configures the global zerolog level.
func SetLogLevel(level string) {
	switch level {
	case "debug":
		zerolog.SetGlobalLevel(zerolog.DebugLevel)
	case "info":
		zerolog.SetGlobalLevel(zerolog.InfoLevel)
	case "warn":
		zerolog.SetGlobalLevel(zerolog.WarnLevel)
	case "error":
		zerolog.SetGlobalLevel(zerolog.ErrorLevel)
	default:
		zerolog.SetGlobalLevel(zerolog.InfoLevel)
	}
	log.Debug().Str("level", level).Msg("log level set")
}
