package com.otterworks.commission.common;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

/**
 * Oracle's default text conversions, which leak into messages and audit detail
 * (rule R38): TO_CHAR(number) drops trailing zeros and the leading zero
 * (8.50 -> "8.5", 0.5 -> ".5", -0.5 -> "-.5"); NULL || 'x' is 'x'.
 */
public final class OracleText {

    /** Wire format the package delegate uses for DATE values. */
    public static final DateTimeFormatter WIRE_DATE = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final DateTimeFormatter ISO_DAY = DateTimeFormatter.ofPattern("yyyy-MM-dd");

    private OracleText() {
    }

    /** TO_CHAR(n) with no format model; null becomes "" as in string concatenation. */
    public static String toChar(BigDecimal n) {
        if (n == null) {
            return "";
        }
        if (n.signum() == 0) {
            return "0";
        }
        String s = n.stripTrailingZeros().toPlainString();
        if (s.startsWith("0.")) {
            return s.substring(1);
        }
        if (s.startsWith("-0.")) {
            return "-" + s.substring(2);
        }
        return s;
    }

    /** TO_CHAR(n) for an integer column such as an id; null becomes "". */
    public static String toChar(Long n) {
        return n == null ? "" : Long.toString(n);
    }

    /** TO_CHAR(d, 'YYYY-MM-DD'). */
    public static String isoDay(LocalDateTime d) {
        return d == null ? "" : ISO_DAY.format(d);
    }

    /** Parses a DATE sent by the delegate as TO_CHAR(d, 'YYYY-MM-DD HH24:MI:SS'). */
    public static LocalDateTime parseWireDate(String s) {
        return s == null ? null : LocalDateTime.parse(s, WIRE_DATE);
    }

    /** Parses a NUMBER sent by the delegate as TO_CHAR(n); accepts ".5" and "-.5". */
    public static BigDecimal parseNumber(String s) {
        return s == null ? null : new BigDecimal(s);
    }
}
