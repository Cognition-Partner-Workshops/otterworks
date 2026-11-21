package middleware

import (
	"net"
	"net/http"
	"strings"
)

// ClientIP identifies the client using forwarding headers only when the TCP
// peer belongs to a configured trusted proxy network.
func ClientIP(trustedProxies []*net.IPNet) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			peerIP := remoteIP(r.RemoteAddr)
			if peerIP == nil || !isTrustedProxy(peerIP, trustedProxies) {
				if peerIP != nil {
					r.RemoteAddr = peerIP.String()
				}
				next.ServeHTTP(w, r)
				return
			}

			clientIP := forwardedClientIP(r.Header.Get("X-Forwarded-For"), r.Header.Get("X-Real-IP"), peerIP, trustedProxies)
			r.RemoteAddr = clientIP
			next.ServeHTTP(w, r)
		})
	}
}

func forwardedClientIP(forwardedFor, realIP string, peerIP net.IP, trustedProxies []*net.IPNet) string {
	entries := strings.Split(forwardedFor, ",")
	for i := len(entries) - 1; i >= 0; i-- {
		entry := entries[i]
		ip := net.ParseIP(strings.TrimSpace(entry))
		if ip == nil || isTrustedProxy(ip, trustedProxies) {
			continue
		}
		return ip.String()
	}

	if ip := net.ParseIP(strings.TrimSpace(realIP)); ip != nil {
		return ip.String()
	}
	return peerIP.String()
}

func remoteIP(remoteAddr string) net.IP {
	host, _, err := net.SplitHostPort(remoteAddr)
	if err != nil {
		host = remoteAddr
	}
	return net.ParseIP(strings.TrimSpace(host))
}

func isTrustedProxy(ip net.IP, trustedProxies []*net.IPNet) bool {
	for _, network := range trustedProxies {
		if network.Contains(ip) {
			return true
		}
	}
	return false
}
