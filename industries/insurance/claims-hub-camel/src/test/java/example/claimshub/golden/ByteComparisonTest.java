package example.claimshub.golden;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;

import org.junit.jupiter.api.Test;

class ByteComparisonTest {

    private static byte[] b(String s) {
        return s.getBytes(StandardCharsets.UTF_8);
    }

    @Test
    void identicalBytesMatch() {
        assertThat(ByteComparison.of(b("<a>1.00</a>"), b("<a>1.00</a>")).identical()).isTrue();
    }

    @Test
    void namesTheFirstDifferingByte() {
        ByteComparison c = ByteComparison.of(b("<a>1002.50</a>"), b("<a>1002.51</a>"));
        assertThat(c.identical()).isFalse();
        assertThat(c.cause()).startsWith("first difference at byte 9");
    }

    @Test
    void aTrailingNewlineIsADifference() {
        ByteComparison c = ByteComparison.of(b("<a/>"), b("<a/>\n"));
        assertThat(c.identical()).isFalse();
        assertThat(c.cause()).contains("golden 4 bytes, actual 5 bytes");
    }
}
