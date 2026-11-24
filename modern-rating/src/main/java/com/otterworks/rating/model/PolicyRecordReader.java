package com.otterworks.rating.model;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;

/** Reads the 80-byte POLREC layout shared with the batch system. */
public final class PolicyRecordReader {

    private static final String POSITIVE = "{ABCDEFGHI";
    private static final String NEGATIVE = "}JKLMNOPQR";
    private static final DateTimeFormatter YYYYMMDD = DateTimeFormatter.BASIC_ISO_DATE;

    private PolicyRecordReader() {}

    public static Policy read(String raw) {
        String r = String.format("%-80s", raw);
        return new Policy(
                r.substring(0, 8).trim(),
                r.substring(8, 10),
                r.substring(10, 12),
                r.substring(12, 17).trim(),
                r.substring(17, 20),
                LocalDate.parse(r.substring(20, 28), YYYYMMDD),
                zoned(r.substring(28, 37), 2),
                Integer.parseInt(r.substring(37, 39)),
                Integer.parseInt(r.substring(39, 41)),
                Integer.parseInt(r.substring(41, 46)),
                r.charAt(46) == 'Y',
                zoned(r.substring(47, 50), 2),
                Integer.parseInt(r.substring(50, 52)),
                r.charAt(52) == 'Y',
                r.charAt(53) == 'Y',
                r.charAt(54) == 'Y');
    }

    /** Zoned decimal whose last character carries the final digit and the sign. */
    static BigDecimal zoned(String field, int scale) {
        char last = field.charAt(field.length() - 1);
        String head = field.substring(0, field.length() - 1);
        int digit;
        boolean negative = false;
        if (Character.isDigit(last)) {
            digit = last - '0';
        } else if (POSITIVE.indexOf(last) >= 0) {
            digit = POSITIVE.indexOf(last);
        } else if (NEGATIVE.indexOf(last) >= 0) {
            digit = NEGATIVE.indexOf(last);
            negative = true;
        } else {
            throw new IllegalArgumentException("not a zoned decimal: " + field);
        }
        BigDecimal value = new BigDecimal(head + digit).movePointLeft(scale);
        return negative ? value.negate() : value;
    }
}
