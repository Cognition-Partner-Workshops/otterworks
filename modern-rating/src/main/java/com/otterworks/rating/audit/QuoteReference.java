package com.otterworks.rating.audit;

import com.otterworks.rating.model.Quote;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

/** Short reference an underwriter reads back over the phone to find a saved quote. */
public final class QuoteReference {

    private QuoteReference() {}

    public static String of(Quote quote) {
        return digest(quote.asLine());
    }

    static String digest(String line) {
        try {
            MessageDigest md = MessageDigest.getInstance("MD5");
            byte[] sum = md.digest(line.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(sum).substring(0, 12).toUpperCase(java.util.Locale.ROOT);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
