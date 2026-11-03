package com.otterworks.ottershops.auth;

import com.otterworks.ottershops.common.ApiException;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Clock;
import java.time.Duration;
import java.util.Base64;
import java.util.HexFormat;
import java.util.Optional;
import java.util.UUID;
import java.util.regex.Pattern;

@Service
public class AuthService {
    public static final Duration SESSION_TTL = Duration.ofDays(30);
    private static final Pattern EMAIL = Pattern.compile("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$");
    private static final SecureRandom RANDOM = new SecureRandom();

    private final CustomerRepository customers;
    private final BCryptPasswordEncoder encoder = new BCryptPasswordEncoder();
    private final Clock clock;

    public AuthService(CustomerRepository customers, Clock clock) {
        this.customers = customers;
        this.clock = clock;
    }

    public record Session(String token, Customer customer) {}

    public Customer register(String email, String password, String firstName, String lastName) {
        String normalized = normalizeEmail(email);
        if (password == null || password.length() < 8) {
            throw ApiException.badRequest("PASSWORD_TOO_SHORT", "Use at least 8 characters for your password");
        }
        if (customers.findByEmail(normalized).isPresent()) {
            throw new ApiException(HttpStatus.CONFLICT, "EMAIL_TAKEN", "An account already exists for " + normalized);
        }
        UUID id = UUID.randomUUID();
        customers.insert(id, normalized, encoder.encode(password), trim(firstName), trim(lastName));
        return customers.findById(id).orElseThrow();
    }

    public Session login(String email, String password) {
        String normalized = normalizeEmail(email);
        String hash = customers.passwordHash(normalized).orElse(null);
        if (hash == null || password == null || !encoder.matches(password, hash)) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "INVALID_CREDENTIALS", "That email and password don't match");
        }
        Customer customer = customers.findByEmail(normalized).orElseThrow();
        return new Session(startSession(customer.id()), customer);
    }

    public String startSession(UUID customerId) {
        byte[] raw = new byte[32];
        RANDOM.nextBytes(raw);
        String token = Base64.getUrlEncoder().withoutPadding().encodeToString(raw);
        customers.createSession(digest(token), customerId, clock.instant().plus(SESSION_TTL));
        return token;
    }

    public Optional<Customer> resolve(String token) {
        if (token == null || token.isBlank()) return Optional.empty();
        return customers.sessionCustomer(digest(token)).flatMap(customers::findById);
    }

    public void logout(String token) {
        if (token != null && !token.isBlank()) customers.deleteSession(digest(token));
    }

    public String hash(String password) {
        return encoder.encode(password);
    }

    public static String normalizeEmail(String email) {
        String e = email == null ? "" : email.trim().toLowerCase();
        if (!EMAIL.matcher(e).matches()) throw ApiException.badRequest("EMAIL_INVALID", "Enter a valid email address");
        return e;
    }

    private static String trim(String s) {
        return s == null || s.isBlank() ? null : s.trim();
    }

    /** Sessions are stored hashed so a database read does not hand out live tokens. */
    static String digest(String token) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(token.getBytes()));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
