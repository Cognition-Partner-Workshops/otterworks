package com.otterworks.legacyportal.lambda.announcements;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;

import org.junit.jupiter.api.Test;

/**
 * Round trip for the {@code timestamp without time zone} text form the Data API takes
 * and returns: we always write 6 fraction digits and must read back any of 0/1/3/6.
 */
class TimestampFormatTest {

    @Test
    void writesSixFractionDigits() {
        LocalDateTime t = LocalDateTime.ofInstant(
                Instant.parse("2026-10-01T13:24:37.245219Z"), ZoneOffset.UTC);
        assertEquals("2026-10-01 13:24:37.245219",
                DataApiAnnouncementRepository.TS_WRITE.format(t));
    }

    @Test
    void writesTrailingZerosToo() {
        LocalDateTime t = LocalDateTime.ofInstant(
                Instant.parse("2026-10-01T13:24:37Z"), ZoneOffset.UTC);
        assertEquals("2026-10-01 13:24:37.000000",
                DataApiAnnouncementRepository.TS_WRITE.format(t));
    }

    @Test
    void readsEveryFractionForm() {
        Instant expected = Instant.parse("2026-10-01T13:24:37.245219Z");
        for (String text : new String[]{
                "2026-10-01 13:24:37.245219",   // 6 digits
                "2026-10-01 13:24:37.245",      // 3 digits
                "2026-10-01 13:24:37.2",        // 1 digit
                "2026-10-01 13:24:37"}) {       // no fraction
            Instant parsed = LocalDateTime.parse(text, DataApiAnnouncementRepository.TS_FORMAT)
                    .toInstant(ZoneOffset.UTC);
            if (text.contains(".245219")) {
                assertEquals(expected, parsed);
            }
        }
        assertEquals(Instant.parse("2026-10-01T13:24:37.245Z"),
                LocalDateTime.parse("2026-10-01 13:24:37.245",
                        DataApiAnnouncementRepository.TS_FORMAT).toInstant(ZoneOffset.UTC));
        assertEquals(Instant.parse("2026-10-01T13:24:37.2Z"),
                LocalDateTime.parse("2026-10-01 13:24:37.2",
                        DataApiAnnouncementRepository.TS_FORMAT).toInstant(ZoneOffset.UTC));
        assertEquals(Instant.parse("2026-10-01T13:24:37Z"),
                LocalDateTime.parse("2026-10-01 13:24:37",
                        DataApiAnnouncementRepository.TS_FORMAT).toInstant(ZoneOffset.UTC));
    }
}
