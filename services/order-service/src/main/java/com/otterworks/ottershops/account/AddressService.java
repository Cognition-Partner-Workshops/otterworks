package com.otterworks.ottershops.account;

import com.otterworks.ottershops.common.ApiException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Set;
import java.util.UUID;

@Service
public class AddressService {
    public static final int MAX_ADDRESSES = 10;
    static final Set<String> STATES = Set.of("AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID",
            "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM",
            "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY");
    private final JdbcTemplate jdbc;

    public AddressService(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public record Address(UUID id, String label, String name, String line1, String line2, String city, String state,
                          String zip, String phone, boolean isDefault) {}

    public record Input(String label, String name, String line1, String line2, String city, String state, String zip,
                        String phone, Boolean isDefault) {}

    public List<Address> list(UUID customerId) {
        return jdbc.query("""
                SELECT id, label, name, line1, line2, city, state, zip, phone, is_default FROM customer_addresses
                WHERE customer_id = ? ORDER BY is_default DESC, created_at""", (rs, i) -> new Address(
                rs.getObject(1, UUID.class), rs.getString(2), rs.getString(3), rs.getString(4), rs.getString(5),
                rs.getString(6), rs.getString(7), rs.getString(8), rs.getString(9), rs.getBoolean(10)), customerId);
    }

    static Input validate(Input in) {
        if (in == null || blank(in.name()) || blank(in.line1()) || blank(in.city())) {
            throw ApiException.badRequest("ADDRESS_INCOMPLETE", "Name, street address and city are required");
        }
        String state = in.state() == null ? "" : in.state().trim().toUpperCase();
        if (!STATES.contains(state)) throw ApiException.badRequest("STATE_INVALID", "Choose a US state");
        String zip = in.zip() == null ? "" : in.zip().trim();
        if (!zip.matches("\\d{5}(-\\d{4})?")) throw ApiException.badRequest("ZIP_INVALID", "Enter a 5-digit ZIP code");
        return new Input(trim(in.label()), in.name().trim(), in.line1().trim(), trim(in.line2()), in.city().trim(), state,
                zip, trim(in.phone()), in.isDefault());
    }

    @Transactional
    public List<Address> add(UUID customerId, Input raw) {
        Input in = validate(raw);
        List<Address> existing = list(customerId);
        if (existing.size() >= MAX_ADDRESSES) throw ApiException.badRequest("ADDRESS_LIMIT", "You can save up to 10 addresses");
        boolean makeDefault = existing.isEmpty() || Boolean.TRUE.equals(in.isDefault());
        if (makeDefault) jdbc.update("UPDATE customer_addresses SET is_default = FALSE WHERE customer_id = ?", customerId);
        jdbc.update("""
                INSERT INTO customer_addresses (id, customer_id, label, name, line1, line2, city, state, zip, phone, is_default)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", UUID.randomUUID(), customerId, in.label(), in.name(), in.line1(),
                in.line2(), in.city(), in.state(), in.zip(), in.phone(), makeDefault);
        return list(customerId);
    }

    @Transactional
    public List<Address> makeDefault(UUID customerId, UUID id) {
        owned(customerId, id);
        jdbc.update("UPDATE customer_addresses SET is_default = (id = ?) WHERE customer_id = ?", id, customerId);
        return list(customerId);
    }

    @Transactional
    public List<Address> delete(UUID customerId, UUID id) {
        boolean wasDefault = owned(customerId, id).isDefault();
        jdbc.update("DELETE FROM customer_addresses WHERE id = ? AND customer_id = ?", id, customerId);
        if (wasDefault) {
            jdbc.update("""
                    UPDATE customer_addresses SET is_default = TRUE WHERE id = (
                      SELECT id FROM customer_addresses WHERE customer_id = ? ORDER BY created_at LIMIT 1)""", customerId);
        }
        return list(customerId);
    }

    Address owned(UUID customerId, UUID id) {
        return list(customerId).stream().filter(a -> a.id().equals(id)).findFirst()
                .orElseThrow(() -> ApiException.notFound("Address"));
    }

    static boolean blank(String s) {
        return s == null || s.isBlank();
    }

    static String trim(String s) {
        return blank(s) ? null : s.trim();
    }
}
