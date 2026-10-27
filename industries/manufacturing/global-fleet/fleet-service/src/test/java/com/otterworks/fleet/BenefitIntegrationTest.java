package com.otterworks.fleet;

import com.otterworks.fleet.assignment.AssignmentException;
import com.otterworks.fleet.assignment.AssignmentService;
import com.otterworks.fleet.assignment.DraftUpdateRequest;
import com.otterworks.fleet.assignment.NewVehicleInput;
import com.otterworks.fleet.benefit.BenefitException;
import com.otterworks.fleet.benefit.BenefitInquiryView;
import com.otterworks.fleet.benefit.BenefitOpenPeriodLookup;
import com.otterworks.fleet.benefit.BenefitPeriodService;
import com.otterworks.fleet.benefit.BenefitPeriodView;
import com.otterworks.fleet.benefit.BenefitResult;
import com.otterworks.fleet.benefit.BenefitResultRepository;
import com.otterworks.fleet.benefit.BenefitPayrollFile;
import com.otterworks.fleet.config.CountryProfile;
import com.otterworks.fleet.domain.Assignment;
import com.otterworks.fleet.domain.AssignmentRepository;
import com.otterworks.fleet.domain.BenefitPeriod;
import com.otterworks.fleet.domain.BenefitPeriodRepository;
import com.otterworks.fleet.domain.Employment;
import com.otterworks.fleet.domain.EmploymentRepository;
import com.otterworks.fleet.domain.EmploymentStatus;
import com.otterworks.fleet.domain.MileageClaim;
import com.otterworks.fleet.domain.MileageClaimRepository;
import com.otterworks.fleet.domain.MileageClaimStatus;
import com.otterworks.fleet.domain.Person;
import com.otterworks.fleet.domain.PersonRepository;
import com.otterworks.fleet.domain.Vehicle;
import com.otterworks.fleet.domain.VehicleRepository;
import com.otterworks.fleet.eligibility.CarRequestStep;
import com.otterworks.fleet.mileage.MileageClaimService;
import com.otterworks.fleet.mileage.MileageException;
import com.otterworks.fleet.mileage.MileageReason;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneOffset;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.atomic.AtomicLong;
import java.util.stream.IntStream;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.test.mock.mockito.SpyBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.test.web.servlet.MockMvc;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyIterable;
import static org.mockito.Mockito.doThrow;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@Import(BenefitIntegrationTest.FixedClockConfiguration.class)
class BenefitIntegrationTest extends AbstractPostgresIntegrationTest {

    private static final Instant NOW = Instant.parse("2040-01-15T12:00:00Z");
    private static final LocalDate TODAY = LocalDate.of(2040, 1, 15);
    private static final AtomicLong EMPLOYEE_SEQUENCE = new AtomicLong();
    private static final AtomicLong VEHICLE_SEQUENCE = new AtomicLong();
    private static final AtomicLong PERIOD_SEQUENCE = new AtomicLong();

    @Autowired
    private BenefitPeriodService benefitPeriodService;

    @Autowired
    private BenefitPeriodRepository benefitPeriodRepository;

    @Autowired
    private BenefitOpenPeriodLookup openPeriodLookup;

    @Autowired
    private BenefitResultRepository resultRepository;

    @Autowired
    private EmploymentRepository employmentRepository;

    @Autowired
    private PersonRepository personRepository;

    @Autowired
    private VehicleRepository vehicleRepository;

    @Autowired
    private AssignmentRepository assignmentRepository;

    @Autowired
    private MileageClaimRepository mileageClaimRepository;

    @Autowired
    private AssignmentService assignmentService;

    @Autowired
    private MileageClaimService mileageClaimService;

    @Autowired
    private CountryProfile profile;

    @Autowired
    private JdbcTemplate jdbc;

    @Autowired
    private MockMvc mockMvc;

    @SpyBean
    private BenefitResultRepository resultRepositorySpy;

    @BeforeEach
    void removePayrollFixturesOutsideBenoutEmployeeWidth() {
        jdbc.update("""
                DELETE FROM mileage_claim
                WHERE employment_id IN (
                    SELECT e.id
                    FROM employment e
                    JOIN person p ON p.id = e.person_id
                    WHERE char_length(p.employee_no) > 8
                )
                """);
        jdbc.update("""
                DELETE FROM assignment
                WHERE employment_id IN (
                    SELECT e.id
                    FROM employment e
                    JOIN person p ON p.id = e.person_id
                    WHERE char_length(p.employee_no) > 8
                )
                """);
    }

    @Test
    void GF26_benefitPeriodLifecycle() throws Exception {
        YearMonth month = YearMonth.from(TODAY);
        Employment employee = employee(profile.minGrade(), LocalDate.of(2020, 1, 1), null, BigDecimal.ZERO);
        Vehicle vehicle = vehicle();
        assignmentRepository.saveAndFlush(new Assignment(
                employee, vehicle, month.atDay(1), null, "NC", null));

        BenefitPeriodView opened = benefitPeriodService.open(month);
        assertEquals("OPEN", opened.status());
        assertTrue(openPeriodLookup.isOpen(TODAY));

        BenefitPeriodView closed = benefitPeriodService.close(month);
        assertEquals("CLOSED", closed.status());
        assertFalse(openPeriodLookup.isOpen(TODAY));

        Employment assignmentTarget = employee(
                profile.minGrade(), LocalDate.of(2020, 1, 1), null, BigDecimal.ZERO);
        AssignmentException assignmentException = assertThrows(
                AssignmentException.class,
                () -> assignmentService.putDraft(
                        assignmentTarget.getPerson().getEmployeeNo(),
                        new DraftUpdateRequest(
                                CarRequestStep.CONFIRM,
                                "NEW",
                                null,
                                new NewVehicleInput(
                                        "FUTURE-CAR",
                                        "Make",
                                        "Model",
                                        new BigDecimal("10000.00"),
                                        100,
                                        "D",
                                        new BigDecimal("12.00")),
                                "NC",
                                TODAY)));
        assertEquals("START_DATE_IN_CLOSED_PERIOD", assignmentException.getCode());
        MileageException mileageException = assertThrows(
                MileageException.class,
                () -> mileageClaimService.submit(
                        assignmentTarget.getPerson().getEmployeeNo(),
                        TODAY,
                        BigDecimal.ONE,
                        "closed benefit period"));
        assertEquals(MileageReason.NO_OPEN_CLAIM_PERIOD, mileageException.getReason());

        BenefitInquiryView beforePriceChange = benefitPeriodService.inquiry(
                employee.getPerson().getEmployeeNo(), month);
        BigDecimal storedTaxable = beforePriceChange.taxableBenefit();
        jdbc.update("UPDATE vehicle SET list_price = ? WHERE id = ?",
                new BigDecimal("99999.99"), vehicle.getId());
        BenefitInquiryView afterPriceChange = benefitPeriodService.inquiry(
                employee.getPerson().getEmployeeNo(), month);
        assertEquals(storedTaxable, afterPriceChange.taxableBenefit());
        assertEquals(beforePriceChange.lines(), afterPriceChange.lines());
        assertEquals(beforePriceChange.taxableBenefit(),
                benefitPeriodService.results(month).stream()
                        .filter(result -> result.employeeNo().equals(employee.getPerson().getEmployeeNo()))
                        .findFirst()
                        .orElseThrow()
                        .taxableBenefit());
    }

    @Test
    void GF27_inquiryShowsRunFigure() {
        YearMonth month = nextPeriod();
        Employment employee = employee(profile.minGrade(), LocalDate.of(2020, 1, 1), null, BigDecimal.ZERO);
        Vehicle vehicle = vehicle();
        assignmentRepository.saveAndFlush(new Assignment(
                employee, vehicle, month.atDay(16), null, "NC", null));

        BenefitInquiryView preview = benefitPeriodService.inquiry(
                employee.getPerson().getEmployeeNo(), month);
        assertEquals("OPEN", preview.status());
        int expectedDays = month.lengthOfMonth() - 15;
        assertEquals(expectedDays, preview.carDays());
        assertTrue(preview.taxableBenefit().compareTo(
                monthlyBenefit(vehicle).setScale(2, profile.benefitRounding())) < 0);

        benefitPeriodService.open(month);
        benefitPeriodService.close(month);
        BenefitInquiryView stored = benefitPeriodService.inquiry(
                employee.getPerson().getEmployeeNo(), month);
        assertEquals("CLOSED", stored.status());
        assertEquals(preview.carDays(), stored.carDays());
        assertEquals(preview.taxableBenefit(), stored.taxableBenefit());
        assertEquals(preview.lines(), stored.lines());
    }

    @Test
    void GF30_belowGradeHolderIsTaxedAndListed() throws Exception {
        YearMonth month = nextPeriod();
        Employment employee = employee(
                profile.minGrade() - 1, LocalDate.of(2020, 1, 1), null, BigDecimal.ZERO);
        Vehicle vehicle = vehicle();
        assignmentRepository.saveAndFlush(new Assignment(
                employee, vehicle, month.atDay(1), null, "NC", null));
        benefitPeriodService.open(month);
        benefitPeriodService.close(month);

        BenefitInquiryView result = benefitPeriodService.inquiry(
                employee.getPerson().getEmployeeNo(), month);
        assertTrue(result.carDays() > 0);
        mockMvc.perform(get("/api/v1/benefit/periods/{period}/below-grade-holders", format(month)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[?(@.employeeNo=='"
                        + employee.getPerson().getEmployeeNo() + "')]").isNotEmpty());
    }

    @Test
    void GF31_periodCloseWritesOutputAndControlTotals() {
        YearMonth month = nextPeriod();
        Employment withCar = employee(
                profile.minGrade(), LocalDate.of(2020, 1, 1), null, BigDecimal.ZERO);
        Vehicle vehicle = vehicle();
        assignmentRepository.saveAndFlush(new Assignment(
                withCar, vehicle, month.atDay(1), null, "NC", null));
        Employment mileageOnly = employee(
                profile.minGrade(), LocalDate.of(2020, 1, 1), null, BigDecimal.ZERO);
        BenefitPeriod period = benefitPeriodRepository.saveAndFlush(
                new BenefitPeriod(month, profile.mileageRate()));
        mileageClaimRepository.saveAndFlush(claim(
                withCar, period, month.atDay(2), 10, MileageClaimStatus.APPROVED, "4.44", month));
        mileageClaimRepository.saveAndFlush(claim(
                withCar, period, month.atDay(3), 20, MileageClaimStatus.PENDING, "8.88", month));
        mileageClaimRepository.saveAndFlush(claim(
                withCar, period, month.atDay(4), 30, MileageClaimStatus.REJECTED, "13.32", month));
        mileageClaimRepository.saveAndFlush(claim(
                mileageOnly, period, month.atDay(5), 5, MileageClaimStatus.APPROVED, "2.22", month));

        BenefitPeriodView closed = benefitPeriodService.close(month);
        assertEquals("CLOSED", closed.status());
        List<BenefitResult> stored = resultRepository.findAllForPeriod(format(month));
        assertEquals(closed.recordCount(), stored.size());
        assertEquals(
                stored.stream().map(BenefitResult::getTaxableBenefit)
                        .reduce(BigDecimal.ZERO.setScale(2), BigDecimal::add),
                closed.totalTaxable());
        assertEquals(
                stored.stream().map(BenefitResult::getMileageAmount)
                        .reduce(BigDecimal.ZERO.setScale(2), BigDecimal::add),
                closed.totalMileage());

        BenefitResult carResult = stored.stream()
                .filter(result -> result.getEmployeeNo().equals(withCar.getPerson().getEmployeeNo()))
                .findFirst()
                .orElseThrow();
        assertEquals(10, carResult.getDistance());
        assertEquals(new BigDecimal("4.44"), carResult.getMileageAmount());
        BenefitResult mileageResult = stored.stream()
                .filter(result -> result.getEmployeeNo().equals(mileageOnly.getPerson().getEmployeeNo()))
                .findFirst()
                .orElseThrow();
        assertEquals(0, mileageResult.getCarDays());
        assertEquals(5, mileageResult.getDistance());

        if (profile.payrollFile()) {
            BenefitPayrollFile file = benefitPeriodService.payrollFile(month);
            byte[] content = file.getContent();
            assertEquals(0, content.length % 64);
            assertEquals(stored.size(), content.length / 64);
            byte[] row = IntStream.range(0, content.length / 64)
                    .mapToObj(index -> Arrays.copyOfRange(content, index * 64, index * 64 + 64))
                    .filter(record -> text(record, 6, 8).trim().equals(withCar.getPerson().getEmployeeNo()))
                    .findFirst()
                    .orElseThrow();
            assertEquals(format(month), text(row, 0, 6));
            assertEquals(String.format("%010d", withCar.getId()), text(row, 14, 10));
            assertEquals(vehicle.getRegistration(), text(row, 24, 8).trim());
            assertEquals(Integer.parseInt(text(row, 32, 2)), carResult.getCarDays());
            assertEquals(carResult.getTaxableBenefit(), comp3(row, 34, 5));
            assertEquals(10, Integer.parseInt(text(row, 39, 6)));
            assertEquals(carResult.getMileageAmount(), comp3(row, 45, 5));
        } else {
            BenefitException disabled = assertThrows(
                    BenefitException.class, () -> benefitPeriodService.payrollFile(month));
            assertEquals("PAYROLL_FILE_DISABLED", disabled.getCode());
        }
    }

    @Test
    void GF31_failedRunChangesNothing() {
        YearMonth month = nextPeriod();
        Employment employee = employee(
                profile.minGrade(), LocalDate.of(2020, 1, 1), null, BigDecimal.ZERO);
        assignmentRepository.saveAndFlush(new Assignment(
                employee, vehicle(), month.atDay(1), null, "NC", null));
        benefitPeriodService.open(month);
        doThrow(new IllegalStateException("simulated result persistence failure"))
                .when(resultRepositorySpy)
                .saveAll(anyIterable());

        assertThrows(IllegalStateException.class, () -> benefitPeriodService.close(month));
        assertEquals("OPEN", benefitPeriodRepository.findByPeriod(format(month)).orElseThrow()
                .getStatus().name());
        assertTrue(resultRepository.findAllForPeriod(format(month)).isEmpty());
    }

    @Test
    void GF31_closedPeriodCannotBeRerun() {
        YearMonth month = nextPeriod();
        Employment employee = employee(
                profile.minGrade(), LocalDate.of(2020, 1, 1), null, BigDecimal.ZERO);
        assignmentRepository.saveAndFlush(new Assignment(
                employee, vehicle(), month.atDay(1), null, "NC", null));
        benefitPeriodService.open(month);
        BenefitPeriodView first = benefitPeriodService.close(month);
        List<BenefitInquiryView> before = benefitPeriodService.results(month);

        BenefitException exception = assertThrows(
                BenefitException.class, () -> benefitPeriodService.close(month));
        assertEquals("PERIOD_CLOSED", exception.getCode());
        assertEquals(before, benefitPeriodService.results(month));
        assertEquals(first, benefitPeriodService.list().stream()
                .filter(period -> period.period().equals(format(month)))
                .findFirst()
                .orElseThrow());
    }

    private Employment employee(
            int grade,
            LocalDate hireDate,
            LocalDate leaveDate,
            BigDecimal contribution) {
        String employeeNo = "B" + String.format("%07d", EMPLOYEE_SEQUENCE.incrementAndGet());
        Person person = personRepository.saveAndFlush(new Person(employeeNo, "Benefit", "Employee"));
        return employmentRepository.saveAndFlush(new Employment(
                person,
                grade,
                leaveDate == null ? EmploymentStatus.ACTIVE : EmploymentStatus.LEFT,
                hireDate,
                leaveDate,
                contribution,
                null,
                33));
    }

    private Vehicle vehicle() {
        String registration = "V" + String.format("%07d", VEHICLE_SEQUENCE.incrementAndGet());
        return vehicleRepository.saveAndFlush(new Vehicle(
                registration,
                "Make",
                "Model",
                new BigDecimal("10000.00"),
                100,
                "D",
                new BigDecimal("12.00"),
                "AVAILABLE"));
    }

    private MileageClaim claim(
            Employment employment,
            BenefitPeriod period,
            LocalDate date,
            int distance,
            MileageClaimStatus status,
            String amount,
            YearMonth paidPeriod) {
        return new MileageClaim(
                employment,
                period,
                null,
                date,
                distance,
                status,
                profile.mileageRate(),
                new BigDecimal(amount),
                format(paidPeriod),
                "benefit fixture",
                NOW);
    }

    private BigDecimal monthlyBenefit(Vehicle vehicle) {
        BigDecimal percentage = profile.benefitPercentSource() == CountryProfile.BenefitPercentSource.VEHICLE
                ? vehicle.getBenefitPercent()
                : profile.benefitPercent();
        int divisor = profile.benefitPercentSource() == CountryProfile.BenefitPercentSource.VEHICLE ? 1200 : 100;
        return vehicle.getListPrice().multiply(percentage)
                .divide(BigDecimal.valueOf(divisor), 12, profile.benefitRounding())
                .add(vehicle.getListPrice()
                        .multiply(profile.commutePercentPerUnit())
                        .divide(BigDecimal.valueOf(100), 12, profile.benefitRounding())
                        .multiply(BigDecimal.valueOf(33)));
    }

    private YearMonth nextPeriod() {
        return YearMonth.of(2041, 1).plusMonths(PERIOD_SEQUENCE.getAndIncrement());
    }

    private static String format(YearMonth month) {
        return String.format("%04d%02d", month.getYear(), month.getMonthValue());
    }

    private static String text(byte[] record, int offset, int width) {
        return new String(record, offset, width, StandardCharsets.US_ASCII);
    }

    private static BigDecimal comp3(byte[] record, int offset, int width) {
        StringBuilder digits = new StringBuilder();
        int sign = 1;
        for (int index = offset; index < offset + width; index++) {
            int value = record[index] & 0xff;
            int high = value >>> 4;
            int low = value & 0x0f;
            digits.append(high);
            if (index == offset + width - 1) {
                sign = low == 0x0d ? -1 : 1;
            } else {
                digits.append(low);
            }
        }
        return new BigDecimal(new BigInteger(digits.toString()).multiply(BigInteger.valueOf(sign)), 2);
    }

    @TestConfiguration
    static class FixedClockConfiguration {

        @Bean
        Clock benefitTestClock() {
            return Clock.fixed(NOW, ZoneOffset.UTC);
        }
    }

}
