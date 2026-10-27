package com.otterworks.fleet;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.fleet.config.CountryProfile;
import com.otterworks.fleet.domain.Assignment;
import com.otterworks.fleet.domain.AssignmentRepository;
import com.otterworks.fleet.domain.Employment;
import com.otterworks.fleet.domain.EmploymentRepository;
import com.otterworks.fleet.domain.EmploymentStatus;
import com.otterworks.fleet.domain.Person;
import com.otterworks.fleet.domain.PersonRepository;
import com.otterworks.fleet.domain.Vehicle;
import com.otterworks.fleet.domain.VehicleRepository;
import com.otterworks.fleet.returns.CarReturnRepository;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;

import static org.hamcrest.Matchers.hasItem;
import static org.hamcrest.Matchers.not;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@Import(AssignmentIntegrationTest.FixedClockConfiguration.class)
@TestPropertySource(properties =
        "fleet.assignment.legacy-assignment-unload=../mainframe/unload/ASSIGNMENT.dat")
class ReturnsIntegrationTest extends AbstractPostgresIntegrationTest {

    private static final LocalDate TODAY = LocalDate.of(2026, 10, 27);
    private static final LocalDate START = LocalDate.of(2026, 3, 1);

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private CountryProfile profile;

    @Autowired
    private PersonRepository personRepository;

    @Autowired
    private EmploymentRepository employmentRepository;

    @Autowired
    private VehicleRepository vehicleRepository;

    @Autowired
    private AssignmentRepository assignmentRepository;

    @Autowired
    private CarReturnRepository carReturnRepository;

    @Test
    void GF14_returnFindsOpenAssignment() throws Exception {
        Vehicle car = vehicle("ab 12");
        Assignment open = assign(car, START);

        String messyPlate = "  " + car.getRegistration().toLowerCase(Locale.ROOT).replace(" ", "   ") + " ";
        mockMvc.perform(get("/api/v1/returns/lookup").param("plate", messyPlate))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.vehicleId").value(car.getId()))
                .andExpect(jsonPath("$.registration").value(car.getRegistration()))
                .andExpect(jsonPath("$.assignmentId").value(open.getId()))
                .andExpect(jsonPath("$.employeeNo").value(open.getEmployment().getPerson().getEmployeeNo()))
                .andExpect(jsonPath("$.startDate").value(START.toString()))
                .andExpect(jsonPath("$.distanceUnit").value(profile.distanceUnit().name()));
        mockMvc.perform(get("/api/v1/returns/lookup").param("vehicleId", car.getId().toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.assignmentId").value(open.getId()));

        submit(Map.of("plate", messyPlate, "assignmentId", open.getId(), "returnDate", TODAY.toString(),
                "odometer", 1000))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.assignmentId").value(open.getId()));

        mockMvc.perform(get("/api/v1/returns/lookup").param("vehicleId", car.getId().toString()))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("ALREADY_RETURNED"));
        submit(Map.of("vehicleId", car.getId(), "odometer", 1001))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("ALREADY_RETURNED"));

        Vehicle poolCar = vehicle("cd 34");
        mockMvc.perform(get("/api/v1/returns/lookup").param("plate", poolCar.getRegistration()))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("ALREADY_RETURNED"));
        mockMvc.perform(get("/api/v1/returns/lookup").param("plate", "NO SUCH PLATE"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("VEHICLE_NOT_FOUND"));
        mockMvc.perform(get("/api/v1/returns/lookup"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("RETURN_KEY_REQUIRED"));
        mockMvc.perform(get("/api/v1/returns/lookup")
                        .param("plate", poolCar.getRegistration())
                        .param("vehicleId", poolCar.getId().toString()))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("RETURN_KEY_REQUIRED"));
    }

    @Test
    void GF14_returnRejectsStaleAssignment() throws Exception {
        Vehicle car = vehicle("ef 56");
        Assignment open = assign(car, START);

        submit(Map.of("vehicleId", car.getId(), "assignmentId", open.getId() + 1_000_000, "odometer", 10))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("ASSIGNMENT_CHANGED"));
        assertNull(assignmentRepository.findById(open.getId()).orElseThrow().getEndDate());
    }

    @Test
    void GF15_returnBeforeStartIsRejected() throws Exception {
        Vehicle car = vehicle("gh 78");
        Assignment open = assign(car, START);

        submit(Map.of("vehicleId", car.getId(), "returnDate", START.minusDays(1).toString(), "odometer", 10))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("RETURN_DATE_BEFORE_START"));
        assertNull(assignmentRepository.findById(open.getId()).orElseThrow().getEndDate());
        assertTrue(carReturnRepository.findFirstByVehicle_IdOrderByReturnDateDescIdDesc(car.getId()).isEmpty());

        submit(Map.of("vehicleId", car.getId(), "returnDate", START.toString(), "odometer", 10))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.returnDate").value(START.toString()));

        Vehicle later = vehicle("gh 79");
        assign(later, START);
        LocalDate future = TODAY.plusDays(14);
        submit(Map.of("vehicleId", later.getId(), "returnDate", future.toString(), "odometer", 10))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.returnDate").value(future.toString()));
    }

    @Test
    void GF16_returnReleasesCar() throws Exception {
        Vehicle car = vehicle("ij 90");
        Assignment open = assign(car, START);
        mockMvc.perform(get("/api/v1/assignments/pool"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[*].id", not(hasItem(car.getId().intValue()))));

        submit(Map.of("vehicleId", car.getId(), "odometer", 2500, "conditionNote", "  scratch rear bumper "))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.returnDate").value(TODAY.toString()))
                .andExpect(jsonPath("$.conditionNote").value("scratch rear bumper"));

        assertEquals(TODAY, assignmentRepository.findById(open.getId()).orElseThrow().getEndDate());
        assertTrue(assignmentRepository.findOpenByPersonId(open.getEmployment().getPerson().getId()).isEmpty());
        assertEquals(TODAY, assignmentRepository.findLatestEndDate(car.getId()));
        mockMvc.perform(get("/api/v1/assignments/pool"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[*].id", hasItem(car.getId().intValue())));
    }

    @Test
    void GF16_returnNoteOverLimitIsRejected() throws Exception {
        Vehicle car = vehicle("ij 91");
        Assignment open = assign(car, START);

        submit(Map.of("vehicleId", car.getId(), "odometer", 10, "conditionNote", "x".repeat(201)))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("CONDITION_NOTE_TOO_LONG"));
        assertNull(assignmentRepository.findById(open.getId()).orElseThrow().getEndDate());
    }

    @Test
    void GF17_returnOdometerHandling() throws Exception {
        Vehicle car = vehicle("kl 12");
        Assignment first = assign(car, START);
        mockMvc.perform(get("/api/v1/returns/lookup").param("vehicleId", car.getId().toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.lastOdometer").doesNotExist())
                .andExpect(jsonPath("$.distanceUnit").value(profile.distanceUnit().name()));

        Map<String, Object> missing = new HashMap<>();
        missing.put("vehicleId", car.getId());
        submit(missing)
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("ODOMETER_REQUIRED"));
        submit(Map.of("vehicleId", car.getId(), "odometer", new BigDecimal("1200.5")))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("ODOMETER_NOT_WHOLE"));
        submit(Map.of("vehicleId", car.getId(), "odometer", -1))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("ODOMETER_INVALID"));
        assertNull(assignmentRepository.findById(first.getId()).orElseThrow().getEndDate());

        // First return of the car: no prior reading, so any whole number is accepted.
        submit(Map.of("vehicleId", car.getId(), "returnDate", "2026-06-30", "odometer", new BigDecimal("12000.0")))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.odometer").value(12000))
                .andExpect(jsonPath("$.distanceUnit").value(profile.distanceUnit().name()));

        Assignment second = assign(car, LocalDate.of(2026, 7, 1));
        mockMvc.perform(get("/api/v1/returns/lookup").param("vehicleId", car.getId().toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.lastOdometer").value(12000));
        submit(Map.of("vehicleId", car.getId(), "odometer", 11999))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("ODOMETER_BELOW_LAST_READING"));
        assertNull(assignmentRepository.findById(second.getId()).orElseThrow().getEndDate());
        submit(Map.of("vehicleId", car.getId(), "odometer", 12000))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.odometer").value(12000));
    }

    private ResultActions submit(Map<String, ?> body) throws Exception {
        return mockMvc.perform(post("/api/v1/returns")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(body)));
    }

    private Assignment assign(Vehicle vehicle, LocalDate start) {
        String employeeNo = "RT-" + UUID.randomUUID().toString().replace("-", "").substring(0, 12)
                .toUpperCase(Locale.ROOT);
        Person person = personRepository.saveAndFlush(new Person(employeeNo, "Return", "Tester"));
        Employment employment = employmentRepository.saveAndFlush(new Employment(
                person, profile.minGrade(), EmploymentStatus.ACTIVE, LocalDate.of(2020, 1, 1), null,
                BigDecimal.ZERO, null));
        return assignmentRepository.saveAndFlush(new Assignment(employment, vehicle, start, null, null, null));
    }

    private Vehicle vehicle(String prefix) {
        String registration = (prefix + " " + UUID.randomUUID().toString().replace("-", "").substring(0, 6))
                .toUpperCase(Locale.ROOT);
        return vehicleRepository.saveAndFlush(new Vehicle(
                registration, "Make", "Model", new BigDecimal("20000.00"), 100, "D", null, "AVAILABLE"));
    }
}
