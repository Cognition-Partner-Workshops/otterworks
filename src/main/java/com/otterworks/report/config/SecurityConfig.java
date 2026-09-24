package com.otterworks.report.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;

/**
 * Security configuration using the SecurityFilterChain @Bean pattern.
 *
 * UPGRADE NOTES:
 * - Replaced extends WebSecurityConfigurerAdapter with a @Bean SecurityFilterChain method
 * - Replaced antMatchers() with requestMatchers()
 * - Replaced authorizeRequests() with authorizeHttpRequests()
 * - Move from javax.servlet to jakarta.servlet
 */
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        // nosemgrep: java.spring.security.audit.spring-csrf-disabled.spring-csrf-disabled
        http
            .csrf(csrf -> csrf.disable())
            .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/health", "/metrics", "/actuator/**").permitAll()
                .requestMatchers("/swagger-ui/**", "/swagger-ui.html", "/v3/api-docs/**").permitAll()
                .requestMatchers("/api/v1/reports/**").permitAll()  // TODO: Add JWT validation
            )
            .headers(headers -> headers
                .frameOptions(frame -> frame.deny())
                .contentTypeOptions(content -> {})
                .xssProtection(xss -> {})
            );
        return http.build();
    }
}
