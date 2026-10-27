package com.otterworks.fleet;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.fleet.assignment.CarRequestResult;
import com.otterworks.fleet.assignment.ConfirmationRequest;
import com.otterworks.fleet.assignment.DoubleHolderView;
import com.otterworks.fleet.assignment.DraftUpdateRequest;
import com.otterworks.fleet.assignment.DraftView;
import com.otterworks.fleet.assignment.NewVehicleInput;
import com.otterworks.fleet.assignment.PoolVehicle;
import com.otterworks.fleet.config.CountryProfile;
import com.otterworks.fleet.domain.Assignment;
import com.otterworks.fleet.domain.AssignmentRepository;
import com.otterworks.fleet.domain.CarRequest;
import com.otterworks.fleet.domain.CarRequestRepository;
import com.otterworks.fleet.domain.Employment;
import com.otterworks.fleet.domain.EmploymentRepository;
import com.otterworks.fleet.domain.EmploymentStatus;
import com.otterworks.fleet.domain.Person;
import com.otterworks.fleet.domain.PersonRepository;
import com.otterworks.fleet.domain.Vehicle;
import com.otterworks.fleet.domain.VehicleRepository;
import com.otterworks.fleet.eligibility.CarRequestStep;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CyclicBarrier;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@Import(AssignmentIntegrationTest.FixedClockConfiguration.class)
@TestPropertySource(properties =
        "fleet.assignment.legacy-assignment-unload=../mainframe/unload/ASSIGNMENT.dat")
class AssignmentIntegrationTest extends AbstractPostgresIntegrationTest {

    private static final LocalDate TODAY = LocalDate.of(2026, 10, 27);
    private static final LocalDate EMPLOYMENT_START = LocalDate.of(2020, 1, 1);

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private PersonRepository personRepository;

    @Autowired
    private EmploymentRepository employmentRepository;

    @Autowired
    private AssignmentRepository assignmentRepository;

    @Autowired
    private VehicleRepository vehicleRepository;

    @Autowired
    private CarRequestRepository carRequestRepository;

    @Autowired
    private CountryProfile profile;

    @Autowired
    private JdbcTemplate jdbc;

    @Test
    void GF05_secondOpenCarIsRefused() throws Exception {
        Employment employee = employee("GF05");
        Vehicle vehicle = vehicle("GF05-CAR");
        assignmentRepository.saveAndFlush(new Assignment(
                employee, vehicle, EMPLOYMENT_START, null, "NC", null));

        mockMvc.perform(put(draftPath(employee))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(new DraftUpdateRequest(
                                CarRequestStep.EMPLOYEE, null, null, null, null, null))))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("ALREADY_HAS_CAR"));
    }

    @Test
    void GF05_unconfirmedDoubleHoldersBlockCutover() throws Exception {
        List<DoubleHolderView> holders = doubleHolders();
        List<DoubleHolderView> unload = holders.stream()
                .filter(holder -> holder.source().equals("LEGACY_UNLOAD"))
                .toList();
        assertEquals(20, unload.size());
        assertTrue(unload.stream().allMatch(holder -> holder.assignments().size() == 2));
        assertTrue(unload.stream().allMatch(holder -> holder.assignments().stream()
                .map(assignment -> assignment.reason())
                .collect(java.util.stream.Collectors.toSet())
                .equals(Set.of("NC", "RP"))));
        DoubleHolderView sample = unload.stream()
                .filter(holder -> holder.employeeNo().equals("E1010559")
                        && holder.employmentLegacyRef().equals("MF:0001286661"))
                .findFirst()
                .orElseThrow();
        assertEquals(Set.of("A000700021", "A000700024"), sample.assignments().stream()
                .map(assignment -> assignment.legacyRef())
                .collect(java.util.stream.Collectors.toSet()));

        var assignment = sample.assignments().get(0);
        mockMvc.perform(post("/api/v1/assignments/cutover/double-holders/{ref}/confirmations",
                                sample.employmentLegacyRef())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(new ConfirmationRequest(
                                assignment.legacyRef(), assignment.startDate().plusDays(1)))))
                .andExpect(status().isCreated());
        List<DoubleHolderView> remaining = doubleHolders().stream()
                .filter(holder -> holder.source().equals("LEGACY_UNLOAD"))
                .toList();
        assertEquals(19, remaining.size());
        assertFalse(remaining.stream().anyMatch(holder ->
                holder.employmentLegacyRef().equals(sample.employmentLegacyRef())));

        DoubleHolderView another = remaining.get(0);
        var openAssignment = another.assignments().get(0);
        mockMvc.perform(post("/api/v1/assignments/cutover/double-holders/{ref}/confirmations",
                                another.employmentLegacyRef())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(new ConfirmationRequest("  ", openAssignment.startDate()))))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("CONFIRMATION_FIELDS_REQUIRED"));
        mockMvc.perform(post("/api/v1/assignments/cutover/double-holders/{ref}/confirmations",
                                another.employmentLegacyRef())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(new ConfirmationRequest(
                                openAssignment.legacyRef(), openAssignment.startDate().minusDays(1)))))
                .andExpect(status().isUnprocessableEntity());

        String employeeNo = "GF05-REHIRE-" + UUID.randomUUID().toString()
                .replace("-", "").substring(0, 12).toUpperCase(Locale.ROOT);
        Long personId = jdbc.queryForObject(
                "INSERT INTO person (employee_no, first_name, last_name) VALUES (?, ?, ?) RETURNING id",
                Long.class, employeeNo, "Rehire", "Holder");
        Long previousEmploymentId = jdbc.queryForObject(
                "INSERT INTO employment (person_id, grade, status, hire_date, leave_date) "
                        + "VALUES (?, ?, 'LEFT', ?, ?) RETURNING id",
                Long.class, personId, profile.minGrade(), TODAY.minusYears(3), TODAY.minusDays(3));
        Long currentEmploymentId = jdbc.queryForObject(
                "INSERT INTO employment (person_id, grade, status, hire_date) "
                        + "VALUES (?, ?, 'ACTIVE', ?) RETURNING id",
                Long.class, personId, profile.minGrade(), TODAY.minusDays(2));
        Long previousVehicleId = jdbc.queryForObject(
                "INSERT INTO vehicle (registration, list_price, co2_g_km, fuel, status) "
                        + "VALUES (?, ?, ?, ?, 'AVAILABLE') RETURNING id",
                Long.class, "GF05-REHIRE-OLD-" + UUID.randomUUID(), BigDecimal.ONE, 0, "D");
        Long currentVehicleId = jdbc.queryForObject(
                "INSERT INTO vehicle (registration, list_price, co2_g_km, fuel, status) "
                        + "VALUES (?, ?, ?, ?, 'AVAILABLE') RETURNING id",
                Long.class, "GF05-REHIRE-CURRENT-" + UUID.randomUUID(), BigDecimal.ONE, 0, "D");
        Long previousAssignmentId = jdbc.queryForObject(
                "INSERT INTO assignment (employment_id, vehicle_id, start_date, reason) "
                        + "VALUES (?, ?, ?, 'NC') RETURNING id",
                Long.class, previousEmploymentId, previousVehicleId, TODAY.minusYears(3));
        jdbc.update(
                "INSERT INTO assignment (employment_id, vehicle_id, start_date, reason) "
                        + "VALUES (?, ?, ?, 'RP')",
                currentEmploymentId, currentVehicleId, TODAY.minusDays(2));
        jdbc.update(
                "INSERT INTO double_holder_confirmation "
                        + "(employment_legacy_ref, assignment_legacy_ref, confirmed_return_date, confirmed_at) "
                        + "VALUES (?, ?, ?, ?)",
                "PERSON:" + employeeNo,
                "A000000001",
                TODAY,
                java.sql.Timestamp.from(Instant.parse("2026-10-27T12:00:00Z")));

        List<DoubleHolderView> serviceHolders = doubleHolders().stream()
                .filter(holder -> holder.source().equals("SERVICE")
                        && holder.employeeNo().equals(employeeNo))
                .toList();
        assertEquals(1, serviceHolders.size());
        DoubleHolderView rehireHolder = serviceHolders.get(0);
        assertEquals("PERSON:" + employeeNo, rehireHolder.employmentLegacyRef());
        assertEquals(2, rehireHolder.assignments().size());

        mockMvc.perform(post("/api/v1/assignments/cutover/double-holders/{ref}/confirmations",
                                rehireHolder.employmentLegacyRef())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(new ConfirmationRequest("A000000001", TODAY))))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("RETURN_REQUIRED"))
                .andExpect(jsonPath("$.message").value("record the return in the returns context"));
        assertEquals(1, doubleHolders().stream()
                .filter(holder -> holder.source().equals("SERVICE")
                        && holder.employeeNo().equals(employeeNo))
                .count());

        jdbc.update("UPDATE assignment SET end_date = ? WHERE id = ?", TODAY, previousAssignmentId);
        assertTrue(doubleHolders().stream().noneMatch(holder ->
                holder.source().equals("SERVICE") && holder.employeeNo().equals(employeeNo)));
    }

    @Test
    void GF06_assignmentRequiresKnownOrRegisteredVehicle() throws Exception {
        Employment employee = employee("GF06");
        Vehicle poolCar = vehicle("GF06-POOL");
        DraftUpdateRequest poolSelection = confirm("POOL", poolCar.getId(), null, null, TODAY);
        mockMvc.perform(put(draftPath(employee)).contentType(MediaType.APPLICATION_JSON).content(json(poolSelection)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.vehicleAvailable").value(true));
        mockMvc.perform(put(draftPath(employee)).contentType(MediaType.APPLICATION_JSON)
                        .content(json(confirm("POOL", Long.MAX_VALUE, null, null, TODAY))))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("VEHICLE_NOT_FOUND"));
        var vehicleRules = objectMapper.readTree(mockMvc.perform(get("/api/v1/assignments/vehicle-rules"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString());
        assertEquals(
                profile.benefitPercentSource() == CountryProfile.BenefitPercentSource.VEHICLE,
                java.util.stream.StreamSupport.stream(
                                vehicleRules.get("requiredNewVehicleFields").spliterator(), false)
                        .anyMatch(field -> field.asText().equals("benefitPercent")));

        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(
                "INSERT INTO vehicle (registration, list_price, co2_g_km, fuel, status) VALUES (?, ?, ?, ?, ?)",
                "GF06-INVALID-PRICE-" + UUID.randomUUID(), BigDecimal.ZERO, 10, "D", "AVAILABLE"));
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(
                "INSERT INTO vehicle (registration, list_price, co2_g_km, fuel, status) VALUES (?, ?, ?, ?, ?)",
                "GF06-INVALID-CO2-" + UUID.randomUUID(), BigDecimal.ONE, -1, "D", "AVAILABLE"));
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(
                "INSERT INTO vehicle (registration, list_price, co2_g_km, fuel, status) VALUES (?, ?, ?, ?, ?)",
                "GF06-INVALID-FUEL-" + UUID.randomUUID(), BigDecimal.ONE, 0, "X", "AVAILABLE"));

        NewVehicleInput invalidPrice = new NewVehicleInput(
                "  ab12   cde ", "Make", "Model", BigDecimal.ZERO, 0, null, benefitPercent());
        mockMvc.perform(put(draftPath(employee)).contentType(MediaType.APPLICATION_JSON)
                        .content(json(confirm("NEW", null, invalidPrice, null, TODAY))))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("LIST_PRICE_INVALID"));
        NewVehicleInput invalidCo2 = new NewVehicleInput(
                "  ab12   cde ", "Make", "Model", new BigDecimal("25000.00"), -1, null, benefitPercent());
        mockMvc.perform(put(draftPath(employee)).contentType(MediaType.APPLICATION_JSON)
                        .content(json(confirm("NEW", null, invalidCo2, null, TODAY))))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("CO2_INVALID"));

        NewVehicleInput valid = new NewVehicleInput(
                "  ab12   cde ", "Make", "Model", new BigDecimal("25000.00"), 0, null, benefitPercent());
        if (profile.benefitPercentSource() == CountryProfile.BenefitPercentSource.VEHICLE) {
            NewVehicleInput missingBenefit = new NewVehicleInput(
                    "AB12 CDE", "Make", "Model", new BigDecimal("25000.00"), 0, "D", null);
            mockMvc.perform(put(draftPath(employee)).contentType(MediaType.APPLICATION_JSON)
                            .content(json(confirm("NEW", null, missingBenefit, null, TODAY))))
                    .andExpect(status().isUnprocessableEntity())
                    .andExpect(jsonPath("$.code").value("BENEFIT_PERCENT_REQUIRED"));
        }
        DraftView saved = objectMapper.readValue(
                mockMvc.perform(put(draftPath(employee)).contentType(MediaType.APPLICATION_JSON)
                                .content(json(confirm("NEW", null, valid, null, TODAY))))
                        .andExpect(status().isOk())
                        .andReturn().getResponse().getContentAsString(),
                DraftView.class);
        assertEquals("AB12 CDE", saved.newVehicle().plate());
        CarRequestResult result = submit(employee, saved.draftId(), 201);
        assertEquals("AB12 CDE", result.registration());
        assertEquals("D", vehicleRepository.findAll().stream()
                .filter(vehicle -> vehicle.getRegistration().equals("AB12 CDE"))
                .findFirst().orElseThrow().getFuel());
        Employment duplicatePlateEmployee = employee("GF06");
        mockMvc.perform(put(draftPath(duplicatePlateEmployee)).contentType(MediaType.APPLICATION_JSON)
                        .content(json(confirm("NEW", null, valid, null, TODAY))))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("PLATE_ALREADY_REGISTERED"));
    }

    @Test
    void GF07_staleSubmitIsRefusedCarNoLongerAvailable() throws Exception {
        Vehicle poolCar = vehicle("GF07-RACE");
        Employment first = employee("GF07");
        Employment second = employee("GF07");
        DraftView firstDraft = saveConfirm(first, poolCar.getId(), "POOL", null, "NC", TODAY);
        DraftView secondDraft = saveConfirm(second, poolCar.getId(), "POOL", null, "NC", TODAY);
        CyclicBarrier barrier = new CyclicBarrier(2);
        ExecutorService executor = Executors.newFixedThreadPool(2);
        try {
            Future<MvcResult> one = executor.submit(() -> {
                barrier.await();
                return submitResponse(first, firstDraft.draftId());
            });
            Future<MvcResult> two = executor.submit(() -> {
                barrier.await();
                return submitResponse(second, secondDraft.draftId());
            });
            MvcResult oneResult = one.get();
            MvcResult twoResult = two.get();
            assertNotEquals(oneResult.getResponse().getStatus(), twoResult.getResponse().getStatus());
            MvcResult winner = oneResult.getResponse().getStatus() == 201 ? oneResult : twoResult;
            MvcResult loser = winner == oneResult ? twoResult : oneResult;
            assertEquals(201, winner.getResponse().getStatus());
            assertEquals(409, loser.getResponse().getStatus());
            assertEquals("CAR_NO_LONGER_AVAILABLE",
                    objectMapper.readTree(loser.getResponse().getContentAsString()).get("code").asText());
            assertTrue(java.util.stream.StreamSupport.stream(
                            objectMapper.readTree(loser.getResponse().getContentAsString())
                                    .get("pool").spliterator(), false)
                    .noneMatch(vehicle -> vehicle.get("id").asLong() == poolCar.getId()));

            Employment losingEmployee = loser == oneResult ? first : second;
            DraftView reset = objectMapper.readValue(
                    mockMvc.perform(get(draftPath(losingEmployee)))
                            .andExpect(status().isOk())
                            .andReturn().getResponse().getContentAsString(),
                    DraftView.class);
            assertEquals(CarRequestStep.VEHICLE, reset.step());
            assertNull(reset.poolVehicleId());
            assertEquals(1, jdbc.queryForObject(
                    "SELECT COUNT(*) FROM assignment WHERE vehicle_id = ? AND end_date IS NULL",
                    Integer.class, poolCar.getId()));
            assertEquals(1, jdbc.queryForObject(
                    "SELECT COUNT(*) FROM car_request WHERE vehicle_id = ?",
                    Integer.class, poolCar.getId()));
        } finally {
            executor.shutdownNow();
        }
    }

    @Test
    void GF07_poolLoanCountsAsHolding() throws Exception {
        Employment holder = employee("GF07");
        Vehicle poolCar = vehicle("GF07-POOL-LOAN");
        assignmentRepository.saveAndFlush(new Assignment(
                holder, poolCar, EMPLOYMENT_START, null, "PL", null));
        assertFalse(pool().stream().anyMatch(vehicle -> vehicle.id().equals(poolCar.getId())));

        Employment requester = employee("GF07");
        mockMvc.perform(put(draftPath(requester)).contentType(MediaType.APPLICATION_JSON)
                        .content(json(confirm("POOL", poolCar.getId(), null, null, TODAY))))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("VEHICLE_NOT_AVAILABLE"));
    }

    @Test
    void GF07_oneOpenAssignmentPerCarConstraint() {
        Employment first = employee("GF07");
        Employment second = employee("GF07");
        Vehicle car = vehicle("GF07-CONSTRAINT");
        jdbc.update("INSERT INTO assignment (employment_id, vehicle_id, start_date, end_date) VALUES (?, ?, ?, ?)",
                first.getId(), car.getId(), EMPLOYMENT_START, TODAY.minusDays(1));
        jdbc.update("INSERT INTO assignment (employment_id, vehicle_id, start_date, end_date) VALUES (?, ?, ?, NULL)",
                first.getId(), car.getId(), TODAY);
        assertThrows(DataIntegrityViolationException.class,
                () -> jdbc.update(
                        "INSERT INTO assignment (employment_id, vehicle_id, start_date, end_date) VALUES (?, ?, ?, NULL)",
                        second.getId(), car.getId(), TODAY));
        String indexDefinition = jdbc.queryForObject(
                "SELECT indexdef FROM pg_indexes WHERE indexname = 'assignment_one_open_per_vehicle'",
                String.class);
        assertTrue(indexDefinition.contains("end_date IS NULL"));
    }

    @Test
    void GF08_assignmentReasonIsRecorded() throws Exception {
        Employment defaultReasonEmployee = employee("GF08");
        DraftView defaultDraft = saveConfirm(
                defaultReasonEmployee, vehicle("GF08-NC").getId(), "POOL", null, null, TODAY);
        assertEquals("NC", submit(defaultReasonEmployee, defaultDraft.draftId(), 201).reason());

        Employment poolLoanEmployee = employee("GF08");
        DraftView poolLoanDraft = saveConfirm(
                poolLoanEmployee, vehicle("GF08-PL").getId(), "POOL", null, "PL", TODAY);
        assertEquals("PL", submit(poolLoanEmployee, poolLoanDraft.draftId(), 201).reason());

        Employment invalidEmployee = employee("GF08");
        mockMvc.perform(put(draftPath(invalidEmployee)).contentType(MediaType.APPLICATION_JSON)
                        .content(json(confirm("POOL", vehicle("GF08-XX").getId(), null, "XX", TODAY))))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("INVALID_REASON"));
        Vehicle databaseCar = vehicle("GF08-DB");
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(
                "INSERT INTO assignment (employment_id, vehicle_id, start_date, reason) VALUES (?, ?, ?, ?)",
                invalidEmployee.getId(), databaseCar.getId(), TODAY, "XX"));
    }

    @Test
    void GF09_assignmentStartDateIsValidated() throws Exception {
        Employment employee = employee("GF09");
        Vehicle car = vehicle("GF09-CAR");
        DraftView defaultDate = saveConfirm(employee, car.getId(), "POOL", null, "NC", null);
        assertEquals(TODAY, defaultDate.startDate());

        Employment beforeHire = employee("GF09", TODAY.plusDays(1), null, EmploymentStatus.ACTIVE);
        assertError(beforeHire, confirm("POOL", vehicle("GF09-HIRE").getId(), null, "NC", TODAY),
                "START_DATE_OUTSIDE_EMPLOYMENT");
        Employment afterLeave = employee("GF09", EMPLOYMENT_START, TODAY.minusDays(1), EmploymentStatus.LEFT);
        assertError(afterLeave, confirm("POOL", vehicle("GF09-LEAVE").getId(), null, "NC", TODAY),
                "START_DATE_OUTSIDE_EMPLOYMENT");

        Employment historyEmployee = employee("GF09");
        Vehicle returnedCar = vehicle("GF09-RETURN");
        assignmentRepository.saveAndFlush(new Assignment(
                historyEmployee, returnedCar, EMPLOYMENT_START, TODAY.minusDays(2), "NC", null));
        assertError(historyEmployee, confirm("POOL", returnedCar.getId(), null, "NC", TODAY.minusDays(2)),
                "START_DATE_BEFORE_LAST_RETURN");
        assertError(employee("GF09"), confirm(
                        "POOL", vehicle("GF09-CLOSED").getId(), null, "NC", TODAY.minusMonths(1)),
                "START_DATE_IN_CLOSED_PERIOD");
    }

    @Test
    void GF10_assignmentIdentifierIsUnique() throws Exception {
        Employment first = employee("GF10");
        DraftView firstDraft = saveConfirm(first, vehicle("GF10-A").getId(), "POOL", null, "NC", TODAY);
        CarRequestResult firstResult = submit(first, firstDraft.draftId(), 201);
        Employment second = employee("GF10");
        DraftView secondDraft = saveConfirm(second, vehicle("GF10-B").getId(), "POOL", null, "NC", TODAY);
        CarRequestResult secondResult = submit(second, secondDraft.draftId(), 201);
        assertNotNull(firstResult.assignmentId());
        assertNotEquals(firstResult.assignmentId(), secondResult.assignmentId());
        assertNull(assignmentRepository.findById(firstResult.assignmentId()).orElseThrow().getLegacyRef());

        Employment migratedEmployee = employee("GF10");
        Vehicle legacyCar = vehicle("GF10-LEGACY");
        jdbc.update("INSERT INTO assignment (employment_id, vehicle_id, start_date, legacy_ref) "
                        + "VALUES (?, ?, ?, ?)",
                migratedEmployee.getId(), legacyCar.getId(), TODAY, "A000000001");
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(
                "INSERT INTO assignment (employment_id, vehicle_id, start_date, legacy_ref) VALUES (?, ?, ?, ?)",
                migratedEmployee.getId(), vehicle("GF10-LEGACY-DUP").getId(), TODAY, "A000000001"));
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(
                "INSERT INTO assignment (employment_id, vehicle_id, start_date, legacy_ref) VALUES (?, ?, ?, ?)",
                migratedEmployee.getId(), vehicle("GF10-LEGACY-INVALID").getId(), TODAY, "NOT-LEGACY"));
    }

    @Test
    void GF11_carRequestIsRecorded() throws Exception {
        Employment employee = employee("GF11");
        DraftView draft = saveConfirm(employee, vehicle("GF11-REQUEST").getId(), "POOL", null, "RP", TODAY);
        CarRequestResult result = submit(employee, draft.draftId(), 201);
        CarRequest request = carRequestRepository.findBySubmissionKey(draft.draftId()).orElseThrow();
        assertEquals("DELIVERED", request.getStatus());
        assertEquals(TODAY, request.getRequestedOn());
        assertEquals(result.assignmentId(), request.getAssignment().getId());
        assertEquals(result.registration(), request.getVehicle().getRegistration());

        Employment refused = employee("GF11");
        DraftView refusedDraft = saveConfirm(refused, vehicle("GF11-REFUSED").getId(), "POOL", null, "NC", TODAY);
        jdbc.update("UPDATE employment SET grade = ? WHERE id = ?", profile.minGrade() - 1, refused.getId());
        mockMvc.perform(post(submitPath(refused))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(new com.otterworks.fleet.assignment.SubmitRequest(refusedDraft.draftId()))))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("GRADE_BELOW_THRESHOLD"));
        assertFalse(carRequestRepository.findBySubmissionKey(refusedDraft.draftId()).isPresent());
        Employment invalidStatusEmployee = employee("GF11");
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(
                "INSERT INTO car_request (employment_id, requested_on, status) VALUES (?, ?, ?)",
                invalidStatusEmployee.getId(), TODAY, "PENDING"));
    }

    @Test
    void GF13_currentCarIsOpenAssignment() throws Exception {
        Employment employee = employee("GF13");
        Vehicle oldCar = vehicle("GF13-HISTORY");
        assignmentRepository.saveAndFlush(new Assignment(
                employee, oldCar, LocalDate.of(2024, 1, 1), LocalDate.of(2025, 1, 1), "NC", null));
        Vehicle currentCar = vehicle("GF13-CURRENT");
        Assignment open = assignmentRepository.saveAndFlush(new Assignment(
                employee, currentCar, LocalDate.of(2025, 2, 1), null, "RP", null));
        Vehicle secondOpenCar = vehicle("GF13-OLDER-OPEN");
        assignmentRepository.saveAndFlush(new Assignment(
                employee, secondOpenCar, LocalDate.of(2024, 12, 1), null, "NC", null));

        mockMvc.perform(get("/api/v1/employees/{employeeNo}/car", employee.getPerson().getEmployeeNo()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.current.id").value(open.getId()))
                .andExpect(jsonPath("$.current.registration").value(currentCar.getRegistration()))
                .andExpect(jsonPath("$.history[0].id").value(open.getId()))
                .andExpect(jsonPath("$.history[1].registration").value(secondOpenCar.getRegistration()))
                .andExpect(jsonPath("$.history[2].registration").value(oldCar.getRegistration()));
        mockMvc.perform(get("/api/v1/employees")
                        .param("q", employee.getPerson().getEmployeeNo()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].currentCar").value(currentCar.getRegistration()));
    }

    @Test
    void GF34_draftClearedOnSubmit() throws Exception {
        Employment employee = employee("GF34");
        DraftView draft = saveConfirm(employee, vehicle("GF34-CLEAR").getId(), "POOL", null, "NC", TODAY);
        submit(employee, draft.draftId(), 201);
        mockMvc.perform(get(draftPath(employee)))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("NO_DRAFT"));
    }

    @Test
    void GF34_draftCanBeDiscarded() throws Exception {
        Employment employee = employee("GF34");
        mockMvc.perform(put(draftPath(employee)).contentType(MediaType.APPLICATION_JSON)
                        .content(json(new DraftUpdateRequest(
                                CarRequestStep.EMPLOYEE, null, null, null, null, null))))
                .andExpect(status().isOk());
        mockMvc.perform(delete(draftPath(employee))).andExpect(status().isNoContent());
        mockMvc.perform(get(draftPath(employee)))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("NO_DRAFT"));
    }

    @Test
    void GF34_doubleSubmitCreatesOneRequest() throws Exception {
        Employment employee = employee("GF34");
        DraftView draft = saveConfirm(employee, vehicle("GF34-DOUBLE").getId(), "POOL", null, "NC", TODAY);
        CarRequestResult first = submit(employee, draft.draftId(), 201);
        CarRequestResult replay = submit(employee, draft.draftId(), 200);
        assertEquals(first.requestId(), replay.requestId());
        assertEquals(1, jdbc.queryForObject(
                "SELECT COUNT(*) FROM car_request WHERE submission_key = ?",
                Integer.class, draft.draftId()));
    }

    @Test
    void GF34_resumeRechecksEligibilityAndCar() throws Exception {
        Employment employee = employee("GF34");
        Vehicle poolCar = vehicle("GF34-RESUME");
        DraftView draft = saveConfirm(employee, poolCar.getId(), "POOL", null, "NC", TODAY);
        assertTrue(pool().stream().anyMatch(vehicle -> vehicle.id().equals(poolCar.getId())));
        assertTrue(draft.pool().stream().anyMatch(vehicle -> vehicle.id().equals(poolCar.getId())));

        Employment carTaker = employee("GF34");
        assignmentRepository.saveAndFlush(new Assignment(
                carTaker, poolCar, TODAY, null, "NC", null));
        DraftView unavailable = objectMapper.readValue(
                mockMvc.perform(get(draftPath(employee)))
                        .andExpect(status().isOk())
                        .andReturn().getResponse().getContentAsString(),
                DraftView.class);
        assertEquals(Boolean.FALSE, unavailable.vehicleAvailable());
        assertEquals(CarRequestStep.VEHICLE, unavailable.step());
        assertNull(unavailable.poolVehicleId());

        jdbc.update("UPDATE employment SET grade = ? WHERE id = ?", profile.minGrade() - 1, employee.getId());
        DraftView ineligible = objectMapper.readValue(
                mockMvc.perform(get(draftPath(employee)))
                        .andExpect(status().isOk())
                        .andReturn().getResponse().getContentAsString(),
                DraftView.class);
        assertFalse(ineligible.eligibility().allowed());
    }

    private Employment employee(String prefix) {
        return employee(prefix, EMPLOYMENT_START, null, EmploymentStatus.ACTIVE);
    }

    private Employment employee(
            String prefix, LocalDate hireDate, LocalDate leaveDate, EmploymentStatus status) {
        String employeeNo = prefix + "-" + UUID.randomUUID().toString()
                .replace("-", "").substring(0, 12).toUpperCase(Locale.ROOT);
        Person person = personRepository.saveAndFlush(new Person(employeeNo, "First", "Last"));
        assertTrue(personRepository.findByEmployeeNo(employeeNo).isPresent());
        return employmentRepository.saveAndFlush(new Employment(
                person, profile.minGrade(), status, hireDate, leaveDate, BigDecimal.ZERO, null));
    }

    private Vehicle vehicle(String prefix) {
        String registration = prefix + "-" + UUID.randomUUID().toString().replace("-", "").substring(0, 8);
        return vehicleRepository.saveAndFlush(new Vehicle(
                registration, "Make", "Model", new BigDecimal("20000.00"), 100, "D", null, "AVAILABLE"));
    }

    private DraftView saveConfirm(
            Employment employee,
            Long vehicleId,
            String choice,
            NewVehicleInput newVehicle,
            String reason,
            LocalDate startDate) throws Exception {
        MvcResult result = mockMvc.perform(put(draftPath(employee))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(confirm(choice, vehicleId, newVehicle, reason, startDate))))
                .andExpect(status().isOk())
                .andReturn();
        return objectMapper.readValue(result.getResponse().getContentAsString(), DraftView.class);
    }

    private DraftUpdateRequest confirm(
            String choice,
            Long vehicleId,
            NewVehicleInput newVehicle,
            String reason,
            LocalDate startDate) {
        return new DraftUpdateRequest(
                CarRequestStep.CONFIRM, choice, vehicleId, newVehicle, reason, startDate);
    }

    private CarRequestResult submit(Employment employee, UUID draftId, int expectedStatus) throws Exception {
        String response = mockMvc.perform(post(submitPath(employee))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(new com.otterworks.fleet.assignment.SubmitRequest(draftId))))
                .andExpect(status().is(expectedStatus))
                .andReturn().getResponse().getContentAsString();
        return objectMapper.readValue(response, CarRequestResult.class);
    }

    private MvcResult submitResponse(Employment employee, UUID draftId) throws Exception {
        return mockMvc.perform(post(submitPath(employee))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(new com.otterworks.fleet.assignment.SubmitRequest(draftId))))
                .andReturn();
    }

    private List<PoolVehicle> pool() throws Exception {
        return objectMapper.readValue(
                mockMvc.perform(get("/api/v1/assignments/pool"))
                        .andExpect(status().isOk())
                        .andReturn().getResponse().getContentAsString(),
                new TypeReference<List<PoolVehicle>>() {});
    }

    private List<DoubleHolderView> doubleHolders() throws Exception {
        return objectMapper.readValue(
                mockMvc.perform(get("/api/v1/assignments/cutover/double-holders"))
                        .andExpect(status().isOk())
                        .andReturn().getResponse().getContentAsString(),
                new TypeReference<>() {});
    }

    private void assertError(Employment employee, DraftUpdateRequest request, String code) throws Exception {
        mockMvc.perform(put(draftPath(employee)).contentType(MediaType.APPLICATION_JSON).content(json(request)))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value(code));
    }

    private String json(Object value) throws Exception {
        return objectMapper.writeValueAsString(value);
    }

    private static String draftPath(Employment employee) {
        return "/api/v1/car-requests/drafts/" + employee.getPerson().getEmployeeNo();
    }

    private static String submitPath(Employment employee) {
        return draftPath(employee) + "/submit";
    }

    private BigDecimal benefitPercent() {
        return profile.benefitPercentSource() == CountryProfile.BenefitPercentSource.VEHICLE
                ? new BigDecimal("15.00")
                : null;
    }

    @TestConfiguration
    static class FixedClockConfiguration {

        @Bean
        Clock assignmentTestClock() {
            return Clock.fixed(Instant.parse("2026-10-27T12:00:00Z"), ZoneOffset.UTC);
        }
    }
}
