package com.otterworks.fleet;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.fleet.assignment.CalendarMonthOpenPeriodLookup;
import com.otterworks.fleet.assignment.OpenPeriodLookup;
import com.otterworks.fleet.config.CountryProfile;
import com.otterworks.fleet.domain.Assignment;
import com.otterworks.fleet.domain.AssignmentRepository;
import com.otterworks.fleet.domain.BenefitPeriodRepository;
import com.otterworks.fleet.domain.Employment;
import com.otterworks.fleet.domain.EmploymentRepository;
import com.otterworks.fleet.domain.EmploymentStatus;
import com.otterworks.fleet.domain.MileageClaim;
import com.otterworks.fleet.domain.MileageClaimRepository;
import com.otterworks.fleet.domain.Person;
import com.otterworks.fleet.domain.PersonRepository;
import com.otterworks.fleet.domain.Vehicle;
import com.otterworks.fleet.domain.VehicleRepository;
import com.otterworks.fleet.eligibility.EligibilityService;
import com.otterworks.fleet.mileage.ClaimView;
import com.otterworks.fleet.mileage.MileageClaimRequest;
import com.otterworks.fleet.mileage.MileageClaimService;
import com.otterworks.fleet.mileage.MileageException;
import com.otterworks.fleet.mileage.MileagePricing;
import com.otterworks.fleet.mileage.MileageReason;
import com.otterworks.fleet.mileage.MileageReimbursementView;
import java.io.IOException;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.math.RoundingMode;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.sql.Timestamp;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicLong;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.AfterEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.test.web.servlet.MockMvc;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@Import(MileageIntegrationTest.FixedClockConfiguration.class)
class MileageIntegrationTest extends AbstractPostgresIntegrationTest {

    private static final LocalDate TODAY = LocalDate.of(2026, 10, 27);
    private static final Instant NOW = Instant.parse("2026-10-27T12:00:00Z");
    private static final DateTimeFormatter BASIC_DATE = DateTimeFormatter.BASIC_ISO_DATE;
    private static final Pattern SEED_CLAIM = Pattern.compile(
            "INSERT INTO mileage_claim \\(id, employee_id, claim_date, km, purpose, amount, status\\) "
                    + "VALUES \\((\\d+), \\d+, '([^']+)', (\\d+), '[^']*', ([0-9.]+), '([^']+)'\\);");
    private static final AtomicLong EMPLOYEE_SEQUENCE = new AtomicLong();
    private Long gf19EmploymentId;
    private boolean gf19BenefitPeriodCreated;

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private CountryProfile profile;

    @Autowired
    private Flyway flyway;

    @Autowired
    private PersonRepository personRepository;

    @Autowired
    private EmploymentRepository employmentRepository;

    @Autowired
    private VehicleRepository vehicleRepository;

    @Autowired
    private AssignmentRepository assignmentRepository;

    @Autowired
    private MileageClaimRepository claimRepository;

    @Autowired
    private BenefitPeriodRepository benefitPeriodRepository;

    @Autowired
    private EligibilityService eligibilityService;

    @Autowired
    private MileageClaimService mileageClaimService;

    @Autowired
    private MileagePricing mileagePricing;

    @Autowired
    private JdbcTemplate jdbc;

    @Autowired
    private PlatformTransactionManager transactionManager;

    @Test
    void GF19_claimDateWithinOpenOrLookbackPeriod() throws Exception {
        Employment employee = employee(EmploymentStatus.ACTIVE, LocalDate.of(2020, 1, 1), null);
        gf19EmploymentId = employee.getId();
        String employeeNo = employee.getPerson().getEmployeeNo();
        LocalDate lookbackStart = YearMonth.from(TODAY)
                .minusMonths(profile.claimLookbackMonths())
                .atDay(1);
        LocalDate outsideWindow = YearMonth.from(lookbackStart).minusMonths(1).atEndOfMonth();
        gf19BenefitPeriodCreated = insertBenefitPeriod(
                "202610", TODAY.withDayOfMonth(1), TODAY.withDayOfMonth(31), profile.mileageRate());

        assertEquals(
                MileageReason.JOURNEY_DATE_IN_FUTURE,
                assertThrows(MileageException.class, () -> mileageClaimService.submit(
                        employeeNo, TODAY.plusDays(1), BigDecimal.ONE, "future")).getReason());

        MileageClaim todayClaim = mileageClaimService.submit(employeeNo, TODAY, BigDecimal.ONE, "today");
        assertEquals("202610", todayClaim.getPaidPeriod());
        MileageClaim backdatedClaim = mileageClaimService.submit(
                employeeNo, lookbackStart, BigDecimal.ONE, "lookback boundary");
        assertEquals(lookbackStart, backdatedClaim.getClaimDate());
        assertEquals("202610", backdatedClaim.getPaidPeriod());
        assertEquals(
                MileageReason.JOURNEY_DATE_OUTSIDE_CLAIM_WINDOW,
                assertThrows(MileageException.class, () -> mileageClaimService.submit(
                        employeeNo, outsideWindow, BigDecimal.ONE, "outside"))
                        .getReason());
        assertEquals("202610", todayClaim.getBenefitPeriod().getPeriod().trim());

        LocalDate earlierDate = TODAY.minusMonths(1).withDayOfMonth(10);
        YearMonth earlierMonth = YearMonth.from(earlierDate);
        OpenPeriodLookup earlierMonthOpen = date -> YearMonth.from(date).equals(earlierMonth);
        MileageClaimService earlierMonthService = service(profile, earlierMonthOpen, mileagePricing);
        MileageClaim earlierClaim = earlierMonthService.submit(
                employeeNo, earlierDate, BigDecimal.ONE, "open earlier month");
        assertEquals(earlierMonth.format(DateTimeFormatter.ofPattern("yyyyMM")), earlierClaim.getPaidPeriod());

        MileageClaimService noCurrentOpenPeriod = service(profile, date -> false, mileagePricing);
        assertEquals(
                MileageReason.NO_OPEN_CLAIM_PERIOD,
                assertThrows(MileageException.class, () -> noCurrentOpenPeriod.submit(
                        employeeNo, TODAY.minusMonths(1), BigDecimal.ONE, "closed current"))
                        .getReason());

        mockMvc.perform(post("/api/v1/mileage/claims")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(new MileageClaimRequest(
                                employeeNo, TODAY.plusDays(1), BigDecimal.ONE, "future"))))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("JOURNEY_DATE_IN_FUTURE"));
    }

    @Test
    void GF20_distanceWithinProfileMaximum() throws Exception {
        mockMvc.perform(get("/api/v1/mileage/quote").param("distance", "0"))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("DISTANCE_OUT_OF_RANGE"));
        mockMvc.perform(get("/api/v1/mileage/quote").param("distance", "-1"))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("DISTANCE_OUT_OF_RANGE"));
        mockMvc.perform(get("/api/v1/mileage/quote")
                        .param("distance", Integer.toString(profile.maxClaimDistance() + 1)))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("DISTANCE_OUT_OF_RANGE"));
        mockMvc.perform(get("/api/v1/mileage/quote").param("distance", "12.5"))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("DISTANCE_NOT_WHOLE"));
        mockMvc.perform(get("/api/v1/mileage/quote"))
                .andExpect(status().isBadRequest());
        mockMvc.perform(get("/api/v1/mileage/quote").param("distance", "1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.distance").value(1));
        mockMvc.perform(get("/api/v1/mileage/quote")
                        .param("distance", Integer.toString(profile.maxClaimDistance())))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.distance").value(profile.maxClaimDistance()));
    }

    @Test
    void v40BackfillRateAndAmountAreRequired() {
        assertEquals(
                profile.mileageRate(),
                new BigDecimal(flyway.getConfiguration().getPlaceholders().get("mileage_rate")));
        Integer requiredPricingColumns = jdbc.queryForObject(
                """
                SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'mileage_claim'
                  AND column_name IN ('rate', 'amount')
                  AND is_nullable = 'NO'
                """,
                Integer.class);
        assertEquals(2, requiredPricingColumns);
    }

    @Test
    void GF21_mileageRoundsHalfUpInBothCountries() {
        assertEquals(RoundingMode.HALF_UP, profile.mileageRounding());
        assertEquals(new BigDecimal("0.31"), mileagePricing.amount(1, new BigDecimal("0.305")));
        assertEquals(new BigDecimal("0.45"), mileagePricing.amount(1, new BigDecimal("0.445")));
        assertEquals(mileagePricing.amount(1, profile.mileageRate()), mileagePricing.quote(1));
        assertEquals(
                new BigDecimal("0.45"),
                new MileagePricing(withMileageRate(profile, new BigDecimal("0.445"))).quote(1));
    }

    @Test
    void GF21_mileageAmountFrozenAtSubmission() {
        Employment employee = employee(EmploymentStatus.ACTIVE, LocalDate.of(2020, 1, 1), null);
        String employeeNo = employee.getPerson().getEmployeeNo();
        MileageClaim initial = mileageClaimService.submit(
                employeeNo, TODAY, BigDecimal.ONE, "original rate");
        CountryProfile changedProfile = withMileageRate(profile, new BigDecimal("0.999"));
        MileageClaimService changedService = service(
                changedProfile,
                new CalendarMonthOpenPeriodLookup(Clock.fixed(NOW, ZoneOffset.UTC)),
                new MileagePricing(changedProfile));

        MileageClaim fromHistory = claimFromHistory(changedService.history(employeeNo).claims(), initial.getId());
        assertEquals(profile.mileageRate(), fromHistory.getRate());
        assertEquals(initial.getAmount(), fromHistory.getAmount());
        MileageClaim approved = new TransactionTemplate(transactionManager)
                .execute(transaction -> changedService.approve(initial.getId()));
        assertEquals(profile.mileageRate(), approved.getRate());
        assertEquals(initial.getAmount(), approved.getAmount());
        MileageReimbursementView reimbursement = changedService.reimbursement(
                employeeNo, YearMonth.from(TODAY));
        assertEquals(1, reimbursement.claimCount());
        assertEquals(initial.getAmount(), reimbursement.amount());

        MileageClaim newClaim = changedService.submit(employeeNo, TODAY, BigDecimal.ONE, "changed rate");
        assertEquals(new BigDecimal("0.999"), newClaim.getRate());
        assertEquals(new BigDecimal("1.00"), newClaim.getAmount());
    }

    @Test
    void GF21_mileageReimbursementMatchesHoldouts() throws Exception {
        JsonNode pairs = objectMapper.readTree(
                Path.of("../parity/mainframe/pairs.json").toFile()).path("pairs");
        int processed = 0;
        for (JsonNode pair : pairs) {
            String pairId = pair.path("id").asText();
            Path input = Path.of("../mainframe/holdout", pairId, "IN");
            Path output = Path.of("../mainframe/holdout", pairId, "OUT");
            assertHoldoutMileage(input, output);
            processed++;
        }
        assertEquals(12, processed);
    }

    @Test
    void GF21_deSeedClaimsAcceptedDifference() throws Exception {
        assertEquals(RoundingMode.HALF_UP, profile.mileageRounding());
        String seed = Files.readString(Path.of("../seed/jsf/002_seed.sql"));
        Matcher matcher = SEED_CLAIM.matcher(seed);
        List<SeedDifference> actualChanges = new ArrayList<>();
        int parsed = 0;
        BigDecimal seedRate = new BigDecimal("0.305");
        while (matcher.find()) {
            long id = Long.parseLong(matcher.group(1));
            int distance = Integer.parseInt(matcher.group(3));
            BigDecimal legacyAmount = new BigDecimal(matcher.group(4));
            BigDecimal expectedLegacy = BigDecimal.valueOf(distance)
                    .multiply(seedRate)
                    .setScale(2, RoundingMode.HALF_EVEN);
            assertEquals(expectedLegacy, legacyAmount, "legacy half-even amount for claim " + id);
            BigDecimal amount = mileagePricing.amount(distance, seedRate);
            if (amount.compareTo(legacyAmount) != 0) {
                actualChanges.add(new SeedDifference(id, distance, legacyAmount, amount));
            }
            parsed++;
        }
        assertEquals(699, parsed);

        List<SeedDifference> acceptedChanges = new ArrayList<>();
        List<String> lines = Files.readAllLines(
                Path.of("src/test/resources/mileage/gf21-de-seed-accepted-difference.csv"));
        for (int index = 1; index < lines.size(); index++) {
            String[] columns = lines.get(index).split(",");
            acceptedChanges.add(new SeedDifference(
                    Long.parseLong(columns[0]),
                    Integer.parseInt(columns[2]),
                    new BigDecimal(columns[3]),
                    new BigDecimal(columns[4])));
        }
        assertEquals(172, actualChanges.size());
        assertEquals(acceptedChanges, actualChanges);
        assertTrue(actualChanges.stream().allMatch(change ->
                change.newAmount().subtract(change.legacyAmount()).equals(new BigDecimal("0.01"))));
    }

    @Test
    void GF22_newClaimIsPendingAndOnlyApprovedIsPaid() throws Exception {
        Employment employee = employee(EmploymentStatus.ACTIVE, LocalDate.of(2020, 1, 1), null);
        String employeeNo = employee.getPerson().getEmployeeNo();
        MileageClaim pending = mileageClaimService.submit(employeeNo, TODAY, BigDecimal.TEN, "pending");
        assertEquals("PENDING", pending.getStatus().name());
        assertNull(pending.getDecidedAt());

        MileageReimbursementView beforeApproval = mileageClaimService.reimbursement(
                employeeNo, YearMonth.from(TODAY));
        assertEquals(0, beforeApproval.claimCount());
        assertEquals(0, beforeApproval.distance());
        assertEquals(new BigDecimal("0.00"), beforeApproval.amount());

        var pendingResponse = mockMvc.perform(get("/api/v1/mileage/claims/pending"))
                .andExpect(status().isOk())
                .andReturn();
        JsonNode pendingClaims = objectMapper.readTree(pendingResponse.getResponse().getContentAsString());
        assertTrue(pendingClaims.toString().contains("\"id\":" + pending.getId()));
        assertTrue(pendingClaims.toString().contains("\"status\":\"PENDING\""));
        mockMvc.perform(post("/api/v1/mileage/claims/{id}/approve", pending.getId()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("APPROVED"))
                .andExpect(jsonPath("$.decidedAt").value(NOW.toString()));
        MileageReimbursementView afterApproval = mileageClaimService.reimbursement(
                employeeNo, YearMonth.from(TODAY));
        assertEquals(1, afterApproval.claimCount());
        assertEquals(10, afterApproval.distance());
        assertEquals(pending.getAmount(), afterApproval.amount());

        MileageClaim rejected = mileageClaimService.submit(employeeNo, TODAY, BigDecimal.ONE, "reject me");
        mockMvc.perform(post("/api/v1/mileage/claims/{id}/reject", rejected.getId()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("REJECTED"));
        assertEquals(
                MileageReason.CLAIM_ALREADY_DECIDED,
                assertThrows(MileageException.class, () -> mileageClaimService.reject(pending.getId()))
                        .getReason());
    }

    @Test
    void GF23_claimVehicleHandling() throws Exception {
        Employment employee = employee(EmploymentStatus.ACTIVE, LocalDate.of(2020, 1, 1), null);
        Vehicle carA = vehicle("CAR-A");
        Vehicle carB = vehicle("CAR-B");
        assignmentRepository.saveAndFlush(new Assignment(
                employee, carA, LocalDate.of(2026, 8, 1), LocalDate.of(2026, 9, 15), "NC", null));
        assignmentRepository.saveAndFlush(new Assignment(
                employee, carB, LocalDate.of(2026, 9, 20), null, "RP", null));

        assertEquals("CAR-A", submit(employee, LocalDate.of(2026, 9, 10)).getVehicle().getRegistration());
        assertEquals("CAR-A", submit(employee, LocalDate.of(2026, 9, 15)).getVehicle().getRegistration());
        assertNull(submit(employee, LocalDate.of(2026, 9, 17)).getVehicle());
        MileageClaim october = submit(employee, LocalDate.of(2026, 10, 1));
        assertEquals("CAR-B", october.getVehicle().getRegistration());

        Employment noCar = employee(EmploymentStatus.ACTIVE, LocalDate.of(2020, 1, 1), null);
        MileageClaim withoutVehicle = submit(noCar, LocalDate.of(2026, 10, 1));
        assertNull(withoutVehicle.getVehicle());
        mockMvc.perform(get("/api/v1/mileage/employees/{employeeNo}/claims",
                        employee.getPerson().getEmployeeNo()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.claims[0].vehicleRegistration").value("CAR-B"));
    }

    @Test
    void GF24_claimHistoryWindow() throws Exception {
        Employment employee = employee(EmploymentStatus.ACTIVE, LocalDate.of(2020, 1, 1), null);
        LocalDate from = TODAY.minusMonths(profile.claimHistoryMonths());
        insertClaim(employee.getId(), from.minusDays(1), "PENDING", 2);
        insertClaim(employee.getId(), from, "PENDING", 3);
        insertClaim(employee.getId(), TODAY.minusDays(1), "REJECTED", 4);
        insertClaim(employee.getId(), TODAY, "APPROVED", 5);

        var response = mockMvc.perform(get("/api/v1/mileage/employees/{employeeNo}/claims",
                        employee.getPerson().getEmployeeNo()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.from").value(from.toString()))
                .andExpect(jsonPath("$.to").value(TODAY.toString()))
                .andExpect(jsonPath("$.claims.length()").value(3))
                .andReturn();
        JsonNode claims = objectMapper.readTree(response.getResponse().getContentAsString()).path("claims");
        assertEquals(TODAY.toString(), claims.get(0).path("journeyDate").asText());
        assertEquals(TODAY.minusDays(1).toString(), claims.get(1).path("journeyDate").asText());
        assertEquals(from.toString(), claims.get(2).path("journeyDate").asText());
        assertEquals("APPROVED", claims.get(0).path("status").asText());
        assertEquals("REJECTED", claims.get(1).path("status").asText());
        assertEquals("PENDING", claims.get(2).path("status").asText());
    }

    @Test
    void GF25_mileageClaimEligibility() throws Exception {
        mockMvc.perform(post("/api/v1/mileage/claims")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(new MileageClaimRequest("", TODAY, BigDecimal.ONE, "blank"))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("EMPLOYEE_NUMBER_REQUIRED"));
        mockMvc.perform(post("/api/v1/mileage/claims")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(new MileageClaimRequest("MISSING", TODAY, BigDecimal.ONE, "unknown"))))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("EMPLOYEE_NOT_FOUND"));

        Employment transferred = employee(
                EmploymentStatus.TRANSFERRED, LocalDate.of(2020, 1, 1), null);
        assertEligibilityCode(transferred.getPerson().getEmployeeNo(), TODAY, "NOT_ACTIVE");

        LocalDate leaveDate = TODAY.minusDays(7);
        Employment leaver = employee(EmploymentStatus.LEFT, LocalDate.of(2020, 1, 1), leaveDate);
        MileageClaim onLeaveDate = mileageClaimService.submit(
                leaver.getPerson().getEmployeeNo(), leaveDate, BigDecimal.ONE, "last day");
        assertEquals(leaveDate, onLeaveDate.getClaimDate());
        assertEligibilityCode(
                leaver.getPerson().getEmployeeNo(), leaveDate.plusDays(1), "CLAIM_AFTER_LEAVING_DATE");

        Employment active = employee(EmploymentStatus.ACTIVE, LocalDate.of(2020, 1, 1), null);
        assertNotNull(mileageClaimService.submit(
                active.getPerson().getEmployeeNo(), TODAY, BigDecimal.ONE, "active"));

        mockMvc.perform(get("/api/v1/mileage/employees/{employeeNo}/reimbursement",
                        active.getPerson().getEmployeeNo())
                        .param("period", "202613"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("INVALID_PERIOD"));
    }

    private void assertHoldoutMileage(Path input, Path output) throws IOException {
        byte[] periodRecord = Files.readAllBytes(input.resolve("BENPRD.dat"));
        assertEquals(40, periodRecord.length);
        String period = text(periodRecord, 0, 6);
        LocalDate start = parseDate(text(periodRecord, 6, 8));
        LocalDate end = parseDate(text(periodRecord, 14, 8));
        BigDecimal rate = new BigDecimal(text(periodRecord, 22, 4)).movePointLeft(3);
        Map<String, Long> mileageByEmployee = new HashMap<>();
        Map<String, BigDecimal> amountByEmployee = new HashMap<>();
        Set<String> outputEmployees = new HashSet<>();

        for (byte[] claim : records(input.resolve("MILECLM.dat"), 64)) {
            String employeeDbKey = text(claim, 18, 10);
            LocalDate claimDate = parseDate(text(claim, 36, 8));
            int miles = Integer.parseInt(text(claim, 44, 5));
            if (claim[49] == 'A' && !claimDate.isBefore(start) && !claimDate.isAfter(end)) {
                mileageByEmployee.merge(employeeDbKey, (long) miles, Long::sum);
                amountByEmployee.merge(
                        employeeDbKey,
                        mileagePricing.amount(miles, rate),
                        BigDecimal::add);
            }
        }

        for (byte[] outputRecord : records(output.resolve("BENOUT.dat"), 64)) {
            String employeeDbKey = text(outputRecord, 14, 10);
            outputEmployees.add(employeeDbKey);
            long expectedMiles = mileageByEmployee.getOrDefault(employeeDbKey, 0L);
            BigDecimal expectedAmount = amountByEmployee.getOrDefault(employeeDbKey, BigDecimal.ZERO.setScale(2));
            long actualMiles = Long.parseLong(text(outputRecord, 39, 6));
            BigDecimal actualAmount = decodeComp3(outputRecord, 45, 5);
            assertEquals(expectedMiles, actualMiles, period + " miles for " + employeeDbKey);
            assertEquals(expectedAmount, actualAmount, period + " amount for " + employeeDbKey);
            if (actualMiles == 0) {
                assertEquals(0L, expectedMiles);
                assertEquals(BigDecimal.ZERO.setScale(2), expectedAmount);
            }
        }
        assertTrue(outputEmployees.containsAll(mileageByEmployee.keySet()), period + " all claimants have BENOUT");
    }

    private List<byte[]> records(Path path, int recordLength) throws IOException {
        byte[] content = Files.readAllBytes(path);
        assertEquals(0, content.length % recordLength, path.toString());
        List<byte[]> records = new ArrayList<>();
        for (int offset = 0; offset < content.length; offset += recordLength) {
            records.add(java.util.Arrays.copyOfRange(content, offset, offset + recordLength));
        }
        return records;
    }

    private String text(byte[] record, int offset, int length) {
        return new String(record, offset, length, StandardCharsets.US_ASCII).trim();
    }

    private LocalDate parseDate(String value) {
        return LocalDate.parse(value, BASIC_DATE);
    }

    private BigDecimal decodeComp3(byte[] record, int offset, int length) {
        StringBuilder digits = new StringBuilder();
        int sign = 1;
        for (int nibbleIndex = 0; nibbleIndex < length * 2; nibbleIndex++) {
            int value = record[offset + nibbleIndex / 2] & 0xff;
            int nibble = nibbleIndex % 2 == 0 ? value >>> 4 : value & 0x0f;
            if (nibbleIndex < 9) {
                digits.append(nibble);
            } else {
                sign = nibble == 0x0d ? -1 : 1;
            }
        }
        BigInteger unscaled = new BigInteger(digits.toString()).multiply(BigInteger.valueOf(sign));
        return new BigDecimal(unscaled, 2);
    }

    private boolean insertBenefitPeriod(String period, LocalDate start, LocalDate end, BigDecimal rate) {
        int inserted = jdbc.update(
                """
                INSERT INTO benefit_period (period, start_date, end_date, mileage_rate)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (period) DO NOTHING
                """,
                period,
                start,
                end,
                rate);
        assertTrue(benefitPeriodRepository.findByPeriod(period).isPresent());
        return inserted == 1;
    }

    private void insertClaim(Long employmentId, LocalDate date, String status, int distance) {
        jdbc.update(
                """
                INSERT INTO mileage_claim (
                    employment_id, claim_date, distance, status, rate, amount,
                    paid_period, purpose, submitted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                employmentId,
                date,
                distance,
                status,
                profile.mileageRate(),
                mileagePricing.amount(distance, profile.mileageRate()),
                YearMonth.from(date).format(DateTimeFormatter.ofPattern("yyyyMM")),
                "history fixture",
                Timestamp.from(NOW));
    }

    @AfterEach
    void cleanGf19PeriodFixture() {
        if (gf19EmploymentId != null) {
            jdbc.update("DELETE FROM mileage_claim WHERE employment_id = ?", gf19EmploymentId);
        }
        if (gf19BenefitPeriodCreated) {
            Integer references = jdbc.queryForObject(
                    """
                    SELECT COUNT(*) FROM mileage_claim
                    WHERE benefit_period_id = (SELECT id FROM benefit_period WHERE period = '202610')
                    """,
                    Integer.class);
            if (references != null && references == 0) {
                jdbc.update("DELETE FROM benefit_period WHERE period = '202610'");
            }
        }
    }

    private Employment employee(EmploymentStatus status, LocalDate hireDate, LocalDate leaveDate) {
        String employeeNo = "MILE" + EMPLOYEE_SEQUENCE.incrementAndGet();
        Person person = personRepository.saveAndFlush(new Person(employeeNo, "Mileage", "Employee"));
        return employmentRepository.saveAndFlush(new Employment(
                person, 10, status, hireDate, leaveDate, BigDecimal.ZERO.setScale(2), null));
    }

    private Vehicle vehicle(String registration) {
        return vehicleRepository.saveAndFlush(new Vehicle(
                registration,
                "Example",
                "Fleet",
                new BigDecimal("25000.00"),
                100,
                "D",
                new BigDecimal("20.00"),
                "AVAILABLE"));
    }

    private MileageClaim submit(Employment employee, LocalDate date) {
        return mileageClaimService.submit(
                employee.getPerson().getEmployeeNo(), date, BigDecimal.ONE, "vehicle coverage");
    }

    private MileageClaimService service(
            CountryProfile serviceProfile,
            OpenPeriodLookup openPeriodLookup,
            MileagePricing pricing) {
        return new MileageClaimService(
                eligibilityService,
                serviceProfile,
                claimRepository,
                assignmentRepository,
                benefitPeriodRepository,
                Clock.fixed(NOW, ZoneOffset.UTC),
                openPeriodLookup,
                pricing);
    }

    private CountryProfile withMileageRate(CountryProfile source, BigDecimal mileageRate) {
        return new CountryProfile(
                source.sourceApp(),
                source.currency(),
                source.distanceUnit(),
                source.minGrade(),
                source.benefitPercentSource(),
                source.benefitPercent(),
                source.commutePercentPerUnit(),
                source.employeeContribution(),
                source.benefitRounding(),
                mileageRate,
                source.mileageRounding(),
                source.claimLookbackMonths(),
                source.maxClaimDistance(),
                source.claimHistoryMonths(),
                source.payrollFile());
    }

    private MileageClaim claimFromHistory(List<ClaimView> claims, Long id) {
        ClaimView found = claims.stream().filter(claim -> claim.id().equals(id)).findFirst().orElseThrow();
        MileageClaim original = claimRepository.findById(found.id()).orElseThrow();
        return original;
    }

    private void assertEligibilityCode(String employeeNo, LocalDate date, String expectedCode) throws Exception {
        mockMvc.perform(post("/api/v1/mileage/claims")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(new MileageClaimRequest(employeeNo, date, BigDecimal.ONE, "eligibility"))))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value(expectedCode));
    }

    private String json(Object value) throws Exception {
        return objectMapper.writeValueAsString(value);
    }

    @TestConfiguration
    static class FixedClockConfiguration {

        @Bean
        Clock mileageTestClock() {
            return Clock.fixed(NOW, ZoneOffset.UTC);
        }
    }

    private record SeedDifference(long id, int distance, BigDecimal legacyAmount, BigDecimal newAmount) {
    }
}
