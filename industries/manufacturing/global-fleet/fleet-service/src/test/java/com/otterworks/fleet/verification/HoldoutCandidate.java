package com.otterworks.fleet.verification;

import com.otterworks.fleet.benefit.BenefitCalculator;
import com.otterworks.fleet.benefit.BenoutWriter;
import com.otterworks.fleet.config.CountryProfile;
import com.otterworks.fleet.domain.MileageClaimStatus;
import java.io.IOException;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.math.RoundingMode;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Currency;
import java.util.List;
import java.util.Map;
import java.util.HashMap;

public final class HoldoutCandidate {

    private static final DateTimeFormatter BASIC_DATE = DateTimeFormatter.BASIC_ISO_DATE;
    private static final DateTimeFormatter PERIOD_FORMAT = DateTimeFormatter.ofPattern("uuuuMM");

    private HoldoutCandidate() {
    }

    public static void main(String[] args) throws IOException {
        Map<String, String> options = arguments(args);
        Path input = Path.of(options.get("--in"));
        Path output = Path.of(options.get("--out"));
        String period = options.get("--period");
        YearMonth month = YearMonth.parse(period, PERIOD_FORMAT);
        byte[] periodRecord = Files.readAllBytes(input.resolve("BENPRD.dat"));
        if (!period.equals(String.format("%06d", integer(periodRecord, 0, 6)))) {
            throw new IllegalArgumentException("Requested period does not match BENPRD.dat");
        }

        LocalDate start = month.atDay(1);
        LocalDate end = month.atEndOfMonth();
        BigDecimal mileageRate = new BigDecimal(text(periodRecord, 22, 4)).movePointLeft(3);
        List<EmployeeRow> employees = employees(input.resolve("EMPLOYEE.dat"));
        Map<String, VehicleRow> vehicles = vehicles(input.resolve("VEHICLE.dat"));
        List<AssignmentRow> assignments = assignments(input.resolve("ASSIGNMENT.dat"));
        List<ClaimRow> claims = claims(input.resolve("MILECLM.dat"));
        BenefitCalculator calculator = new BenefitCalculator();
        CountryProfile profile = ukProfile();

        List<BenefitCalculator.Calculation> calculations = new ArrayList<>();
        for (EmployeeRow employee : employees) {
            if (employee.hireDate().isAfter(end)
                    || (employee.leaveDate() != null && employee.leaveDate().isBefore(start))) {
                continue;
            }
            List<AssignmentRow> overlapping = assignments.stream()
                    .filter(assignment -> assignment.employeeDbkey() == employee.dbkey())
                    .filter(assignment -> !assignment.startDate().isAfter(end))
                    .filter(assignment -> assignment.endDate() == null
                            || !assignment.endDate().isBefore(start))
                    .toList();
            List<BenefitCalculator.AssignmentInput> assignmentInputs = overlapping.stream()
                    .map(assignment -> {
                        VehicleRow vehicle = vehicles.get(assignment.vehicleId());
                        return new BenefitCalculator.AssignmentInput(
                                assignment.assignmentId(),
                                vehicle.id(),
                                assignment.vehicleId(),
                                assignment.startDate(),
                                assignment.endDate(),
                                vehicle.listPrice(),
                                vehicle.benefitPercent());
                    })
                    .toList();
            List<BenefitCalculator.MileageInput> mileageInputs = claims.stream()
                    .filter(claim -> claim.employeeDbkey() == employee.dbkey())
                    .filter(claim -> claim.status() == MileageClaimStatus.APPROVED)
                    .filter(claim -> !claim.claimDate().isBefore(start) && !claim.claimDate().isAfter(end))
                    .map(claim -> new BenefitCalculator.MileageInput(
                            claim.status(),
                            String.format("%04d%02d", claim.claimDate().getYear(), claim.claimDate().getMonthValue()),
                            claim.miles(),
                            BigDecimal.valueOf(claim.miles())
                                    .multiply(mileageRate)
                                    .setScale(2, RoundingMode.HALF_UP)))
                    .toList();
            BenefitCalculator.EmploymentInput employment = new BenefitCalculator.EmploymentInput(
                    employee.dbkey(),
                    employee.employeeNo(),
                    "MF:" + String.format("%010d", employee.dbkey()),
                    employee.hireDate(),
                    employee.leaveDate(),
                    employee.contribution(),
                    0);
            BenefitCalculator.Calculation calculation = calculator.calculate(
                    profile, month, employment, assignmentInputs, mileageInputs);
            if (calculation.hasOutputRecord()) {
                calculations.add(calculation);
            }
        }

        Files.createDirectories(output);
        Files.write(output.resolve("BENOUT.dat"), new BenoutWriter().write(period, calculations));
        BigDecimal totalTaxable = calculations.stream()
                .map(BenefitCalculator.Calculation::taxableBenefit)
                .reduce(BigDecimal.ZERO.setScale(2), BigDecimal::add);
        BigDecimal totalMileage = calculations.stream()
                .map(BenefitCalculator.Calculation::mileageAmount)
                .reduce(BigDecimal.ZERO.setScale(2), BigDecimal::add);
        Files.writeString(
                output.resolve("CONTROL.txt"),
                "count=" + calculations.size()
                        + "\ntotalTaxable=" + totalTaxable.toPlainString()
                        + "\ntotalMileage=" + totalMileage.toPlainString()
                        + "\n",
                StandardCharsets.UTF_8);
    }

    private static Map<String, String> arguments(String[] args) {
        if (args.length != 6) {
            throw new IllegalArgumentException("Expected --in DIR --out DIR --period YYYYMM");
        }
        Map<String, String> options = new HashMap<>();
        for (int index = 0; index < args.length; index += 2) {
            if (!List.of("--in", "--out", "--period").contains(args[index])) {
                throw new IllegalArgumentException("Unexpected argument: " + args[index]);
            }
            options.put(args[index], args[index + 1]);
        }
        if (!options.keySet().containsAll(List.of("--in", "--out", "--period"))) {
            throw new IllegalArgumentException("Expected --in DIR --out DIR --period YYYYMM");
        }
        return options;
    }

    private static List<EmployeeRow> employees(Path path) throws IOException {
        return records(path, 100).stream()
                .map(record -> new EmployeeRow(
                        Long.parseLong(text(record, 0, 10)),
                        text(record, 10, 8).trim(),
                        date(record, 61),
                        date(record, 69),
                        comp3(record, 78, 4)))
                .toList();
    }

    private static Map<String, VehicleRow> vehicles(Path path) throws IOException {
        Map<String, VehicleRow> result = new HashMap<>();
        for (byte[] record : records(path, 100)) {
            VehicleRow vehicle = new VehicleRow(
                    Long.parseLong(text(record, 0, 10)),
                    text(record, 10, 8).trim(),
                    comp3(record, 54, 5),
                    new BigDecimal(text(record, 62, 4)).movePointLeft(2));
            result.put(vehicle.vehicleId(), vehicle);
        }
        return result;
    }

    private static List<AssignmentRow> assignments(Path path) throws IOException {
        return records(path, 64).stream()
                .map(record -> new AssignmentRow(
                        Long.parseLong(text(record, 1, 9)),
                        Long.parseLong(text(record, 18, 10)),
                        text(record, 28, 8).trim(),
                        date(record, 36),
                        date(record, 44),
                        text(record, 52, 2).trim()))
                .toList();
    }

    private static List<ClaimRow> claims(Path path) throws IOException {
        return records(path, 64).stream()
                .map(record -> new ClaimRow(
                        Long.parseLong(text(record, 18, 10)),
                        date(record, 36),
                        integer(record, 44, 5),
                        record[49] == 'A' ? MileageClaimStatus.APPROVED : MileageClaimStatus.PENDING))
                .toList();
    }

    private static List<byte[]> records(Path path, int recordLength) throws IOException {
        byte[] bytes = Files.readAllBytes(path);
        if (bytes.length % recordLength != 0) {
            throw new IllegalArgumentException(path + " has an incomplete fixed-width record");
        }
        List<byte[]> records = new ArrayList<>(bytes.length / recordLength);
        for (int offset = 0; offset < bytes.length; offset += recordLength) {
            records.add(java.util.Arrays.copyOfRange(bytes, offset, offset + recordLength));
        }
        return records;
    }

    private static LocalDate date(byte[] record, int offset) {
        String value = text(record, offset, 8);
        return value.equals("00000000") ? null : LocalDate.parse(value, BASIC_DATE);
    }

    private static String text(byte[] record, int offset, int width) {
        return new String(record, offset, width, StandardCharsets.US_ASCII);
    }

    private static int integer(byte[] record, int offset, int width) {
        String value = text(record, offset, width).trim();
        return value.isEmpty() ? 0 : Integer.parseInt(value);
    }

    private static BigDecimal comp3(byte[] record, int offset, int width) {
        int[] nibbles = new int[width * 2];
        for (int index = 0; index < width; index++) {
            int value = record[offset + index] & 0xff;
            nibbles[index * 2] = value >>> 4;
            nibbles[index * 2 + 1] = value & 0x0f;
        }
        int signNibble = nibbles[nibbles.length - 1];
        StringBuilder digits = new StringBuilder();
        for (int index = 0; index < nibbles.length - 1; index++) {
            if (nibbles[index] > 9) {
                throw new IllegalArgumentException("Invalid COMP-3 digit");
            }
            digits.append(nibbles[index]);
        }
        int sign = signNibble == 0x0d ? -1 : 1;
        return new BigDecimal(new BigInteger(digits.toString()).multiply(BigInteger.valueOf(sign)), 2);
    }

    private static CountryProfile ukProfile() {
        return new CountryProfile(
                "gf-mainframe-idms",
                Currency.getInstance("GBP"),
                CountryProfile.DistanceUnit.MILE,
                7,
                CountryProfile.BenefitPercentSource.VEHICLE,
                null,
                BigDecimal.ZERO,
                CountryProfile.EmployeeContribution.EMPLOYEE,
                RoundingMode.DOWN,
                new BigDecimal("0.445"),
                RoundingMode.HALF_UP,
                3,
                1500,
                6,
                true);
    }

    private record EmployeeRow(
            long dbkey,
            String employeeNo,
            LocalDate hireDate,
            LocalDate leaveDate,
            BigDecimal contribution) {
    }

    private record VehicleRow(long id, String vehicleId, BigDecimal listPrice, BigDecimal benefitPercent) {
    }

    private record AssignmentRow(
            long assignmentId,
            long employeeDbkey,
            String vehicleId,
            LocalDate startDate,
            LocalDate endDate,
            String reason) {
    }

    private record ClaimRow(long employeeDbkey, LocalDate claimDate, int miles, MileageClaimStatus status) {
    }
}
