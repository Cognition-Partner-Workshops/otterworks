package com.bank.kyc;

import java.util.ArrayList;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.WebSecurityConfigurerAdapter;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.provisioning.InMemoryUserDetailsManager;

@Configuration
public class SecurityConfig extends WebSecurityConfigurerAdapter {

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    public UserDetailsService serviceUsers(
            @Value("${kyc.auth.uploader.username}") String uploader,
            @Value("${kyc.auth.uploader.password-hash}") String uploaderHash,
            @Value("${kyc.auth.reviewer.username}") String reviewer,
            @Value("${kyc.auth.reviewer.password-hash}") String reviewerHash) {
        List<UserDetails> users = new ArrayList<>();
        addUser(users, uploader, uploaderHash, "UPLOADER");
        addUser(users, reviewer, reviewerHash, "REVIEWER");
        return new InMemoryUserDetailsManager(users);
    }

    private static void addUser(List<UserDetails> users, String username, String hash, String role) {
        if (!username.isBlank() && !hash.isBlank()) {
            users.add(User.withUsername(username).password(hash).roles(role).build());
        }
    }

    @Override
    protected void configure(HttpSecurity http) throws Exception {
        // No cookies or sessions: callers authenticate each request with HTTP Basic.
        http.csrf().disable()
                .sessionManagement().sessionCreationPolicy(SessionCreationPolicy.STATELESS)
                .and().requestCache().disable()
                .authorizeRequests()
                .antMatchers(HttpMethod.POST, "/documents/*").hasRole("UPLOADER")
                .antMatchers(HttpMethod.GET, "/documents/*").hasRole("REVIEWER")
                .anyRequest().denyAll()
                .and().httpBasic();
    }
}
