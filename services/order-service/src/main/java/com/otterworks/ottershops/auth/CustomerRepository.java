package com.otterworks.ottershops.auth;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;

@Repository
public class CustomerRepository {
    private static final RowMapper<Customer> MAPPER = (rs, i) -> new Customer(
            rs.getObject("id", UUID.class), rs.getString("email"), rs.getString("first_name"),
            rs.getString("last_name"), rs.getInt("rewards_points"), rs.getTimestamp("created_at").toInstant());

    private final JdbcTemplate jdbc;

    public CustomerRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<Customer> findById(UUID id) {
        return jdbc.query("SELECT * FROM customers WHERE id = ?", MAPPER, id).stream().findFirst();
    }

    public Optional<Customer> findByEmail(String email) {
        return jdbc.query("SELECT * FROM customers WHERE lower(email) = lower(?)", MAPPER, email).stream().findFirst();
    }

    public Optional<String> passwordHash(String email) {
        return jdbc.queryForList("SELECT password_hash FROM customers WHERE lower(email) = lower(?)", String.class, email)
                .stream().findFirst();
    }

    public void insert(UUID id, String email, String hash, String first, String last) {
        jdbc.update("INSERT INTO customers (id, email, password_hash, first_name, last_name) VALUES (?, ?, ?, ?, ?)",
                id, email.toLowerCase(), hash, first, last);
    }

    public void addPoints(UUID id, int points) {
        jdbc.update("UPDATE customers SET rewards_points = rewards_points + ?, updated_at = now() WHERE id = ?", points, id);
    }

    public void createSession(String token, UUID customerId, Instant expiresAt) {
        jdbc.update("INSERT INTO customer_sessions (token, customer_id, expires_at) VALUES (?, ?, ?)",
                token, customerId, Timestamp.from(expiresAt));
    }

    public Optional<UUID> sessionCustomer(String token) {
        return jdbc.queryForList("SELECT customer_id FROM customer_sessions WHERE token = ? AND expires_at > now()",
                UUID.class, token).stream().findFirst();
    }

    public void deleteSession(String token) {
        jdbc.update("DELETE FROM customer_sessions WHERE token = ?", token);
    }
}
