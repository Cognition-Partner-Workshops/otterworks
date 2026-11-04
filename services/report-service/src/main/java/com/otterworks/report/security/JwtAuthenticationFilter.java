package com.otterworks.report.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

import javax.crypto.SecretKey;
import javax.servlet.FilterChain;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Authenticates report API callers from the HS256 access token issued by auth-service.
 *
 * The api-gateway forwards the caller's Authorization header unchanged, so the service
 * verifies the same token the gateway verified instead of trusting a header any client
 * on the network path could set. When the gateway also sends X-User-ID it must name the
 * token's subject. Requests without a valid access token stay anonymous and are rejected
 * by {@link com.otterworks.report.config.SecurityConfig}.
 */
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    static final String GATEWAY_USER_HEADER = "X-User-ID";

    private static final Logger logger = LoggerFactory.getLogger(JwtAuthenticationFilter.class);
    private static final String BEARER_PREFIX = "bearer ";

    private final List<SecretKey> keys;

    public JwtAuthenticationFilter(String secret, String peerSecret) {
        List<SecretKey> configured = new ArrayList<>();
        for (String s : new String[] {secret, peerSecret}) {
            if (s != null && !s.trim().isEmpty()) {
                configured.add(Keys.hmacShaKeyFor(s.getBytes(StandardCharsets.UTF_8)));
            }
        }
        if (configured.isEmpty()) {
            logger.warn("JWT_SECRET is not set: every /api/v1/reports request will be rejected");
        }
        this.keys = configured;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        ReportCaller caller = authenticate(request);
        if (caller != null) {
            List<SimpleGrantedAuthority> authorities = caller.getRoles().stream()
                    .map(role -> new SimpleGrantedAuthority("ROLE_" + role))
                    .collect(Collectors.toList());
            SecurityContextHolder.getContext().setAuthentication(
                    new UsernamePasswordAuthenticationToken(caller, null, authorities));
        }
        try {
            chain.doFilter(request, response);
        } finally {
            SecurityContextHolder.clearContext();
        }
    }

    private ReportCaller authenticate(HttpServletRequest request) {
        String header = request.getHeader("Authorization");
        if (header == null || !header.regionMatches(true, 0, BEARER_PREFIX, 0, BEARER_PREFIX.length())) {
            return null;
        }
        String token = header.substring(BEARER_PREFIX.length()).trim();
        Claims claims = verify(token);
        if (claims == null || !"access".equals(claims.get("type"))) {
            return null;
        }

        String userId = claims.getSubject();
        if (userId == null || userId.isEmpty()) {
            Object legacy = claims.get("user_id");
            userId = legacy instanceof String ? (String) legacy : null;
        }
        if (userId == null || userId.isEmpty()) {
            return null;
        }

        String gatewayUser = request.getHeader(GATEWAY_USER_HEADER);
        if (gatewayUser != null && !gatewayUser.isEmpty() && !gatewayUser.equals(userId)) {
            logger.warn("Rejected report request: {} does not match the token subject", GATEWAY_USER_HEADER);
            return null;
        }
        return new ReportCaller(userId, roles(claims.get("roles")));
    }

    private Claims verify(String token) {
        for (SecretKey key : keys) {
            try {
                return Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload();
            } catch (JwtException | IllegalArgumentException e) {
                // Try the next configured key; an unverifiable token stays anonymous.
            }
        }
        return null;
    }

    private static Set<String> roles(Object claim) {
        Set<String> roles = new LinkedHashSet<>();
        if (claim instanceof Collection) {
            for (Object role : (Collection<?>) claim) {
                if (role != null) {
                    roles.add(role.toString());
                }
            }
        }
        return roles;
    }
}
