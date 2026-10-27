package com.otterworks.fleet;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.fleet.benefit.BenefitCalculator;
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
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class BenefitHoldoutTest {

    private static final Path PAIRS = Path.of("../parity/mainframe/pairs.json");
    private static final Path HOLDOUT = Path.of("../mainframe/holdout");
    private static final DateTimeFormatter BASIC_DATE = DateTimeFormatter.BASIC_ISO_DATE;

    @Test
    void GF27_benefitMatchesHoldouts() throws Exception {
        JsonNode pairs = new ObjectMapper().readTree(PAIRS.toFile()).path("pairs");
        BenefitCalculator calculator = new BenefitCalculator();
        CountryProfile profile = ukProfile();
        List<PairStats> stats = new ArrayList<>();
        int excludedTotal = 0;
        int mismatchTotal = 0;

        for (JsonNode pair : pairs) {
            String pairId = pair.path("id").asText();
            Path input = HOLDOUT.resolve(pairId).resolve("IN");
            Path output = HOLDOUT.resolve(pairId).resolve("OUT").resolve("BENOUT.dat");
            PairStats pairStats = comparePair(calculator, profile, pairId, input, output);
            stats.add(pairStats);
            excludedTotal += pairStats.excluded();
            mismatchTotal += pairStats.mismatched();
        }

        String table = statsTable(stats);
        System.out.println(table);
        Path report = Path.of("/home/ubuntu/gf-benefit/holdouts.txt");
        Files.createDirectories(report.getParent());
        Files.writeString(report, table, StandardCharsets.UTF_8);

        assertEquals(12, stats.size());
        assertEquals(198, excludedTotal, table);
        assertEquals(0, mismatchTotal, table);
    }

    private PairStats comparePair(
            BenefitCalculator calculator,
            CountryProfile profile,
            String pairId,
            Path input,
            Path expectedPath) throws IOException {
        List<EmployeeRow> employees = employees(input.resolve("EMPLOYEE.dat"));
        Map<String, VehicleRow> vehicles = vehicles(input.resolve("VEHICLE.dat"));
        List<AssignmentRow> assignments = assignments(input.resolve("ASSIGNMENT.dat"));
        List<ClaimRow> claims = claims(input.resolve("MILECLM.dat"));
        byte[] periodRecord = Files.readAllBytes(input.resolve("BENPRD.dat"));
        int periodNumber = integer(periodRecord, 0, 6);
        YearMonth month = YearMonth.parse(Integer.toString(periodNumber), DateTimeFormatter.ofPattern("uuuuMM"));
        LocalDate start = month.atDay(1);
        LocalDate end = month.atEndOfMonth();
        BigDecimal mileageRate = new BigDecimal(text(periodRecord, 22, 4)).movePointLeft(3);

        Map<Long, OutputRow> expected = new HashMap<>();
        for (byte[] record : records(expectedPath, 64)) {
            OutputRow row = new OutputRow(
                    text(record, 6, 8).trim(),
                    Long.parseLong(text(record, 14, 10)),
                    text(record, 24, 8).trim(),
                    integer(record, 32, 2),
                    comp3(record, 34, 5),
                    integer(record, 39, 6),
                    comp3(record, 45, 5),
                    text(record, 50, 1).trim());
            expected.put(row.dbkey(), row);
        }

        Map<Long, OutputRow> actual = new HashMap<>();
        Set<Long> excludedDbkeys = new HashSet<>();
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
            if (overlapping.size() > 1) {
                excludedDbkeys.add(employee.dbkey());
                continue;
            }
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
                actual.put(employee.dbkey(), new OutputRow(
                        employee.employeeNo(),
                        employee.dbkey(),
                        calculation.lines().stream()
                                .max(java.util.Comparator.comparing(BenefitCalculator.Line::fromDate)
                                        .thenComparingLong(BenefitCalculator.Line::assignmentId))
                                .map(BenefitCalculator.Line::registration)
                                .orElse(""),
                        calculation.carDays(),
                        calculation.taxableBenefit(),
                        calculation.distance(),
                        calculation.mileageAmount(),
                        calculation.leaverFlag() == null ? "" : calculation.leaverFlag()));
            }
        }

        Set<Long> keys = new HashSet<>(expected.keySet());
        keys.addAll(actual.keySet());
        keys.removeAll(excludedDbkeys);
        int matched = 0;
        for (Long dbkey : keys) {
            if (expected.containsKey(dbkey) && expected.get(dbkey).equals(actual.get(dbkey))) {
                matched++;
            }
        }
        return new PairStats(pairId, keys.size(), matched, keys.size() - matched, excludedDbkeys.size());
    }

    private List<EmployeeRow> employees(Path path) throws IOException {
        return records(path, 100).stream()
                .map(record -> new EmployeeRow(
                        Long.parseLong(text(record, 0, 10)),
                        text(record, 10, 8).trim(),
                        date(record, 61),
                        date(record, 69),
                        comp3(record, 78, 4)))
                .toList();
    }

    private Map<String, VehicleRow> vehicles(Path path) throws IOException {
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

    private List<AssignmentRow> assignments(Path path) throws IOException {
        return records(path, 64).stream()
                .map(record -> new AssignmentRow(
                        Long.parseLong(text(record, 1, 9)),
                        Long.parseLong(text(record, 18, 10)),
                        text(record, 28, 8).trim(),
                        date(record, 36),
                        date(record, 44)))
                .toList();
    }

    private List<ClaimRow> claims(Path path) throws IOException {
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

    private static String statsTable(List<PairStats> stats) {
        StringBuilder output = new StringBuilder();
        output.append("| Pair | Compared | Matched | Mismatched | Excluded |\n")
                .append("|---|---:|---:|---:|---:|\n");
        stats.forEach(row -> output.append("| ").append(row.pair())
                .append(" | ").append(row.compared())
                .append(" | ").append(row.matched())
                .append(" | ").append(row.mismatched())
                .append(" | ").append(row.excluded()).append(" |\n"));
        return output.toString();
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
            LocalDate endDate) {
    }

    private record ClaimRow(long employeeDbkey, LocalDate claimDate, int miles, MileageClaimStatus status) {
    }

    private record OutputRow(
            String employeeNo,
            long dbkey,
            String vehicleId,
            int days,
            BigDecimal taxable,
            int miles,
            BigDecimal reimbursement,
            String flag) {
    }

    private record PairStats(String pair, int compared, int matched, int mismatched, int excluded) {
    }
}
