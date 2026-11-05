package com.bank.kyc;

import java.io.IOException;
import javax.servlet.FilterChain;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.web.filter.OncePerRequestFilter;

public class ServiceTokenAuthenticationFilter extends OncePerRequestFilter {
    private final AuthenticationManager authenticationManager;
    private final AuthenticationEntryPoint unauthorized;

    public ServiceTokenAuthenticationFilter(AuthenticationManager authenticationManager,
                                            AuthenticationEntryPoint unauthorized) {
        this.authenticationManager = authenticationManager;
        this.unauthorized = unauthorized;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String header = request.getHeader("Authorization");
        if (header == null) {
            chain.doFilter(request, response);
            return;
        }
        Authentication authentication;
        try {
            if (!header.startsWith("Bearer ")) {
                throw new BadCredentialsException("Invalid service token");
            }
            String token = header.substring(7);
            int separator = token.indexOf(':');
            if (separator <= 0 || separator == token.length() - 1) {
                throw new BadCredentialsException("Invalid service token");
            }
            authentication = authenticationManager.authenticate(new UsernamePasswordAuthenticationToken(
                    token.substring(0, separator), token.substring(separator + 1)));
        } catch (AuthenticationException exception) {
            SecurityContextHolder.clearContext();
            unauthorized.commence(request, response, exception);
            return;
        }
        SecurityContextHolder.setContext(SecurityContextHolder.createEmptyContext());
        SecurityContextHolder.getContext().setAuthentication(authentication);
        try {
            chain.doFilter(request, response);
        } finally {
            SecurityContextHolder.clearContext();
        }
    }
}
