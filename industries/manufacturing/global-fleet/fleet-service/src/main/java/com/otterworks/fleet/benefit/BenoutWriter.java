package com.otterworks.fleet.benefit;

import java.io.ByteArrayOutputStream;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.math.RoundingMode;
import java.nio.charset.StandardCharsets;
import java.util.Comparator;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.stereotype.Component;

@Component
public class BenoutWriter {

    private static final Pattern MAINFRAME_REFERENCE = Pattern.compile("^MF:(\\d+)$");

    public byte[] write(String period, List<BenefitCalculator.Calculation> calculations) {
        if (period == null || !period.matches("\\d{6}")) {
            throw new IllegalArgumentException("Period must be six digits");
        }
        ByteArrayOutputStream output = new ByteArrayOutputStream(calculations.size() * 64);
        calculations.stream()
                .filter(BenefitCalculator.Calculation::hasOutputRecord)
                .sorted(Comparator.comparing(BenoutWriter::dbkey)
                        .thenComparing(calculation -> calculation.employment().employmentId()))
                .forEach(calculation -> output.writeBytes(record(period, calculation)));
        return output.toByteArray();
    }

    private byte[] record(String period, BenefitCalculator.Calculation calculation) {
        ByteArrayOutputStream record = new ByteArrayOutputStream(64);
        record.writeBytes(ascii(period));
        record.writeBytes(ascii(text(calculation.employment().employeeNo(), 8, "employee number")));
        record.writeBytes(ascii(String.format("%010d", dbkey(calculation))));
        record.writeBytes(ascii(text(
                calculation.lines().isEmpty() ? "" : selectedRegistration(calculation),
                8,
                "vehicle registration")));
        record.writeBytes(ascii(number(calculation.carDays(), 2)));
        record.writeBytes(comp3(calculation.taxableBenefit(), 9));
        record.writeBytes(ascii(number(calculation.distance(), 6)));
        record.writeBytes(comp3(calculation.mileageAmount(), 9));
        record.writeBytes(ascii(text(calculation.leaverFlag(), 1, "leaver flag")));
        record.writeBytes(ascii(" ".repeat(13)));
        if (record.size() != 64) {
            throw new IllegalStateException("BENOUT record must be 64 bytes");
        }
        return record.toByteArray();
    }

    private String selectedRegistration(BenefitCalculator.Calculation calculation) {
        return calculation.lines().stream()
                .max(Comparator.comparing(BenefitCalculator.Line::fromDate)
                        .thenComparingLong(BenefitCalculator.Line::assignmentId))
                .map(BenefitCalculator.Line::registration)
                .orElse("");
    }

    private static BigInteger dbkey(BenefitCalculator.Calculation calculation) {
        String legacyRef = calculation.employment().legacyRef();
        Matcher matcher = legacyRef == null ? null : MAINFRAME_REFERENCE.matcher(legacyRef);
        BigInteger value = matcher != null && matcher.matches()
                ? new BigInteger(matcher.group(1))
                : BigInteger.valueOf(calculation.employment().employmentId());
        if (value.signum() < 0 || value.toString().length() > 10) {
            throw new IllegalArgumentException("BENOUT dbkey must fit ten digits");
        }
        return value;
    }

    private String number(int value, int width) {
        if (value < 0 || value >= Math.pow(10, width)) {
            throw new IllegalArgumentException("BENOUT numeric field is out of range");
        }
        return String.format("%0" + width + "d", value);
    }

    private String text(String value, int width, String field) {
        String actual = value == null ? "" : value;
        if (actual.length() > width || !StandardCharsets.US_ASCII.newEncoder().canEncode(actual)) {
            throw new IllegalArgumentException(
                    "BENOUT " + field + " must be ASCII and fit in " + width + " characters");
        }
        return actual + " ".repeat(width - actual.length());
    }

    private byte[] comp3(BigDecimal value, int precision) {
        BigDecimal amount = value.setScale(2, RoundingMode.UNNECESSARY);
        BigInteger unscaled = amount.movePointRight(2).abs().toBigIntegerExact();
        String digits = unscaled.toString();
        if (digits.length() > precision) {
            throw new IllegalArgumentException("BENOUT packed decimal is out of range");
        }
        digits = "0".repeat(precision - digits.length()) + digits;
        String nibbles = digits + (amount.signum() < 0 ? "D" : "C");
        byte[] packed = new byte[(nibbles.length() + 1) / 2];
        for (int index = 0; index < nibbles.length(); index += 2) {
            int high = Character.digit(nibbles.charAt(index), 16);
            int low = Character.digit(nibbles.charAt(index + 1), 16);
            packed[index / 2] = (byte) ((high << 4) | low);
        }
        return packed;
    }

    private byte[] ascii(String value) {
        return value.getBytes(StandardCharsets.US_ASCII);
    }
}
