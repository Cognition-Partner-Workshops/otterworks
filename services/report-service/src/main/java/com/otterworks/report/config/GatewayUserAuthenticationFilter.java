package com.otterworks.report.config;

import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.AuthorityUtils;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

import javax.servlet.FilterChain;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;

/**
 * Authenticates a request from the {@code X-User-ID} header the API gateway sets
 * after it has validated the caller's JWT. The gateway always overwrites this
 * header on proxied requests, so its value is the verified identity of the caller.
 *
 * Requests without the header stay anonymous and are rejected by the
 * {@code authenticated()} rule on the report routes in {@link SecurityConfig}.
 */
public class GatewayUserAuthenticationFilter extends OncePerRequestFilter {

    public static final String USER_ID_HEADER = "X-User-ID";

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        String userId = request.getHeader(USER_ID_HEADER);
        if (userId != null && !userId.trim().isEmpty()
                && SecurityContextHolder.getContext().getAuthentication() == null) {
            UsernamePasswordAuthenticationToken authentication = new UsernamePasswordAuthenticationToken(
                    userId.trim(), null, AuthorityUtils.createAuthorityList("ROLE_USER"));
            SecurityContextHolder.getContext().setAuthentication(authentication);
        }
        filterChain.doFilter(request, response);
    }
}
