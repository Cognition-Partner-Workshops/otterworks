package com.otterworks.report.security;

import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

import javax.servlet.FilterChain;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Turns the identity the API gateway forwards into a Spring Security principal.
 *
 * The gateway validates the bearer JWT and sets {@code X-User-ID} (the token subject)
 * and {@code X-User-Roles} (the token's roles, comma separated) on every proxied
 * request. A request without {@code X-User-ID} stays anonymous and is refused by
 * {@link com.otterworks.report.config.SecurityConfig}.
 */
public class GatewayIdentityFilter extends OncePerRequestFilter {

    public static final String USER_ID_HEADER = "X-User-ID";
    public static final String USER_ROLES_HEADER = "X-User-Roles";
    public static final String ROLE_PREFIX = "ROLE_";
    public static final String ADMIN_ROLE = "ADMIN";

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain chain) throws ServletException, IOException {
        String userId = request.getHeader(USER_ID_HEADER);
        if (userId != null && !userId.trim().isEmpty()
                && SecurityContextHolder.getContext().getAuthentication() == null) {
            UsernamePasswordAuthenticationToken authentication = new UsernamePasswordAuthenticationToken(
                    userId.trim(), null, authoritiesFrom(request.getHeader(USER_ROLES_HEADER)));
            SecurityContextHolder.getContext().setAuthentication(authentication);
        }
        chain.doFilter(request, response);
    }

    static List<GrantedAuthority> authoritiesFrom(String rolesHeader) {
        List<GrantedAuthority> authorities = new ArrayList<GrantedAuthority>();
        authorities.add(new SimpleGrantedAuthority(ROLE_PREFIX + "USER"));
        if (rolesHeader == null) {
            return authorities;
        }
        for (String role : rolesHeader.split(",")) {
            String name = role.trim().toUpperCase(Locale.ROOT);
            if (name.isEmpty() || "USER".equals(name)) {
                continue;
            }
            authorities.add(new SimpleGrantedAuthority(ROLE_PREFIX + name));
        }
        return authorities;
    }
}
