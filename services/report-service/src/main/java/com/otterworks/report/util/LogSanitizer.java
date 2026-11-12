package com.otterworks.report.util;

/**
 * Strips line breaks from user-supplied values before they reach a log line so a
 * caller cannot forge extra log entries.
 */
public final class LogSanitizer {

    private LogSanitizer() {
    }

    public static String clean(Object value) {
        if (value == null) {
            return null;
        }
        return String.valueOf(value).replaceAll("[\\r\\n]", "_");
    }
}
