package com.otterworks.ottershops.auth;

import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.stereotype.Component;

import java.util.Arrays;
import java.util.Optional;
import java.util.UUID;

/** Resolves the signed-in shopper from the session cookie or a bearer token. */
@Component
public class CurrentCustomer {
    public static final String COOKIE = "os_session";
    private final AuthService auth;

    public CurrentCustomer(AuthService auth) {
        this.auth = auth;
    }

    public static String token(HttpServletRequest req) {
        String header = req.getHeader("Authorization");
        if (header != null && header.startsWith("Bearer ")) return header.substring(7).trim();
        Cookie[] cookies = req.getCookies();
        if (cookies == null) return null;
        return Arrays.stream(cookies).filter(c -> COOKIE.equals(c.getName())).map(Cookie::getValue).findFirst().orElse(null);
    }

    public Optional<Customer> get(HttpServletRequest req) {
        return auth.resolve(token(req));
    }

    public Optional<UUID> id(HttpServletRequest req) {
        return get(req).map(Customer::id);
    }
}
