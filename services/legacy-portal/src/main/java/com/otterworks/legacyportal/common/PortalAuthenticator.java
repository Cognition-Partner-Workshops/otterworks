package com.otterworks.legacyportal.common;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;
import javax.crypto.SecretKey;
import javax.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.stereotype.Component;

/**
 * Single place that turns an incoming request into an authenticated {@link PortalPrincipal}.
 *
 * <p>Accepts the OtterWorks access token issued by auth-service: an HS256 JWT in the {@code
 * Authorization: Bearer} header, signed with the shared {@code JWT_SECRET}, whose subject is the
 * user id and whose {@code roles} claim lists the user's roles. Refresh tokens ({@code
 * type=refresh}) are not accepted as an identity.
 */
@Component
public class PortalAuthenticator {

    private static final String BEARER_PREFIX = "Bearer ";
    private static final String ROLES_CLAIM = "roles";
    private static final String TYPE_CLAIM = "type";
    private static final String REFRESH_TYPE = "refresh";

    private final SecretKey key;

    public PortalAuthenticator(@Value("${portal.auth.jwt-secret}") String secret) {
        this.key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
    }

    public PortalPrincipal authenticate(HttpServletRequest request) {
        String header = request.getHeader(HttpHeaders.AUTHORIZATION);
        if (header == null || !header.startsWith(BEARER_PREFIX)) {
            throw unauthenticated("Missing bearer token");
        }
        return authenticate(header.substring(BEARER_PREFIX.length()).trim());
    }

    public PortalPrincipal authenticate(String token) {
        Claims claims;
        try {
            claims = Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload();
        } catch (JwtException | IllegalArgumentException e) {
            throw unauthenticated("Invalid bearer token");
        }
        if (REFRESH_TYPE.equals(claims.get(TYPE_CLAIM, String.class))) {
            throw unauthenticated("Refresh tokens cannot be used as an identity");
        }
        String userId = claims.getSubject();
        if (userId == null || userId.isBlank()) {
            throw unauthenticated("Bearer token has no subject");
        }
        return new PortalPrincipal(userId, roles(claims));
    }

    private static List<String> roles(Claims claims) {
        Object raw = claims.get(ROLES_CLAIM);
        if (!(raw instanceof List)) {
            return Collections.emptyList();
        }
        return ((List<?>) raw)
                .stream().filter(r -> r != null).map(Object::toString).collect(Collectors.toList());
    }

    private static PortalAuthException unauthenticated(String message) {
        return new PortalAuthException(PortalAuthException.Kind.UNAUTHENTICATED, message);
    }
}
