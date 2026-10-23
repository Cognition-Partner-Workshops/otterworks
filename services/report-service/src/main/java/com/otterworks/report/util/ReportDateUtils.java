package com.otterworks.report.util;

import org.apache.commons.lang3.StringUtils;
import org.apache.commons.lang3.time.DateUtils;

import java.text.ParseException;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.Calendar;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;

/**
 * Date utility class: java.util.Date in, strings out.
 *
 * Every formatted string is in UTC. The service runs with TZ=America/Chicago, and the CSV/Excel/PDF
 * banners, file names and upstream query strings are all pinned to UTC, so none of these formatters
 * may use ZoneId.systemDefault().
 *
 * LEGACY PATTERNS:
 * 1. java.util.Date everywhere (target: java.time.Instant / LocalDateTime / ZonedDateTime)
 * 2. Calendar manipulation (target: java.time.temporal.ChronoUnit / Period)
 */
public final class ReportDateUtils {

    // DateTimeFormatter is immutable and thread-safe, unlike the SimpleDateFormat instances it replaces.
    private static final DateTimeFormatter ISO_FORMAT =
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).withZone(ZoneOffset.UTC);
    private static final DateTimeFormatter DISPLAY_FORMAT =
            DateTimeFormatter.ofPattern("MMM dd, yyyy HH:mm", Locale.US).withZone(ZoneOffset.UTC);
    private static final DateTimeFormatter FILE_NAME_FORMAT =
            DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss", Locale.US).withZone(ZoneOffset.UTC);

    private ReportDateUtils() {
        // Utility class
    }

    /**
     * Format a Date to ISO 8601 string (UTC).
     */
    public static String toIsoString(Date date) {
        if (date == null) {
            return null;
        }
        return ISO_FORMAT.format(date.toInstant());
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
     * LEGACY: lenient Commons Lang DateUtils parsing in the JVM default time zone.
     */
    public static Date parseIsoDate(String dateString) {
        if (StringUtils.isBlank(dateString)) {
            return null;
        }
        try {
            return DateUtils.parseDate(dateString, new String[]{
                    "yyyy-MM-dd'T'HH:mm:ss'Z'",
                    "yyyy-MM-dd'T'HH:mm:ssZ",
                    "yyyy-MM-dd HH:mm:ss",
                    "yyyy-MM-dd"
            });
        } catch (ParseException e) {
            throw new IllegalArgumentException("Cannot parse date: " + dateString, e);
        }
    }

    /**
     * Get the start of today (midnight UTC).
     * LEGACY: Calendar manipulation instead of LocalDate.atStartOfDay().
     */
    public static Date startOfToday() {
        Calendar cal = Calendar.getInstance(TimeZone.getTimeZone("UTC"));
        cal.set(Calendar.HOUR_OF_DAY, 0);
        cal.set(Calendar.MINUTE, 0);
        cal.set(Calendar.SECOND, 0);
        cal.set(Calendar.MILLISECOND, 0);
        return cal.getTime();
    }

    /**
     * Get the start of this month.
     * LEGACY: Calendar manipulation instead of YearMonth.
     */
    public static Date startOfMonth() {
        Calendar cal = Calendar.getInstance(TimeZone.getTimeZone("UTC"));
        cal.set(Calendar.DAY_OF_MONTH, 1);
        cal.set(Calendar.HOUR_OF_DAY, 0);
        cal.set(Calendar.MINUTE, 0);
        cal.set(Calendar.SECOND, 0);
        cal.set(Calendar.MILLISECOND, 0);
        return cal.getTime();
    }

    /**
     * Subtract days from a date.
     * LEGACY: Commons Lang DateUtils.addDays with negative value.
     */
    public static Date daysAgo(int days) {
        return DateUtils.addDays(new Date(), -days);
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
