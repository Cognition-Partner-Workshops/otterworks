package com.otterworks.report.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;

/**
 * Verifies the HMAC-signed access tokens issued by auth-service.
 *
 * Mirrors the api-gateway: {@code JWT_SECRET} is the deployment's key and the optional
 * {@code JWT_PEER_SECRET} is a second key tokens are also accepted under, so a peer
 * deployment's admin dashboard can read this deployment's archive (Before/After panel).
 */
@Component
public class JwtTokenVerifier {

    static final String TYPE_CLAIM = "type";
    static final String ROLES_CLAIM = "roles";
    private static final String REFRESH_TYPE = "refresh";

    private final SecretKey key;
    private final SecretKey peerKey;

    public JwtTokenVerifier(
            @Value("${jwt.secret}") String secret,
            @Value("${jwt.peer-secret:}") String peerSecret) {
        if (secret == null || secret.trim().isEmpty()) {
            throw new IllegalStateException(
                    "JWT_SECRET is required: report-service refuses to start without a token signing key");
        }
        this.key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.peerKey = (peerSecret == null || peerSecret.trim().isEmpty())
                ? null
                : Keys.hmacShaKeyFor(peerSecret.getBytes(StandardCharsets.UTF_8));
    }

    /**
     * Parses and verifies an access token.
     *
     * @throws JwtException when the signature, expiry or token type is not acceptable
     */
    public Claims verifyAccessToken(String token) {
        Claims claims;
        try {
            claims = parse(token, key);
        } catch (JwtException primary) {
            if (peerKey == null) {
                throw primary;
            }
            claims = parse(token, peerKey);
        }
        if (REFRESH_TYPE.equals(claims.get(TYPE_CLAIM, String.class))) {
            throw new JwtException("refresh tokens cannot be used to call the API");
        }
        if (claims.getSubject() == null || claims.getSubject().trim().isEmpty()) {
            throw new JwtException("token has no subject");
        }
        return claims;
    }

    private static Claims parse(String token, SecretKey signingKey) {
        return Jwts.parser().verifyWith(signingKey).build().parseSignedClaims(token).getPayload();
    }
}
