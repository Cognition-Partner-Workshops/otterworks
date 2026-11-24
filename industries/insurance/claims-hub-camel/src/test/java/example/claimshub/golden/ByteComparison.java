package example.claimshub.golden;

import java.nio.charset.StandardCharsets;

/** Byte-for-byte comparison of a map output with its golden, with the first divergence described. */
public record ByteComparison(boolean identical, String cause) {

    private static final int CONTEXT = 40;

    public static ByteComparison of(byte[] expected, byte[] actual) {
        int limit = Math.min(expected.length, actual.length);
        int at = 0;
        while (at < limit && expected[at] == actual[at]) {
            at++;
        }
        if (at == limit && expected.length == actual.length) {
            return new ByteComparison(true, "");
        }
        String cause = "first difference at byte " + at
                + " (golden " + expected.length + " bytes, actual " + actual.length + " bytes): golden \""
                + excerpt(expected, at) + "\", actual \"" + excerpt(actual, at) + "\"";
        return new ByteComparison(false, cause);
    }

    private static String excerpt(byte[] bytes, int at) {
        int from = Math.max(0, at - 10);
        int to = Math.min(bytes.length, at + CONTEXT);
        if (from >= to) {
            return "<end of output>";
        }
        return new String(bytes, from, to - from, StandardCharsets.UTF_8)
                .replace("\r", "\\r").replace("\n", "\\n").replace("|", "\\|");
    }
}
