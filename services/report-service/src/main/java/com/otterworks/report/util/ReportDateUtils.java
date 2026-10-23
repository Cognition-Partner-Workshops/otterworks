package com.otterworks.report.util;

import org.apache.commons.lang3.StringUtils;

import java.text.ParsePosition;
import java.text.SimpleDateFormat;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Date;

/**
 * Date formatting and range helpers with UTC output and legacy-compatible parsing.
 */
public final class ReportDateUtils {

    private static final DateTimeFormatter ISO_FORMAT =
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss'Z'").withZone(ZoneOffset.UTC);
    private static final DateTimeFormatter DISPLAY_FORMAT =
            DateTimeFormatter.ofPattern("MMM dd, yyyy HH:mm").withZone(ZoneOffset.UTC);
    private static final DateTimeFormatter FILE_NAME_FORMAT =
            DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss").withZone(ZoneOffset.UTC);

    private ReportDateUtils() {
        // Utility class
    }

    /**
     * Format a Date to ISO 8601 string.
     */
    public static String toIsoString(Date date) {
        return date == null ? null : ISO_FORMAT.format(date.toInstant());
    }

    /**
     * Format a Date for display purposes.
     */
    public static String toDisplayString(Date date) {
        if (date == null) {
            return "N/A";
        }
        return DISPLAY_FORMAT.format(date.toInstant());
    }

    /**
     * Format a Date for use in file names.
     */
    public static String toFileNameString(Date date) {
        if (date == null) {
            date = new Date();
        }
        return FILE_NAME_FORMAT.format(date.toInstant());
    }

    /**
     * Parse an ISO 8601 date string.
     */
    public static Date parseIsoDate(String dateString) {
        if (StringUtils.isBlank(dateString)) {
            return null;
        }

        // Keep the legacy default-zone, lenient parsing semantics.
        String[] patterns = {
                "yyyy-MM-dd'T'HH:mm:ss'Z'",
                "yyyy-MM-dd'T'HH:mm:ssZ",
                "yyyy-MM-dd HH:mm:ss",
                "yyyy-MM-dd"
        };
        for (String pattern : patterns) {
            SimpleDateFormat format = new SimpleDateFormat(pattern);
            format.setLenient(true);
            ParsePosition position = new ParsePosition(0);
            Date parsed = format.parse(dateString, position);
            if (parsed != null && position.getIndex() == dateString.length()) {
                return parsed;
            }
        }
        throw new IllegalArgumentException("Cannot parse date: " + dateString);
    }

    /**
     * Get the start of today (midnight UTC).
     */
    public static Date startOfToday() {
        return Date.from(LocalDate.now(ZoneOffset.UTC).atStartOfDay(ZoneOffset.UTC).toInstant());
    }

    /**
     * Get the start of this month (midnight UTC).
     */
    public static Date startOfMonth() {
        return Date.from(YearMonth.now(ZoneOffset.UTC).atDay(1).atStartOfDay(ZoneOffset.UTC).toInstant());
    }

    /**
     * Subtract calendar days in the JVM default time zone.
     */
    public static Date daysAgo(int days) {
        return Date.from(ZonedDateTime.now().minusDays(days).toInstant());
    }

    /**
     * Check if a date falls within a range (inclusive).
     */
    public static boolean isWithinRange(Date date, Date start, Date end) {
        if (date == null || start == null || end == null) {
            return false;
        }
        return !date.before(start) && !date.after(end);
    }

    /**
     * Calculate duration between two dates in a human-readable format.
     * LEGACY: Manual millisecond arithmetic instead of Duration.between().
     */
    public static String humanReadableDuration(Date start, Date end) {
        if (start == null || end == null) {
            return "unknown";
        }
        long diffMs = end.getTime() - start.getTime();
        long seconds = diffMs / 1000;
        long minutes = seconds / 60;
        long hours = minutes / 60;

        if (hours > 0) {
            return hours + "h " + (minutes % 60) + "m";
        } else if (minutes > 0) {
            return minutes + "m " + (seconds % 60) + "s";
        } else {
            return seconds + "s";
        }
    }
}
