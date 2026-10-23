package com.otterworks.report.util;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;

import java.time.Instant;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

public class ReportDateUtilsTest {

    private TimeZone originalTimeZone;
    private Locale originalLocale;

    @Before
    public void setUp() {
        originalTimeZone = TimeZone.getDefault();
        originalLocale = Locale.getDefault();
        TimeZone.setDefault(TimeZone.getTimeZone("America/Chicago"));
        Locale.setDefault(Locale.US);
    }

    @After
    public void tearDown() {
        TimeZone.setDefault(originalTimeZone);
        Locale.setDefault(originalLocale);
    }

    @Test
    public void formatsDatesInUtc() {
        Date date = Date.from(Instant.parse("2026-01-01T03:30:00Z"));

        assertEquals("Jan 01, 2026 03:30", ReportDateUtils.toDisplayString(date));
        assertEquals("2026-01-01T03:30:00Z", ReportDateUtils.toIsoString(date));
        assertEquals("20260101_033000", ReportDateUtils.toFileNameString(date));
    }

    @Test
    public void preservesNullFormattingBehavior() {
        assertNull(ReportDateUtils.toIsoString(null));
        assertEquals("N/A", ReportDateUtils.toDisplayString(null));
        assertTrue(ReportDateUtils.toFileNameString(null).matches("\\d{8}_\\d{6}"));
    }

    @Test
    public void startOfTodayAndMonthAreUtcMidnight() {
        LocalDate todayUtc = LocalDate.now(ZoneOffset.UTC);
        Date startOfToday = ReportDateUtils.startOfToday();
        Date startOfMonth = ReportDateUtils.startOfMonth();

        assertEquals(Date.from(todayUtc.atStartOfDay(ZoneOffset.UTC).toInstant()), startOfToday);
        assertEquals(Date.from(YearMonth.from(todayUtc).atDay(1).atStartOfDay(ZoneOffset.UTC).toInstant()), startOfMonth);
        assertEquals(0, startOfToday.toInstant().atZone(ZoneOffset.UTC).toLocalTime().toSecondOfDay());
        assertEquals(0, startOfMonth.toInstant().atZone(ZoneOffset.UTC).toLocalTime().toSecondOfDay());
    }

    @Test
    public void formatsHumanReadableDurations() {
        Date start = new Date(0);

        assertEquals("3s", ReportDateUtils.humanReadableDuration(start, new Date(3_000)));
        assertEquals("1m 5s", ReportDateUtils.humanReadableDuration(start, new Date(65_000)));
        assertEquals("1h 1m", ReportDateUtils.humanReadableDuration(start, new Date(3_660_000)));
        assertEquals("unknown", ReportDateUtils.humanReadableDuration(null, new Date(0)));
    }

    @Test
    public void parsesDateAtChicagoMidnightAndHandlesInvalidInput() {
        Date expected = Date.from(LocalDate.of(2026, 1, 1)
                .atStartOfDay(ZoneId.of("America/Chicago"))
                .toInstant());

        assertEquals(expected, ReportDateUtils.parseIsoDate("2026-01-01"));
        assertNull(ReportDateUtils.parseIsoDate(""));
        try {
            ReportDateUtils.parseIsoDate("not-a-date");
            fail("Expected IllegalArgumentException");
        } catch (IllegalArgumentException exception) {
            assertEquals("Cannot parse date: not-a-date", exception.getMessage());
        }
    }
}
