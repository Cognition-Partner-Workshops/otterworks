package com.otterworks.report.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.WebAuthenticationDetailsSource;
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
import java.util.Collections;
import java.util.List;

/**
 * Resolves the caller of a report request.
 *
 * With {@code otterworks.jwt.secret} configured (the JWT_SECRET shared with auth-service
 * and the gateway) the bearer token is verified here and the identity and roles come from
 * its claims, so a forwarded or spoofed X-User-ID header is never trusted on its own.
 * Without a secret the service can only run behind the gateway, which validates the token
 * and sets X-User-ID; that header is then the identity and carries no admin role.
 */
public class JwtAuthFilter extends OncePerRequestFilter {

    private static final Logger logger = LoggerFactory.getLogger(JwtAuthFilter.class);

    static final String USER_ID_HEADER = "X-User-ID";
    private static final String BEARER_PREFIX = "Bearer ";
    private static final String ROLE_PREFIX = "ROLE_";

    private final SecretKey key;

    public JwtAuthFilter(String secret) {
        this.key = StringUtils.hasText(secret)
                ? Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8))
                : null;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        UsernamePasswordAuthenticationToken authentication = resolveCaller(request);
        if (authentication != null) {
            authentication.setDetails(new WebAuthenticationDetailsSource().buildDetails(request));
            SecurityContextHolder.getContext().setAuthentication(authentication);
        }
        filterChain.doFilter(request, response);
    }

    private UsernamePasswordAuthenticationToken resolveCaller(HttpServletRequest request) {
        if (key != null) {
            return fromBearerToken(request.getHeader("Authorization"));
        }
        return fromGatewayHeader(request.getHeader(USER_ID_HEADER));
    }

    private UsernamePasswordAuthenticationToken fromBearerToken(String authorizationHeader) {
        Claims claims;
        String userId;
        try {
            String token = bearerToken(authorizationHeader);
            claims = Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload();
            userId = subjectOf(claims);
        } catch (JwtException | IllegalArgumentException e) {
            logger.debug("No usable bearer token: {}", e.getMessage());
            return null;
        }
        return new UsernamePasswordAuthenticationToken(userId, null, authoritiesFrom(claims));
    }

    private static String bearerToken(String authorizationHeader) {
        if (authorizationHeader == null || !authorizationHeader.startsWith(BEARER_PREFIX)) {
            throw new IllegalArgumentException("missing Authorization: Bearer header");
        }
        String token = authorizationHeader.substring(BEARER_PREFIX.length()).trim();
        if (token.isEmpty()) {
            throw new IllegalArgumentException("empty bearer token");
        }
        return token;
    }

    /** The user the verified access token identifies; throws when it is not a usable access token. */
    private static String subjectOf(Claims claims) {
        if (!"access".equals(claims.get("type", String.class))) {
            throw new JwtException("not an access token");
        }
        String userId = claims.getSubject();
        if (!StringUtils.hasText(userId)) {
            userId = claims.get("user_id", String.class);
        }
        if (!StringUtils.hasText(userId)) {
            throw new JwtException("token has no subject");
        }
        return sanitize(userId);
    }

    /** Identity values end up in log lines; strip anything that could forge a log entry. */
    private static String sanitize(String value) {
        return value.trim().replaceAll("[\\r\\n]", "");
    }

    private UsernamePasswordAuthenticationToken fromGatewayHeader(String userId) {
        String callerId;
        try {
            callerId = requireText(userId, USER_ID_HEADER);
        } catch (IllegalArgumentException e) {
            return null;
        }
        return new UsernamePasswordAuthenticationToken(callerId, null,
                Collections.singletonList(new SimpleGrantedAuthority(ROLE_PREFIX + "USER")));
    }

    private static String requireText(String value, String what) {
        if (!StringUtils.hasText(value)) {
            throw new IllegalArgumentException(what + " is missing");
        }
        return sanitize(value);
    }

    private static List<GrantedAuthority> authoritiesFrom(Claims claims) {
        List<GrantedAuthority> authorities = new ArrayList<>();
        Object roles = claims.get("roles");
        if (roles instanceof List) {
            for (Object role : (List<?>) roles) {
                if (role != null) {
                    authorities.add(new SimpleGrantedAuthority(ROLE_PREFIX + role.toString().toUpperCase()));
                }
            }
        }
        if (authorities.isEmpty()) {
            authorities.add(new SimpleGrantedAuthority(ROLE_PREFIX + "USER"));
        }
        return authorities;
    }
}
