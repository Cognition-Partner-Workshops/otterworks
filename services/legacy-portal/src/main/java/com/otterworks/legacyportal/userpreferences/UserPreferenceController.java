package com.otterworks.legacyportal.userpreferences;

import javax.validation.Valid;
import javax.validation.constraints.NotBlank;
import javax.validation.constraints.Size;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/preferences")
public class UserPreferenceController {

    private final UserPreferenceService service;
    @Value("${JWT_SECRET:}") private String jwtSecret;

    private void requireOwner(String userId, String authorization) {
        Claims claims;
        try {
            if (authorization == null || !authorization.startsWith("Bearer ")) {
                throw new IllegalArgumentException("Missing token");
            }
            claims = Jwts.parser().verifyWith(Keys.hmacShaKeyFor(jwtSecret.getBytes(StandardCharsets.UTF_8)))
                    .build().parseSignedClaims(authorization.substring(7)).getPayload();
            if (claims.getSubject() == null || claims.getSubject().isBlank()
                    || claims.getExpiration() == null || !"access".equals(claims.get("type"))) {
                throw new IllegalArgumentException("Invalid access token");
            }
        } catch (JwtException | IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Authentication required");
        }
        if (!userId.equals(claims.getSubject())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Preferences belong to another user");
        }
    }

    public UserPreferenceController(UserPreferenceService service) {
        this.service = service;
    }

    @GetMapping("/{userId}")
    public PreferenceResponse get(@PathVariable String userId, @RequestHeader(value = "Authorization", required = false) String authorization) {
        requireOwner(userId, authorization);
        return PreferenceResponse.from(service.getOrDefault(userId));
    }

    @PutMapping("/{userId}")
    public PreferenceResponse update(
            @PathVariable String userId, @Valid @RequestBody UpdatePreferenceRequest request,
            @RequestHeader(value = "Authorization", required = false) String authorization) {
        requireOwner(userId, authorization);
        return PreferenceResponse.from(
                service.save(
                        userId,
                        request.getTheme(),
                        request.getLocale(),
                        request.isEmailNotifications()));
    }

    public static class UpdatePreferenceRequest {

        @NotBlank
        @Size(max = 20)
        private String theme;

        @NotBlank
        @Size(max = 20)
        private String locale;

        private boolean emailNotifications;

        public String getTheme() {
            return theme;
        }

        public void setTheme(String theme) {
            this.theme = theme;
        }

        public String getLocale() {
            return locale;
        }

        public void setLocale(String locale) {
            this.locale = locale;
        }

        public boolean isEmailNotifications() {
            return emailNotifications;
        }

        public void setEmailNotifications(boolean emailNotifications) {
            this.emailNotifications = emailNotifications;
        }
    }

    public static class PreferenceResponse {

        private final String userId;
        private final String theme;
        private final String locale;
        private final boolean emailNotifications;

        private PreferenceResponse(
                String userId, String theme, String locale, boolean emailNotifications) {
            this.userId = userId;
            this.theme = theme;
            this.locale = locale;
            this.emailNotifications = emailNotifications;
        }

        static PreferenceResponse from(UserPreference p) {
            return new PreferenceResponse(
                    p.getUserId(), p.getTheme(), p.getLocale(), p.isEmailNotifications());
        }

        public String getUserId() {
            return userId;
        }

        public String getTheme() {
            return theme;
        }

        public String getLocale() {
            return locale;
        }

        public boolean isEmailNotifications() {
            return emailNotifications;
        }
    }
}
