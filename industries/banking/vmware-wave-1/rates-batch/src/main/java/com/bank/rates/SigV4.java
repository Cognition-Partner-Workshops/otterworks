package com.bank.rates;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.Map;
import java.util.TreeMap;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

final class SigV4 {
    static String encodePath(String path) {
        StringBuilder out = new StringBuilder();
        for (byte b : path.getBytes(StandardCharsets.UTF_8)) {
            int c = b & 255;
            if (c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' || c >= '0' && c <= '9'
                    || c == '-' || c == '_' || c == '.' || c == '~' || c == '/') out.append((char) c);
            else out.append(String.format("%%%02X", c));
        }
        return out.toString();
    }
    static String hex(byte[] bytes) {
        StringBuilder out = new StringBuilder();
        for (byte b : bytes) out.append(String.format("%02x", b & 255));
        return out.toString();
    }
    static String hash(byte[] data) {
        try { return hex(MessageDigest.getInstance("SHA-256").digest(data)); }
        catch (Exception e) { throw new IllegalStateException(e); }
    }
    private static byte[] hmac(byte[] key, String text) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(key, "HmacSHA256"));
            return mac.doFinal(text.getBytes(StandardCharsets.UTF_8));
        } catch (Exception e) { throw new IllegalStateException(e); }
    }
    static String timestamp(Instant now) {
        return DateTimeFormatter.ofPattern("yyyyMMdd'T'HHmmss'Z'").withZone(ZoneOffset.UTC).format(now);
    }
    static String authorization(String method, String path, Map<String, String> headers,
                                String payloadHash, String region, String access, String secret) {
        TreeMap<String, String> sorted = new TreeMap<>();
        headers.forEach((k, v) -> sorted.put(k.toLowerCase(java.util.Locale.ROOT), v.trim().replaceAll("\\s+", " ")));
        StringBuilder canonicalHeaders = new StringBuilder();
        sorted.forEach((k, v) -> canonicalHeaders.append(k).append(':').append(v).append('\n'));
        String signed = String.join(";", sorted.keySet());
        String canonical = method + "\n" + path + "\n\n" + canonicalHeaders + "\n" + signed + "\n" + payloadHash;
        String time = sorted.get("x-amz-date"), date = time.substring(0, 8);
        String scope = date + "/" + region + "/s3/aws4_request";
        String toSign = "AWS4-HMAC-SHA256\n" + time + "\n" + scope + "\n" + hash(canonical.getBytes(StandardCharsets.UTF_8));
        byte[] key = hmac(("AWS4" + secret).getBytes(StandardCharsets.UTF_8), date);
        key = hmac(hmac(hmac(key, region), "s3"), "aws4_request");
        return "AWS4-HMAC-SHA256 Credential=" + access + "/" + scope + ", SignedHeaders=" + signed
                + ", Signature=" + hex(hmac(key, toSign));
    }
}
