package com.otterworks.fleet;

import com.otterworks.fleet.config.CountryProfile;
import com.otterworks.fleet.domain.Employment;
import com.otterworks.fleet.domain.EmploymentRepository;
import com.otterworks.fleet.domain.EmploymentStatus;
import com.otterworks.fleet.domain.Person;
import com.otterworks.fleet.domain.PersonRepository;
import com.otterworks.fleet.eligibility.BelowGradeHolder;
import com.otterworks.fleet.eligibility.CarRequestStep;
import com.otterworks.fleet.eligibility.EligibilityDecision;
import com.otterworks.fleet.eligibility.EligibilityException;
import com.otterworks.fleet.eligibility.EligibilityReason;
import com.otterworks.fleet.eligibility.EligibilityService;
import com.otterworks.fleet.eligibility.EmployeeNumbers;
import com.otterworks.fleet.eligibility.EmployeeSearchService;
import com.otterworks.fleet.eligibility.EmploymentHistoryLoader;
import java.io.IOException;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import org.flywaydb.core.Flyway;
import org.flywaydb.core.api.MigrationVersion;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class EligibilityIntegrationTest extends AbstractPostgresIntegrationTest {

    private static final DateTimeFormatter BASIC_DATE = DateTimeFormatter.BASIC_ISO_DATE;

    @Autowired
    private EligibilityService eligibilityService;

    @Autowired
    private EmploymentHistoryLoader historyLoader;

    @Autowired
    private EmployeeSearchService employeeSearchService;

    @Autowired
    private PersonRepository personRepository;

    @Autowired
    private EmploymentRepository employmentRepository;

    @Autowired
    private CountryProfile profile;

    @Autowired
    private JdbcTemplate jdbc;

    @Autowired
    private MockMvc mockMvc;

    @Test
    void GF02_gradeBelowThresholdIsRefused() throws Exception {
        Employment below = createEmployment(unique("GF02"), profile.minGrade() - 1, EmploymentStatus.ACTIVE,
                LocalDate.of(2020, 1, 1), null);
        for (CarRequestStep step : CarRequestStep.values()) {
            EligibilityDecision decision = eligibilityService.carRequest(
                    below.getPerson().getEmployeeNo(), step, LocalDate.of(2026, 10, 1));
            assertFalse(decision.allowed());
            assertEquals(EligibilityReason.GRADE_BELOW_THRESHOLD, decision.reason());
        }

        Employment lowered = createEmployment(unique("GF02"), profile.minGrade(), EmploymentStatus.ACTIVE,
                LocalDate.of(2020, 1, 1), null);
        assertTrue(eligibilityService.carRequest(
                lowered.getPerson().getEmployeeNo(), CarRequestStep.EMPLOYEE, LocalDate.of(2026, 10, 1)).allowed());
        lowered.setGrade(profile.minGrade() - 1);
        employmentRepository.save(lowered);
        EligibilityDecision confirm = eligibilityService.carRequest(
                lowered.getPerson().getEmployeeNo(), CarRequestStep.CONFIRM, LocalDate.of(2026, 10, 1));
        assertFalse(confirm.allowed());
        assertEquals(EligibilityReason.GRADE_BELOW_THRESHOLD, confirm.reason());

        mockMvc.perform(get("/api/v1/eligibility/car-request")
                        .param("employeeNo", below.getPerson().getEmployeeNo())
                        .param("step", "EMPLOYEE")
                        .param("date", "2026-10-01"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.allowed").value(false))
                .andExpect(jsonPath("$.reason").value("GRADE_BELOW_THRESHOLD"));
    }

    @Test
    void GF02_gradeAtThresholdIsEligible() {
        for (int grade : List.of(profile.minGrade(), profile.minGrade() + 1)) {
            Employment employment = createEmployment(
                    unique("GF02"), grade, EmploymentStatus.ACTIVE, LocalDate.of(2020, 1, 1), null);
            for (CarRequestStep step : CarRequestStep.values()) {
                EligibilityDecision decision = eligibilityService.carRequest(
                        employment.getPerson().getEmployeeNo(), step, LocalDate.of(2026, 10, 1));
                assertTrue(decision.allowed());
                assertNull(decision.reason());
            }
        }
    }

    @Test
    void GF02_batchRunListsBelowThresholdHolders() throws Exception {
        YearMonth period = YearMonth.of(2025, 4);
        Employment open = createEmployment(
                unique("GF02"), profile.minGrade() - 1, EmploymentStatus.ACTIVE, LocalDate.of(2020, 1, 1), null);
        Employment ending = createEmployment(
                unique("GF02"), profile.minGrade() - 1, EmploymentStatus.ACTIVE, LocalDate.of(2020, 1, 1), null);
        Employment eligible = createEmployment(
                unique("GF02"), profile.minGrade(), EmploymentStatus.ACTIVE, LocalDate.of(2020, 1, 1), null);
        Employment noAssignment = createEmployment(
                unique("GF02"), profile.minGrade() - 1, EmploymentStatus.ACTIVE, LocalDate.of(2020, 1, 1), null);
        long openId = createAssignment(open, unique("CAR"), LocalDate.of(2024, 10, 1), null);
        long endingId = createAssignment(ending, unique("CAR"), LocalDate.of(2024, 10, 1), period.atDay(18));
        createAssignment(eligible, unique("CAR"), LocalDate.of(2024, 10, 1), null);

        List<BelowGradeHolder> holders = eligibilityService.belowGradeHolders(period);
        assertTrue(holders.stream().anyMatch(row -> row.employeeNo().equals(open.getPerson().getEmployeeNo())));
        assertTrue(holders.stream().anyMatch(row -> row.employeeNo().equals(ending.getPerson().getEmployeeNo())));
        assertFalse(holders.stream().anyMatch(row -> row.employeeNo().equals(eligible.getPerson().getEmployeeNo())));
        assertFalse(holders.stream().anyMatch(row -> row.employeeNo().equals(noAssignment.getPerson().getEmployeeNo())));
        assertNull(jdbc.queryForObject("SELECT end_date FROM assignment WHERE id = ?", LocalDate.class, openId));
        assertEquals(period.atDay(18),
                jdbc.queryForObject("SELECT end_date FROM assignment WHERE id = ?", LocalDate.class, endingId));

        String report = mockMvc.perform(get("/api/v1/eligibility/below-grade-holders")
                        .param("period", "202504"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        assertTrue(report.contains(open.getPerson().getEmployeeNo()));
        assertTrue(report.contains(ending.getPerson().getEmployeeNo()));
        assertFalse(report.contains(eligible.getPerson().getEmployeeNo()));
    }

    @Test
    void GF03_unknownEmployeeIsRejected() throws Exception {
        for (String employeeNo : List.of("GF03-UNKNOWN-" + UUID.randomUUID(), " ", "   ")) {
            EligibilityDecision car = eligibilityService.carRequest(
                    employeeNo, CarRequestStep.EMPLOYEE, LocalDate.of(2026, 10, 1));
            EligibilityDecision claim = eligibilityService.mileageClaim(employeeNo, LocalDate.of(2026, 10, 1));
            EligibilityDecision inquiry = eligibilityService.inquiry(employeeNo);
            EligibilityReason expected = employeeNo.isBlank()
                    ? EligibilityReason.EMPLOYEE_NUMBER_REQUIRED
                    : EligibilityReason.EMPLOYEE_NOT_FOUND;
            assertFalse(car.allowed());
            assertEquals(expected, car.reason());
            assertFalse(claim.allowed());
            assertEquals(expected, claim.reason());
            assertFalse(inquiry.allowed());
            assertEquals(expected, inquiry.reason());
        }
        assertEquals(EligibilityReason.EMPLOYEE_NUMBER_REQUIRED,
                eligibilityService.carRequest(null, CarRequestStep.EMPLOYEE, LocalDate.now()).reason());
        assertEquals(EligibilityReason.EMPLOYEE_NUMBER_REQUIRED,
                eligibilityService.mileageClaim(null, LocalDate.now()).reason());
        assertEquals(EligibilityReason.EMPLOYEE_NUMBER_REQUIRED, eligibilityService.inquiry(null).reason());

        Person normalized = createPerson("E123");
        assertEquals(normalized.getId(), eligibilityService.findPerson(" e123 ").orElseThrow().getId());
        assertEquals("E123", EmployeeNumbers.normalize(" e123 "));

        String unknown = unique("GF03");
        mockMvc.perform(get("/api/v1/employees/{employeeNo}", unknown))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("EMPLOYEE_NOT_FOUND"));
        mockMvc.perform(get("/api/v1/eligibility/car-request")
                        .param("employeeNo", unknown)
                        .param("step", "EMPLOYEE"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.allowed").value(false))
                .andExpect(jsonPath("$.reason").value("EMPLOYEE_NOT_FOUND"));
        mockMvc.perform(get("/api/v1/eligibility/mileage-claim")
                        .param("employeeNo", unknown)
                        .param("claimDate", "2026-10-01"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.allowed").value(false))
                .andExpect(jsonPath("$.reason").value("EMPLOYEE_NOT_FOUND"));
        mockMvc.perform(get("/api/v1/eligibility/car-request")
                        .param("employeeNo", "")
                        .param("step", "EMPLOYEE"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reason").value("EMPLOYEE_NUMBER_REQUIRED"));
        mockMvc.perform(get("/api/v1/eligibility/mileage-claim")
                        .param("employeeNo", " ")
                        .param("claimDate", "2026-10-01"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reason").value("EMPLOYEE_NUMBER_REQUIRED"));
        mockMvc.perform(get("/api/v1/employees/{employeeNo}", "  "))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("EMPLOYEE_NUMBER_REQUIRED"));

        assertThrows(EligibilityException.class,
                () -> eligibilityService.requireCarRequest(" ", CarRequestStep.EMPLOYEE, LocalDate.now()));
        assertThrows(EligibilityException.class,
                () -> eligibilityService.requireCarRequest(unknown, CarRequestStep.EMPLOYEE, LocalDate.now()));
        assertThrows(EligibilityException.class,
                () -> eligibilityService.requireMileageClaim(" ", LocalDate.now()));
        assertThrows(EligibilityException.class,
                () -> eligibilityService.requireMileageClaim(unknown, LocalDate.now()));
        assertThrows(EligibilityException.class, () -> eligibilityService.requireInquiry(" "));
        assertThrows(EligibilityException.class, () -> eligibilityService.requireInquiry(unknown));
    }

    @Test
    void GF03_employeeStatusGatesCarRequest() throws Exception {
        LocalDate today = LocalDate.of(2026, 10, 1);
        Employment active = createEmployment(
                unique("GF03"), profile.minGrade(), EmploymentStatus.ACTIVE, LocalDate.of(2020, 1, 1), null);
        Employment left = createEmployment(
                unique("GF03"), profile.minGrade(), EmploymentStatus.LEFT,
                LocalDate.of(2020, 1, 1), LocalDate.of(2025, 1, 31));
        Employment transferred = createEmployment(
                unique("GF03"), profile.minGrade(), EmploymentStatus.TRANSFERRED,
                LocalDate.of(2020, 1, 1), null);
        Employment expiredActive = createEmployment(
                unique("GF03"), profile.minGrade(), EmploymentStatus.ACTIVE,
                LocalDate.of(2020, 1, 1), LocalDate.of(2026, 9, 30));
        Employment hiredTomorrow = createEmployment(
                unique("GF03"), profile.minGrade(), EmploymentStatus.ACTIVE, today.plusDays(1), null);
        Employment hiredToday = createEmployment(
                unique("GF03"), profile.minGrade(), EmploymentStatus.ACTIVE, today, null);

        assertTrue(eligibilityService.carRequest(
                active.getPerson().getEmployeeNo(), CarRequestStep.EMPLOYEE, today).allowed());
        assertEquals(EligibilityReason.NOT_ACTIVE, eligibilityService.carRequest(
                left.getPerson().getEmployeeNo(), CarRequestStep.EMPLOYEE, today).reason());
        assertEquals(EligibilityReason.NOT_ACTIVE, eligibilityService.carRequest(
                transferred.getPerson().getEmployeeNo(), CarRequestStep.EMPLOYEE, today).reason());
        assertEquals(EligibilityReason.NOT_ACTIVE, eligibilityService.carRequest(
                expiredActive.getPerson().getEmployeeNo(), CarRequestStep.EMPLOYEE, today).reason());
        assertEquals(EligibilityReason.NOT_ACTIVE, eligibilityService.carRequest(
                hiredTomorrow.getPerson().getEmployeeNo(), CarRequestStep.EMPLOYEE, today).reason());
        assertTrue(eligibilityService.carRequest(
                hiredToday.getPerson().getEmployeeNo(), CarRequestStep.EMPLOYEE, today).allowed());
        assertTrue(eligibilityService.inquiry(left.getPerson().getEmployeeNo()).allowed());
        assertTrue(eligibilityService.inquiry(transferred.getPerson().getEmployeeNo()).allowed());

        Person rehired = createPerson(unique("GF03"));
        Employment olderActive = employmentRepository.save(new Employment(
                rehired, profile.minGrade(), EmploymentStatus.ACTIVE,
                LocalDate.of(2010, 1, 1), null, BigDecimal.ZERO, null));
        Employment newerLeft = employmentRepository.save(new Employment(
                rehired, profile.minGrade(), EmploymentStatus.LEFT,
                LocalDate.of(2020, 1, 1), LocalDate.of(2025, 1, 31), BigDecimal.ZERO, null));
        assertTrue(olderActive.getHireDate().isBefore(newerLeft.getHireDate()));
        assertEquals(newerLeft.getId(), eligibilityService.currentEmployment(rehired).orElseThrow().getId());
        assertEquals(EligibilityReason.NOT_ACTIVE, eligibilityService.carRequest(
                rehired.getEmployeeNo(), CarRequestStep.EMPLOYEE, today).reason());

        mockMvc.perform(get("/api/v1/eligibility/car-request")
                        .param("employeeNo", active.getPerson().getEmployeeNo())
                        .param("step", "CONFIRM")
                        .param("date", "2026-10-27"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.allowed").value(true));
        mockMvc.perform(get("/api/v1/eligibility/car-request")
                        .param("employeeNo", left.getPerson().getEmployeeNo())
                        .param("step", "CONFIRM")
                        .param("date", "2026-10-27"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.allowed").value(false))
                .andExpect(jsonPath("$.reason").value("NOT_ACTIVE"));
    }

    @Test
    void GF03_leaverMayClaimUpToLeavingDate() throws Exception {
        Employment left = createEmployment(
                unique("GF03"), profile.minGrade(), EmploymentStatus.LEFT,
                LocalDate.of(2020, 1, 1), LocalDate.of(2025, 1, 31));
        EligibilityDecision lastDay = eligibilityService.mileageClaim(
                left.getPerson().getEmployeeNo(), LocalDate.of(2025, 1, 31));
        assertTrue(lastDay.allowed());
        assertEquals(left.getId(), lastDay.employmentId());
        EligibilityDecision after = eligibilityService.mileageClaim(
                left.getPerson().getEmployeeNo(), LocalDate.of(2025, 2, 1));
        assertFalse(after.allowed());
        assertEquals(EligibilityReason.CLAIM_AFTER_LEAVING_DATE, after.reason());
        mockMvc.perform(get("/api/v1/eligibility/mileage-claim")
                        .param("employeeNo", left.getPerson().getEmployeeNo())
                        .param("claimDate", "2025-01-31"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.allowed").value(true))
                .andExpect(jsonPath("$.employmentId").value(left.getId()));
        mockMvc.perform(get("/api/v1/eligibility/mileage-claim")
                        .param("employeeNo", left.getPerson().getEmployeeNo())
                        .param("claimDate", "2025-02-01"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.allowed").value(false))
                .andExpect(jsonPath("$.reason").value("CLAIM_AFTER_LEAVING_DATE"));
        mockMvc.perform(get("/api/v1/eligibility/mileage-claim")
                        .param("employeeNo", left.getPerson().getEmployeeNo())
                        .param("claimDate", "27.10.2026"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("BAD_REQUEST"))
                .andExpect(jsonPath("$.message").value("Bad Request"));
        Person withNoHistory = createPerson(unique("GF03"));
        assertEquals(EligibilityReason.NO_EMPLOYMENT_ON_DATE,
                eligibilityService.mileageClaim(withNoHistory.getEmployeeNo(), LocalDate.of(2025, 1, 1)).reason());

        Person withEmploymentGap = createPerson(unique("GF03"));
        employmentRepository.save(new Employment(
                withEmploymentGap, profile.minGrade(), EmploymentStatus.LEFT,
                LocalDate.of(2020, 1, 1), LocalDate.of(2022, 12, 31), BigDecimal.ZERO, null));
        employmentRepository.save(new Employment(
                withEmploymentGap, profile.minGrade(), EmploymentStatus.ACTIVE,
                LocalDate.of(2024, 1, 1), null, BigDecimal.ZERO, null));
        assertEquals(EligibilityReason.NO_EMPLOYMENT_ON_DATE, eligibilityService.mileageClaim(
                withEmploymentGap.getEmployeeNo(), LocalDate.of(2023, 6, 1)).reason());
        assertEquals(EligibilityReason.NO_EMPLOYMENT_ON_DATE, eligibilityService.mileageClaim(
                withEmploymentGap.getEmployeeNo(), LocalDate.of(2019, 12, 31)).reason());

        Employment active = createEmployment(
                unique("GF03"), profile.minGrade(), EmploymentStatus.ACTIVE, LocalDate.of(2020, 1, 1), null);
        assertTrue(eligibilityService.mileageClaim(
                active.getPerson().getEmployeeNo(), LocalDate.of(2025, 1, 1)).allowed());
        Employment transferred = createEmployment(
                unique("GF03"), profile.minGrade(), EmploymentStatus.TRANSFERRED,
                LocalDate.of(2020, 1, 1), LocalDate.of(2025, 12, 31));
        EligibilityDecision transferClaim = eligibilityService.mileageClaim(
                transferred.getPerson().getEmployeeNo(), LocalDate.of(2025, 1, 1));
        assertFalse(transferClaim.allowed());
        assertEquals(EligibilityReason.NOT_ACTIVE, transferClaim.reason());
    }

    @Test
    void GF04_rehireEmploymentsAreKeptApart() throws Exception {
        List<LegacyEmployee> employeeRows = readRecords("../mainframe/unload/EMPLOYEE.dat", 100)
                .stream()
                .map(EligibilityIntegrationTest::parseEmployee)
                .filter(row -> List.of("E1010398", "E1010524").contains(row.employeeNo()))
                .toList();
        List<LegacyAssignment> assignmentRows = readRecords("../mainframe/unload/ASSIGNMENT.dat", 64)
                .stream()
                .map(EligibilityIntegrationTest::parseAssignment)
                .filter(row -> List.of("E1010398", "E1010524").contains(row.employeeNo()))
                .toList();
        List<LegacyClaim> claimRows = readRecords("../mainframe/unload/MILECLM.dat", 64)
                .stream()
                .map(EligibilityIntegrationTest::parseClaim)
                .filter(row -> List.of("E1010398", "E1010524").contains(row.employeeNo()))
                .toList();

        List<EmploymentHistoryLoader.LegacyEmploymentRecord> records = employeeRows.stream()
                .map(row -> new EmploymentHistoryLoader.LegacyEmploymentRecord(
                        "MF:" + row.dbkey(),
                        row.employeeNo(),
                        row.lastName(),
                        row.firstName(),
                        row.grade(),
                        row.status(),
                        row.hireDate(),
                        row.leaveDate(),
                        row.monthlyContribution()))
                .toList();
        List<Employment> loaded = historyLoader.load(records);
        assertEquals(4, loaded.size());

        for (String employeeNo : List.of("E1010398", "E1010524")) {
            assertEquals(1, personRepository.findByEmployeeNo(employeeNo).stream().count());
            Person person = personRepository.findByEmployeeNo(employeeNo).orElseThrow();
            assertEquals(2, eligibilityService.employments(person).size());
            Employment current = eligibilityService.currentEmployment(person).orElseThrow();
            assertEquals(EmploymentStatus.ACTIVE, current.getStatus());
            LegacyEmployee latestRecord = employeeRows.stream()
                    .filter(row -> row.employeeNo().equals(employeeNo) && row.status() == EmploymentStatus.ACTIVE)
                    .findFirst()
                    .orElseThrow();
            assertEquals(latestRecord.firstName(), person.getFirstName());
            assertEquals(latestRecord.lastName(), person.getLastName());
            assertEquals(current.getId(), historyLoader.employmentByLegacyRef(
                    "MF:" + (employeeNo.equals("E1010398") ? "0001286624" : "0001286994"))
                    .orElseThrow().getId());
        }

        Employment e1010398Left = historyLoader.employmentByLegacyRef("MF:0001282406").orElseThrow();
        Employment e1010398Rehire = historyLoader.employmentByLegacyRef("MF:0001286624").orElseThrow();
        assertEquals(5, e1010398Left.getGrade());
        assertEquals(LocalDate.of(2004, 4, 30), e1010398Left.getHireDate());
        assertEquals(LocalDate.of(2014, 6, 9), e1010398Left.getLeaveDate());
        assertEquals(EmploymentStatus.LEFT, e1010398Left.getStatus());
        assertEquals(7, e1010398Rehire.getGrade());
        assertEquals(LocalDate.of(2020, 3, 5), e1010398Rehire.getHireDate());
        Employment e1010524Left = historyLoader.employmentByLegacyRef("MF:0001283257").orElseThrow();
        Employment e1010524Rehire = historyLoader.employmentByLegacyRef("MF:0001286994").orElseThrow();
        assertEquals(9, e1010524Left.getGrade());
        assertEquals(LocalDate.of(2007, 2, 7), e1010524Left.getHireDate());
        assertEquals(LocalDate.of(2015, 3, 4), e1010524Left.getLeaveDate());
        assertEquals(11, e1010524Rehire.getGrade());
        assertEquals(LocalDate.of(2021, 12, 27), e1010524Rehire.getHireDate());

        assertEquals(6, assignmentRows.size());
        for (LegacyAssignment row : assignmentRows) {
            Employment byReference = historyLoader.employmentByLegacyRef("MF:" + row.employeeDbkey()).orElseThrow();
            Employment onDate = eligibilityService.employmentOn(row.employeeNo(), row.startDate()).orElseThrow();
            assertEquals(byReference.getId(), onDate.getId());
            long vehicleId = jdbc.queryForObject(
                    "INSERT INTO vehicle (registration, status) VALUES (?, 'AVAILABLE') "
                            + "ON CONFLICT (registration) DO UPDATE SET registration = EXCLUDED.registration RETURNING id",
                    Long.class, row.vehicleId());
            jdbc.update(
                    "INSERT INTO assignment (employment_id, vehicle_id, start_date, end_date, reason) "
                            + "VALUES (?, ?, ?, ?, ?)",
                    byReference.getId(), vehicleId, row.startDate(), row.endDate(), row.reason());
        }
        assertEquals(31, claimRows.size());
        for (LegacyClaim row : claimRows) {
            Employment byReference = historyLoader.employmentByLegacyRef("MF:" + row.employeeDbkey()).orElseThrow();
            Employment onDate = eligibilityService.employmentOn(row.employeeNo(), row.claimDate()).orElseThrow();
            assertEquals(byReference.getId(), onDate.getId());
            jdbc.update(
                    "INSERT INTO mileage_claim (employment_id, claim_date, distance, status) VALUES (?, ?, ?, ?)",
                    byReference.getId(), row.claimDate(), row.miles(), row.status());
        }

        assertEquals(1, assignmentCount(e1010398Left));
        assertEquals(1, assignmentCount(e1010524Left));
        assertEquals(1, assignmentCount(e1010398Rehire));
        assertEquals(3, assignmentCount(e1010524Rehire));
        assertEquals(0, claimCount(e1010398Left));
        assertEquals(0, claimCount(e1010524Left));
        assertEquals(20, claimCount(e1010398Rehire));
        assertEquals(11, claimCount(e1010524Rehire));
        List<Employment> reloaded = historyLoader.load(records);
        assertEquals(4, reloaded.size());
        assertEquals(java.util.Set.of(e1010398Left.getId(), e1010398Rehire.getId()),
                reloaded.stream()
                        .filter(item -> item.getPerson().getEmployeeNo().equals("E1010398"))
                        .map(Employment::getId)
                        .collect(java.util.stream.Collectors.toSet()));
        assertEquals(4, jdbc.queryForObject("SELECT COUNT(*) FROM employment WHERE legacy_ref LIKE 'MF:%'", Integer.class));

        EmploymentHistoryLoader.LegacyEmploymentRecord originalRehire = records.stream()
                .filter(record -> record.legacyRef().equals("MF:0001286624"))
                .findFirst()
                .orElseThrow();
        EmploymentHistoryLoader.LegacyEmploymentRecord changedRehire =
                new EmploymentHistoryLoader.LegacyEmploymentRecord(
                        originalRehire.legacyRef(),
                        originalRehire.employeeNo(),
                        originalRehire.lastName(),
                        originalRehire.firstName(),
                        8,
                        EmploymentStatus.LEFT,
                        originalRehire.hireDate(),
                        LocalDate.of(2024, 12, 31),
                        new BigDecimal("87.65"));
        List<Employment> updated = historyLoader.load(List.of(changedRehire));
        assertEquals(1, updated.size());
        assertEquals(e1010398Rehire.getId(), updated.get(0).getId());
        assertEquals(8, updated.get(0).getGrade());
        assertEquals(EmploymentStatus.LEFT, updated.get(0).getStatus());
        assertEquals(LocalDate.of(2024, 12, 31), updated.get(0).getLeaveDate());
        assertEquals(new BigDecimal("87.65"), updated.get(0).getMonthlyContribution());
        assertEquals(2, eligibilityService.employments(
                personRepository.findByEmployeeNo("E1010398").orElseThrow()).size());

        EmploymentHistoryLoader.LegacyEmploymentRecord conflicting = new EmploymentHistoryLoader.LegacyEmploymentRecord(
                changedRehire.legacyRef(),
                unique("GF04"),
                "Other",
                "Person",
                8,
                EmploymentStatus.ACTIVE,
                LocalDate.of(2020, 1, 1),
                null,
                BigDecimal.ZERO);
        IllegalStateException conflict = assertThrows(
                IllegalStateException.class, () -> historyLoader.load(List.of(conflicting)));
        assertEquals("legacy reference MF:0001286624 already belongs to another employee", conflict.getMessage());
    }

    @Test
    void GF02_invalidBatchPeriodReturnsBadRequest() throws Exception {
        mockMvc.perform(get("/api/v1/eligibility/below-grade-holders").param("period", "2025-04"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void GF33_noLookupBeanFallsBackToEmptyCurrentCar() {
        Person person = createPerson(unique("GF03"));
        assertNull(employeeSearchService.search(person.getEmployeeNo()).get(0).currentCar());
    }

    @Test
    void GF04_migrationKeepsNamesAndBackfillsStatus() {
        String schema = "v11_migration_test";
        jdbc.execute("DROP SCHEMA IF EXISTS " + schema + " CASCADE");
        Flyway flyway = Flyway.configure()
                .dataSource(jdbc.getDataSource())
                .locations("classpath:db/migration/domain")
                .schemas(schema)
                .defaultSchema(schema)
                .target(MigrationVersion.fromVersion("1.0"))
                .load();
        flyway.migrate();

        Long personId = jdbc.queryForObject(
                "INSERT INTO " + schema + ".person (employee_no, name) VALUES (?, ?) RETURNING id",
                Long.class, unique("GF04"), "Legacy Name");
        String employmentSql = "INSERT INTO " + schema
                + ".employment (person_id, grade, status, hire_date, leave_date, monthly_contribution) "
                + "VALUES (?, ?, ?, ?, ?, ?)";
        jdbc.update(employmentSql, personId, 5, null, LocalDate.of(2020, 1, 1), null, BigDecimal.ZERO);
        jdbc.update(employmentSql, personId, 6, null,
                LocalDate.of(2021, 1, 1), LocalDate.of(2022, 1, 1), BigDecimal.ZERO);
        jdbc.update(employmentSql, personId, 7, "FORMER",
                LocalDate.of(2023, 1, 1), null, BigDecimal.ZERO);

        flyway = Flyway.configure()
                .dataSource(jdbc.getDataSource())
                .locations("classpath:db/migration/domain")
                .schemas(schema)
                .defaultSchema(schema)
                .load();
        flyway.migrate();

        assertEquals("Legacy Name", jdbc.queryForObject(
                "SELECT last_name FROM " + schema + ".person WHERE id = ?", String.class, personId));
        assertNull(jdbc.queryForObject(
                "SELECT first_name FROM " + schema + ".person WHERE id = ?", String.class, personId));
        assertEquals(List.of("ACTIVE", "LEFT", "LEFT"), jdbc.queryForList(
                "SELECT status FROM " + schema + ".employment WHERE person_id = ? ORDER BY id",
                String.class, personId));
    }

    private Employment createEmployment(
            String employeeNo, Integer grade, EmploymentStatus status, LocalDate hireDate, LocalDate leaveDate) {
        Person person = createPerson(employeeNo);
        return employmentRepository.save(new Employment(
                person, grade, status, hireDate, leaveDate, BigDecimal.ZERO, null));
    }

    private Person createPerson(String employeeNo) {
        return personRepository.save(new Person(employeeNo, "First" + employeeNo, "Last" + employeeNo));
    }

    private long createAssignment(Employment employment, String registration, LocalDate startDate, LocalDate endDate) {
        long vehicleId = jdbc.queryForObject(
                "INSERT INTO vehicle (registration, status) VALUES (?, 'AVAILABLE') RETURNING id",
                Long.class, registration);
        return jdbc.queryForObject(
                "INSERT INTO assignment (employment_id, vehicle_id, start_date, end_date) "
                        + "VALUES (?, ?, ?, ?) RETURNING id",
                Long.class, employment.getId(), vehicleId, startDate, endDate);
    }

    private int assignmentCount(Employment employment) {
        return jdbc.queryForObject(
                "SELECT COUNT(*) FROM assignment WHERE employment_id = ?", Integer.class, employment.getId());
    }

    private int claimCount(Employment employment) {
        return jdbc.queryForObject(
                "SELECT COUNT(*) FROM mileage_claim WHERE employment_id = ?", Integer.class, employment.getId());
    }

    private static String unique(String prefix) {
        return prefix + "-" + UUID.randomUUID().toString().replace("-", "").substring(0, 12).toUpperCase();
    }

    private static List<byte[]> readRecords(String path, int recordLength) throws IOException {
        byte[] bytes = Files.readAllBytes(Path.of(path));
        if (bytes.length % recordLength != 0) {
            throw new IOException("Unexpected record length in " + path);
        }
        List<byte[]> records = new ArrayList<>();
        for (int offset = 0; offset < bytes.length; offset += recordLength) {
            records.add(java.util.Arrays.copyOfRange(bytes, offset, offset + recordLength));
        }
        return records;
    }

    private static LegacyEmployee parseEmployee(byte[] record) {
        return new LegacyEmployee(
                text(record, 0, 10),
                text(record, 10, 8),
                text(record, 18, 20),
                text(record, 38, 15),
                Integer.parseInt(text(record, 53, 2)),
                employmentStatus(text(record, 77, 1)),
                date(record, 61),
                date(record, 69),
                packedDecimal(record, 78, 4, 2));
    }

    private static LegacyAssignment parseAssignment(byte[] record) {
        return new LegacyAssignment(
                text(record, 10, 8),
                text(record, 18, 10),
                text(record, 28, 8),
                date(record, 36),
                date(record, 44),
                text(record, 52, 2));
    }

    private static LegacyClaim parseClaim(byte[] record) {
        return new LegacyClaim(
                text(record, 10, 8),
                text(record, 18, 10),
                text(record, 28, 8),
                date(record, 36),
                Integer.parseInt(text(record, 44, 5)),
                text(record, 49, 1));
    }

    private static String text(byte[] record, int offset, int length) {
        return new String(record, offset, length, StandardCharsets.US_ASCII).trim();
    }

    private static LocalDate date(byte[] record, int offset) {
        String value = text(record, offset, 8);
        return value.equals("00000000") ? null : LocalDate.parse(value, BASIC_DATE);
    }

    private static BigDecimal packedDecimal(byte[] record, int offset, int length, int scale) {
        StringBuilder digits = new StringBuilder();
        int sign = 1;
        for (int index = 0; index < length; index++) {
            int value = record[offset + index] & 0xff;
            digits.append(value >>> 4);
            int low = value & 0x0f;
            if (index == length - 1) {
                if (low == 0x0d) {
                    sign = -1;
                }
            } else {
                digits.append(low);
            }
        }
        BigDecimal result = new BigDecimal(digits.toString()).movePointLeft(scale);
        return sign < 0 ? result.negate() : result;
    }

    private static EmploymentStatus employmentStatus(String value) {
        return switch (value) {
            case "A" -> EmploymentStatus.ACTIVE;
            case "T" -> EmploymentStatus.LEFT;
            case "X" -> EmploymentStatus.TRANSFERRED;
            default -> throw new IllegalArgumentException("Unsupported legacy status " + value);
        };
    }

    private record LegacyEmployee(
            String dbkey,
            String employeeNo,
            String lastName,
            String firstName,
            Integer grade,
            EmploymentStatus status,
            LocalDate hireDate,
            LocalDate leaveDate,
            BigDecimal monthlyContribution) {
    }

    private record LegacyAssignment(
            String employeeNo,
            String employeeDbkey,
            String vehicleId,
            LocalDate startDate,
            LocalDate endDate,
            String reason) {
    }

    private record LegacyClaim(
            String employeeNo,
            String employeeDbkey,
            String vehicleId,
            LocalDate claimDate,
            int miles,
            String status) {
    }
}
