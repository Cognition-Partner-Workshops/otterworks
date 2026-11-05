package com.otterworks.report.config;

import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

import javax.servlet.FilterChain;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.Arrays;
import java.util.Collection;
import java.util.List;
import java.util.Locale;
import java.util.stream.Collectors;

/**
 * Authenticates requests from the identity the api-gateway forwards after it
 * has validated the caller's JWT: {@code X-User-ID} (the subject) and
 * {@code X-User-Roles} (comma-separated roles). The gateway strips both from
 * client requests, and backends are only reachable through it in the cluster.
 */
public class GatewayIdentityFilter extends OncePerRequestFilter {

    public static final String USER_ID_HEADER = "X-User-ID";
    public static final String USER_ROLES_HEADER = "X-User-Roles";

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain chain) throws ServletException, IOException {
        String userId = request.getHeader(USER_ID_HEADER);
        if (userId != null && !userId.trim().isEmpty()) {
            SecurityContextHolder.getContext().setAuthentication(
                    new GatewayAuthentication(userId.trim(), roles(request.getHeader(USER_ROLES_HEADER))));
        }
        try {
            chain.doFilter(request, response);
        } finally {
            SecurityContextHolder.clearContext();
        }
    }

    private static List<GrantedAuthority> roles(String header) {
        if (header == null || header.trim().isEmpty()) {
            return java.util.Collections.singletonList(new SimpleGrantedAuthority("ROLE_USER"));
        }
        return Arrays.stream(header.split(","))
                .map(String::trim)
                .filter(r -> !r.isEmpty())
                .map(r -> r.toUpperCase(Locale.ROOT))
                .map(r -> r.startsWith("ROLE_") ? r : "ROLE_" + r)
                .map(SimpleGrantedAuthority::new)
                .collect(Collectors.toList());
    }

    /** Authentication carrying the gateway-forwarded user id as its principal. */
    static final class GatewayAuthentication extends AbstractAuthenticationToken {
        private final String userId;

        GatewayAuthentication(String userId, Collection<? extends GrantedAuthority> authorities) {
            super(authorities);
            this.userId = userId;
            setAuthenticated(true);
        }

        @Override
        public Object getCredentials() {
            return "";
        }

        @Override
        public Object getPrincipal() {
            return userId;
        }
    }
}
