package com.otterworks.commission.common;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * Only the COMMISSION_PKG delegate may call the rule endpoints: every request
 * except the health probe must carry {@code Authorization: Bearer <token>}
 * matching {@code commission.caller-token}. With no token configured every
 * rule call is refused. The {@code actor} a request carries is therefore only
 * ever the {@code p_actor} the package's own caller passed.
 */
@Component
public class CallerAuthFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(CallerAuthFilter.class);
    private static final String BEARER = "Bearer ";

    private final byte[] expected;

    public CallerAuthFilter(@Value("${commission.caller-token:}") String callerToken) {
        this.expected = callerToken == null || callerToken.isBlank() ? null : sha256(callerToken);
        if (expected == null) {
            log.warn("commission.caller-token is not set: every rule endpoint will answer 401");
        }
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI().substring(request.getContextPath().length());
        return "GET".equals(request.getMethod())
                && (path.equals("/actuator/health") || path.startsWith("/actuator/health/"));
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        if (authenticated(request.getHeader(HttpHeaders.AUTHORIZATION))) {
            chain.doFilter(request, response);
            return;
        }
        log.warn("refused unauthenticated {} {}", request.getMethod(), request.getRequestURI());
        response.setStatus(HttpStatus.UNAUTHORIZED.value());
        response.setHeader(HttpHeaders.WWW_AUTHENTICATE, "Bearer");
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.getWriter().write("{\"message\":\"caller not authenticated\"}");
    }

    private boolean authenticated(String header) {
        if (expected == null || header == null || !header.startsWith(BEARER)) {
            return false;
        }
        return MessageDigest.isEqual(expected, sha256(header.substring(BEARER.length())));
    }

    private static byte[] sha256(String s) {
        try {
            return MessageDigest.getInstance("SHA-256").digest(s.getBytes(StandardCharsets.UTF_8));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
