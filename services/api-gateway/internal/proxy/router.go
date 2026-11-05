package proxy

import (
	"encoding/json"
	"net/http"
	"net/http/httputil"
	"net/url"
	"strings"

	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"

	"github.com/Cognition-Partner-Workshops/otterworks/services/api-gateway/internal/middleware"
)

// Route defines a mapping from a URL prefix to a backend service.
type Route struct {
	Prefix    string
	TargetURL string
}

// RouterConfig holds configuration for the reverse proxy router.
type RouterConfig struct {
	Routes        []Route
	CBManager     *CircuitBreakerManager
	Logger        zerolog.Logger
	EnableTracing bool
}

// Identity headers the gateway derives from the validated JWT. Any value a
// client sends for them is discarded before the request reaches a backend.
const (
	HeaderUserID    = "X-User-ID"
	HeaderUserRoles = "X-User-Roles"
)

// InternalOnlyPaths are backend routes meant for service-to-service callers
// only; user traffic through the edge is answered with 404 and never proxied.
func InternalOnlyPaths() []string {
	return []string{
		"/api/v1/search/index",
		"/api/v1/search/reindex",
	}
}

func isInternalOnlyPath(path string) bool {
	for _, p := range InternalOnlyPaths() {
		if path == p || strings.HasPrefix(path, p+"/") {
			return true
		}
	}
	return false
}

func notFound(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusNotFound)
	json.NewEncoder(w).Encode(map[string]string{
		"error": "route not found",
	})
}

// NewRouter creates a chi router with all service routes mounted.
func NewRouter(cfg RouterConfig) chi.Router {
	r := chi.NewRouter()

	r.Use(func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
			if isInternalOnlyPath(req.URL.Path) {
				notFound(w)
				return
			}
			next.ServeHTTP(w, req)
		})
	})

	for _, route := range cfg.Routes {
		route := route // capture loop var
		r.Route(route.Prefix, func(sub chi.Router) {
			handler := newProxyHandler(route, cfg)
			sub.HandleFunc("/*", handler)
			sub.HandleFunc("/", handler)
		})
	}
	r.NotFound(func(w http.ResponseWriter, r *http.Request) {
		notFound(w)
	})

	return r
}

func newProxyHandler(route Route, cfg RouterConfig) http.HandlerFunc {
	// The full request path (e.g. /api/v1/auth/register) is preserved in
	// req.URL.Path, so the target URL should be just the backend host.
	// httputil.ReverseProxy joins the target path with req.URL.Path.
	target, err := url.Parse(route.TargetURL)
	if err != nil {
		cfg.Logger.Fatal().Err(err).Str("target", route.TargetURL).Msg("invalid proxy target URL")
	}

	proxy := httputil.NewSingleHostReverseProxy(target)

	// Wrap the default director to forward authenticated user identity.
	// The auth-service issues JWTs with the user ID in the standard "sub" claim
	// (claims.Subject). Fall back to the custom "user_id" claim for compatibility.
	defaultDirector := proxy.Director
	proxy.Director = func(req *http.Request) {
		defaultDirector(req)
		req.Header.Del(HeaderUserID)
		req.Header.Del(HeaderUserRoles)
		if claims := middleware.GetJWTClaims(req.Context()); claims != nil {
			userID := claims.Subject
			if userID == "" {
				userID = claims.UserID
			}
			if userID != "" {
				req.Header.Set(HeaderUserID, userID)
			}
			if len(claims.Roles) > 0 {
				req.Header.Set(HeaderUserRoles, strings.Join(claims.Roles, ","))
			}
		}
	}

	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		cfg.Logger.Error().
			Err(err).
			Str("target", route.TargetURL).
			Str("path", r.URL.Path).
			Str("method", r.Method).
			Msg("proxy error")

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadGateway)
		json.NewEncoder(w).Encode(map[string]string{
			"error":  "service unavailable",
			"target": route.Prefix,
		})
	}

	var handler http.Handler = proxy
	if cfg.EnableTracing {
		handler = otelhttp.NewHandler(proxy, "proxy:"+route.Prefix)
	}

	cb := cfg.CBManager.Get(route.Prefix)

	return func(w http.ResponseWriter, r *http.Request) {
		if err := cb.Execute(handler, w, r); err != nil {
			cfg.Logger.Warn().
				Str("circuit_breaker", route.Prefix).
				Str("state", cb.State().String()).
				Msg("circuit breaker rejected request")

			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusServiceUnavailable)
			json.NewEncoder(w).Encode(map[string]string{
				"error":   "service temporarily unavailable",
				"service": route.Prefix,
				"reason":  "circuit breaker open",
			})
		}
	}
}
