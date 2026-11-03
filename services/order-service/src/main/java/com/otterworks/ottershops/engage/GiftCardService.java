package com.otterworks.ottershops.engage;

import com.otterworks.ottershops.common.ApiException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDate;
import java.util.HexFormat;
import java.util.List;

@Service
public class GiftCardService {
    private final JdbcTemplate jdbc;

    public GiftCardService(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public record Balance(String last4, int balanceCents, LocalDate expiresOn) {}

    record Row(String pinHash, int balanceCents, LocalDate expiresOn) {}

    static String digits(String s) {
        return s == null ? "" : s.replaceAll("[\\s-]", "");
    }

    static String hash(String number, String pin) {
        try {
            byte[] d = MessageDigest.getInstance("SHA-256").digest((number + ":" + pin).getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(d);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    /** A wrong number and a wrong PIN get the same answer, so the endpoint can't be used to find valid numbers. */
    public Balance balance(String rawNumber, String rawPin) {
        String number = digits(rawNumber);
        String pin = digits(rawPin);
        if (!number.matches("\\d{16}") || !pin.matches("\\d{4}")) {
            throw ApiException.badRequest("GIFT_CARD_INVALID", "Enter the 16-digit card number and 4-digit PIN");
        }
        List<Row> rows = jdbc.query("SELECT pin_hash, balance_cents, expires_on FROM gift_cards WHERE number = ?",
                (rs, i) -> new Row(rs.getString(1), rs.getInt(2), rs.getObject(3, LocalDate.class)), number);
        if (rows.isEmpty() || !MessageDigest.isEqual(rows.get(0).pinHash().getBytes(StandardCharsets.UTF_8),
                hash(number, pin).getBytes(StandardCharsets.UTF_8))) {
            throw ApiException.notFound("Gift card with that number and PIN");
        }
        Row r = rows.get(0);
        return new Balance(number.substring(12), r.balanceCents(), r.expiresOn());
    }
}
