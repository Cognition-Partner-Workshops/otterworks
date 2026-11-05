package com.bank.kyc;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configuration.WebSecurityConfigurerAdapter;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

@Configuration
@EnableWebSecurity
public class SecurityConfig extends WebSecurityConfigurerAdapter {
    @Value("${JWT_SECRET:}") private String jwtSecret;

    @Override protected void configure(HttpSecurity http) throws Exception {
        http.csrf().disable().sessionManagement().sessionCreationPolicy(SessionCreationPolicy.STATELESS)
            .and().exceptionHandling().authenticationEntryPoint((request, response, error) -> response.sendError(401))
            .and().authorizeRequests()
            .antMatchers("/health", "/actuator/health").permitAll()
            .antMatchers(HttpMethod.POST, "/documents/**")
                .access("hasRole('SERVICE') and authentication.name == 'onboarding-service'")
            .antMatchers(HttpMethod.GET, "/documents/**").hasAnyRole("COMPLIANCE", "ADMIN")
            .anyRequest().authenticated()
            .and().addFilterBefore(new JwtAuthenticationFilter(jwtSecret), UsernamePasswordAuthenticationFilter.class);
    }
}
