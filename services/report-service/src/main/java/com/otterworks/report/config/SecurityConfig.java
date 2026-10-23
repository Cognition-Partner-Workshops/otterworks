package com.otterworks.report.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.header.writers.XXssProtectionHeaderWriter;

/**
 * Spring Security 6 configuration: a {@link SecurityFilterChain} bean with the same access rules
 * as the former WebSecurityConfigurerAdapter.
 *
 * Spring Security 5's authorizeRequests() let unmatched requests through and did not check error
 * dispatches; authorizeHttpRequests() denies both by default, so anyRequest().permitAll() keeps the
 * previous behaviour (unknown paths and /error still answer 404/405/400, not 403).
 */
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http // nosemgrep: java.spring.security.audit.spring-csrf-disabled.spring-csrf-disabled
            .csrf(AbstractHttpConfigurer::disable)
            .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/health", "/metrics", "/actuator/**").permitAll()
                .requestMatchers("/swagger-ui/**", "/swagger-resources/**", "/v2/api-docs/**").permitAll()
                .requestMatchers("/api/v1/reports/**").permitAll()  // TODO: Add JWT validation
                .requestMatchers("/api/reports/reconciliation/**", "/api/archive/**", "/api/v1/archive/**").permitAll()
                .anyRequest().permitAll())
            .headers(headers -> headers
                .frameOptions(frame -> frame.deny())
                .contentTypeOptions(Customizer.withDefaults())
                .xssProtection(xss -> xss.headerValue(XXssProtectionHeaderWriter.HeaderValue.ENABLED_MODE_BLOCK)));
        return http.build();
    }
}
