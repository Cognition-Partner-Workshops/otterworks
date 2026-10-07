package com.otterworks.report.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.MalformedJwtException;
import io.jsonwebtoken.UnsupportedJwtException;
import io.jsonwebtoken.security.Keys;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
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
import java.util.Collections;
import java.util.List;

/**
 * Authenticates callers from the auth-service access token in {@code Authorization: Bearer}.
 *
 * Mirrors auth-service's JwtAuthFilter: HMAC signature verified with the shared JWT_SECRET,
 * {@code sub} is the principal, {@code roles} become {@code ROLE_*} authorities, and refresh
 * tokens are rejected. Gateway-forwarded identity headers (X-User-ID) are deliberately not
 * trusted because they are client-settable when the service is reached directly. With no
 * secret configured nothing authenticates, so protected routes fail closed with 401.
 *
 * JWT_PEER_SECRET (optional) mirrors the api-gateway's peer key so a peer deployment's
 * admin dashboard can still read this deployment's archive through its gateway.
 */
@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private static final Logger logger = LoggerFactory.getLogger(JwtAuthenticationFilter.class);
    private static final String BEARER_PREFIX = "Bearer ";

    private final List<SecretKey> signingKeys = new ArrayList<SecretKey>();

    public JwtAuthenticationFilter(@Value("${otterworks.auth.jwt-secret:}") String jwtSecret,
                                   @Value("${otterworks.auth.jwt-peer-secret:}") String jwtPeerSecret) {
        addKey(jwtSecret);
        addKey(jwtPeerSecret);
        if (signingKeys.isEmpty()) {
            logger.error("JWT_SECRET is not set: report endpoints will reject every request with 401");
        }
    }

    private void addKey(String secret) {
        if (StringUtils.hasText(secret)) {
            signingKeys.add(Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8)));
        }
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        try {
            SecurityContextHolder.getContext().setAuthentication(authenticate(bearerToken(request)));
        } catch (JwtException | IllegalArgumentException e) {
            logger.debug("Request not authenticated: {}", e.getClass().getSimpleName());
        }
        filterChain.doFilter(request, response);
    }

    private static String bearerToken(HttpServletRequest request) {
        String header = request.getHeader("Authorization");
        return header != null && header.startsWith(BEARER_PREFIX)
                ? header.substring(BEARER_PREFIX.length()).trim() : null;
    }

    private UsernamePasswordAuthenticationToken authenticate(String token) {
        Claims claims = verify(token);
        requireAccessToken(claims);
        return new UsernamePasswordAuthenticationToken(
                claims.getSubject(), null, authorities(claims.get("roles")));
    }

    private static void requireAccessToken(Claims claims) {
        if ("refresh".equals(claims.get("type", String.class))) {
            throw new UnsupportedJwtException("refresh tokens cannot be used as access tokens");
        }
        if (!StringUtils.hasText(claims.getSubject())) {
            throw new MalformedJwtException("token has no subject");
        }
    }

    private Claims verify(String token) {
        if (!StringUtils.hasText(token)) {
            throw new IllegalArgumentException("no bearer token");
        }
        JwtException failure = new JwtException("JWT_SECRET is not configured");
        for (SecretKey key : signingKeys) {
            try {
                return Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload();
            } catch (JwtException e) {
                failure = e;
            }
        }
        throw failure;
    }

    private static Collection<SimpleGrantedAuthority> authorities(Object rolesClaim) {
        if (!(rolesClaim instanceof Collection)) {
            return Collections.emptyList();
        }
        List<SimpleGrantedAuthority> authorities = new ArrayList<SimpleGrantedAuthority>();
        for (Object role : (Collection<?>) rolesClaim) {
            if (role != null && StringUtils.hasText(role.toString())) {
                authorities.add(new SimpleGrantedAuthority("ROLE_" + role));
            }
        }
        return authorities;
    }
}
