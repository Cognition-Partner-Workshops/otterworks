package com.otterworks.fleet.benefit;

import com.otterworks.fleet.config.CountryProfile;
import com.otterworks.fleet.domain.Assignment;
import com.otterworks.fleet.domain.AssignmentRepository;
import com.otterworks.fleet.domain.BenefitPeriod;
import com.otterworks.fleet.domain.BenefitPeriodRepository;
import com.otterworks.fleet.domain.BenefitPeriodStatus;
import com.otterworks.fleet.domain.Employment;
import com.otterworks.fleet.domain.EmploymentRepository;
import com.otterworks.fleet.domain.MileageClaim;
import com.otterworks.fleet.domain.MileageClaimRepository;
import com.otterworks.fleet.domain.MileageClaimStatus;
import com.otterworks.fleet.domain.Person;
import com.otterworks.fleet.domain.Vehicle;
import com.otterworks.fleet.eligibility.EligibilityService;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Collectors;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class BenefitPeriodService {

    private static final DateTimeFormatter PERIOD_FORMAT = DateTimeFormatter.ofPattern("uuuuMM");

    private final BenefitPeriodRepository periodRepository;
    private final EmploymentRepository employmentRepository;
    private final AssignmentRepository assignmentRepository;
    private final MileageClaimRepository mileageClaimRepository;
    private final BenefitResultRepository resultRepository;
    private final BenefitPayrollFileRepository payrollFileRepository;
    private final EligibilityService eligibilityService;
    private final CountryProfile profile;
    private final BenefitCalculator calculator;
    private final BenoutWriter benoutWriter;
    private final BenefitOpenPeriodLookup openPeriodLookup;
    private final Clock clock;

    public BenefitPeriodService(
            BenefitPeriodRepository periodRepository,
            EmploymentRepository employmentRepository,
            AssignmentRepository assignmentRepository,
            MileageClaimRepository mileageClaimRepository,
            BenefitResultRepository resultRepository,
            BenefitPayrollFileRepository payrollFileRepository,
            EligibilityService eligibilityService,
            CountryProfile profile,
            BenoutWriter benoutWriter,
            BenefitOpenPeriodLookup openPeriodLookup,
            ObjectProvider<Clock> clockProvider) {
        this.periodRepository = periodRepository;
        this.employmentRepository = employmentRepository;
        this.assignmentRepository = assignmentRepository;
        this.mileageClaimRepository = mileageClaimRepository;
        this.resultRepository = resultRepository;
        this.payrollFileRepository = payrollFileRepository;
        this.eligibilityService = eligibilityService;
        this.profile = profile;
        this.calculator = new BenefitCalculator();
        this.benoutWriter = benoutWriter;
        this.openPeriodLookup = openPeriodLookup;
        this.clock = clockProvider.getIfAvailable(Clock::systemUTC);
    }

    @Transactional
    public BenefitPeriodView open(YearMonth month) {
        String period = format(month);
        if (periodRepository.findByPeriod(period).isPresent()) {
            throw new BenefitException("PERIOD_EXISTS", HttpStatus.CONFLICT);
        }
        BenefitPeriod benefitPeriod = periodRepository.saveAndFlush(
                new BenefitPeriod(month, profile.mileageRate()));
        return view(benefitPeriod);
    }

    @Transactional(readOnly = true)
    public List<BenefitPeriodView> list() {
        return periodRepository.findAllByOrderByPeriodDesc().stream()
                .map(this::view)
                .toList();
    }

    @Transactional
    public BenefitPeriodView close(YearMonth month) {
        String periodKey = format(month);
        BenefitPeriod period = periodRepository.findByPeriodForUpdate(periodKey)
                .orElseThrow(() -> new BenefitException("PERIOD_NOT_FOUND", HttpStatus.NOT_FOUND));
        if (period.getStatus() == BenefitPeriodStatus.CLOSED) {
            throw new BenefitException("PERIOD_CLOSED", HttpStatus.CONFLICT);
        }

        List<Employment> employments = employmentRepository.findInRun(period.getStartDate(), period.getEndDate());
        List<Long> employmentIds = employments.stream().map(Employment::getId).toList();
        List<Assignment> assignments = employmentIds.isEmpty()
                ? List.of()
                : assignmentRepository.findOverlappingForEmployments(
                        employmentIds, period.getStartDate(), period.getEndDate());
        List<MileageClaim> claims = employmentIds.isEmpty()
                ? List.of()
                : mileageClaimRepository.findByEmployment_IdInAndPaidPeriodAndStatus(
                        employmentIds, periodKey, MileageClaimStatus.APPROVED);
        Map<Long, List<Assignment>> assignmentsByEmployment = assignments.stream()
                .collect(Collectors.groupingBy(assignment -> assignment.getEmployment().getId()));
        Map<Long, List<MileageClaim>> claimsByEmployment = claims.stream()
                .collect(Collectors.groupingBy(claim -> claim.getEmployment().getId()));
        Map<Long, Assignment> assignmentById = assignments.stream()
                .collect(Collectors.toMap(Assignment::getId, assignment -> assignment));
        Map<Long, Vehicle> vehicleById = assignments.stream()
                .map(Assignment::getVehicle)
                .collect(Collectors.toMap(Vehicle::getId, vehicle -> vehicle, (first, ignored) -> first));

        List<BenefitCalculator.Calculation> calculations = employments.stream()
                .map(employment -> calculate(
                        period.getStartDate(),
                        period.getEndDate(),
                        employment,
                        assignmentsByEmployment.getOrDefault(employment.getId(), List.of()),
                        claimsByEmployment.getOrDefault(employment.getId(), List.of())))
                .filter(BenefitCalculator.Calculation::hasOutputRecord)
                .toList();

        List<BenefitResult> results = calculations.stream()
                .map(calculation -> {
                    Employment employment = employments.stream()
                            .filter(item -> item.getId().equals(calculation.employment().employmentId()))
                            .findFirst()
                            .orElseThrow();
                    Vehicle vehicle = calculation.vehicleId() == null
                            ? null
                            : vehicleById.get(calculation.vehicleId());
                    return new BenefitResult(period, employment, calculation, vehicle, assignmentById);
                })
                .toList();
        resultRepository.saveAll(results);

        BigDecimal totalTaxable = calculations.stream()
                .map(BenefitCalculator.Calculation::taxableBenefit)
                .reduce(BigDecimal.ZERO.setScale(2), BigDecimal::add);
        BigDecimal totalMileage = calculations.stream()
                .map(BenefitCalculator.Calculation::mileageAmount)
                .reduce(BigDecimal.ZERO.setScale(2), BigDecimal::add);
        if (profile.payrollFile()) {
            payrollFileRepository.save(new BenefitPayrollFile(
                    period,
                    benoutWriter.write(periodKey, calculations),
                    clock.instant()));
        }
        period.close(results.size(), totalTaxable, totalMileage, clock.instant());
        return view(periodRepository.saveAndFlush(period));
    }

    @Transactional(readOnly = true)
    public List<BenefitInquiryView> results(YearMonth month) {
        String period = format(month);
        requirePeriod(period);
        return resultRepository.findAllForPeriod(period).stream()
                .sorted(Comparator.comparing(result -> dbkeyOrder(
                        result.getEmployment().getLegacyRef(), result.getEmployment().getId())))
                .map(result -> view(result, period, BenefitPeriodStatus.CLOSED.name()))
                .toList();
    }

    @Transactional(readOnly = true)
    public BenefitPayrollFile payrollFile(YearMonth month) {
        String period = format(month);
        if (!profile.payrollFile()) {
            throw new BenefitException("PAYROLL_FILE_DISABLED", HttpStatus.NOT_FOUND);
        }
        BenefitPeriod benefitPeriod = requirePeriod(period);
        if (benefitPeriod.getStatus() != BenefitPeriodStatus.CLOSED) {
            throw new BenefitException("PERIOD_NOT_CLOSED", HttpStatus.NOT_FOUND);
        }
        return payrollFileRepository.findByBenefitPeriod_Period(period)
                .orElseThrow(() -> new BenefitException("PAYROLL_FILE_NOT_FOUND", HttpStatus.NOT_FOUND));
    }

    @Transactional(readOnly = true)
    public BenefitInquiryView inquiry(String employeeNo, YearMonth month) {
        Person person = eligibilityService.requireInquiry(employeeNo);
        String periodKey = format(month);
        Optional<BenefitPeriod> period = periodRepository.findByPeriod(periodKey);
        if (period.isPresent() && period.get().getStatus() == BenefitPeriodStatus.CLOSED) {
            List<BenefitResult> stored = resultRepository.findAllForPeriod(periodKey);
            BenefitResult result = stored.stream()
                    .filter(candidate -> candidate.getEmployeeNo().equals(person.getEmployeeNo()))
                    .max(Comparator.comparing(candidate -> candidate.getEmployment().getId()))
                    .orElseThrow(() -> new BenefitException("BENEFIT_RESULT_NOT_FOUND", HttpStatus.NOT_FOUND));
            return view(result, periodKey, BenefitPeriodStatus.CLOSED.name());
        }
        if (period.isEmpty() && !openPeriodLookup.isOpen(month.atDay(1))) {
            throw new BenefitException("PERIOD_NOT_FOUND", HttpStatus.NOT_FOUND);
        }

        Employment employment = employmentRepository.findInRunByEmployeeNo(
                        person.getEmployeeNo(), month.atDay(1), month.atEndOfMonth())
                .stream()
                .findFirst()
                .orElse(null);
        if (employment == null) {
            return emptyView(person.getEmployeeNo(), periodKey);
        }
        List<Assignment> assignments = assignmentRepository.findOverlappingByEmployment(
                employment.getId(), month.atDay(1), month.atEndOfMonth());
        List<MileageClaim> claims = mileageClaimRepository.findByEmployment_IdInAndPaidPeriodAndStatus(
                List.of(employment.getId()), periodKey, MileageClaimStatus.APPROVED);
        return view(
                calculate(month.atDay(1), month.atEndOfMonth(), employment, assignments, claims),
                periodKey,
                BenefitPeriodStatus.OPEN.name());
    }

    @Transactional(readOnly = true)
    public BenefitStatementView statement(String employeeNo, YearMonth month) {
        Person person = eligibilityService.requireInquiry(employeeNo);
        BenefitInquiryView inquiry = inquiry(person.getEmployeeNo(), month);
        Employment employment = employmentRepository.findInRunByEmployeeNo(
                        person.getEmployeeNo(), month.atDay(1), month.atEndOfMonth())
                .stream()
                .findFirst()
                .orElseGet(() -> employmentRepository.findByPersonOrderByHireDateDescIdDesc(person)
                        .stream()
                        .findFirst()
                        .orElse(null));
        String firstName = person.getFirstName();
        String lastName = person.getLastName();
        String ruleText = ruleText();
        return new BenefitStatementView(
                inquiry.employeeNo(),
                firstName,
                lastName,
                java.util.stream.Stream.of(firstName, lastName)
                        .filter(value -> value != null && !value.isBlank())
                        .collect(Collectors.joining(" ")),
                employment == null ? 0 : employment.getCommuteDistance(),
                inquiry.period(),
                inquiry.status(),
                inquiry.lines(),
                inquiry.carDays(),
                inquiry.taxableBenefit(),
                inquiry.distance(),
                inquiry.mileageAmount(),
                inquiry.leaverFlag(),
                inquiry.currency(),
                ruleText);
    }

    private BenefitCalculator.Calculation calculate(
            LocalDate periodStart,
            LocalDate periodEnd,
            Employment employment,
            List<Assignment> assignments,
            List<MileageClaim> claims) {
        BenefitCalculator.EmploymentInput employmentInput = new BenefitCalculator.EmploymentInput(
                employment.getId(),
                employment.getPerson().getEmployeeNo(),
                employment.getLegacyRef(),
                employment.getHireDate(),
                employment.getLeaveDate(),
                employment.getMonthlyContribution(),
                employment.getCommuteDistance());
        List<BenefitCalculator.AssignmentInput> assignmentInputs = assignments.stream()
                .map(assignment -> new BenefitCalculator.AssignmentInput(
                        assignment.getId(),
                        assignment.getVehicle().getId(),
                        assignment.getVehicle().getRegistration(),
                        assignment.getStartDate(),
                        assignment.getEndDate(),
                        assignment.getVehicle().getListPrice(),
                        assignment.getVehicle().getBenefitPercent()))
                .toList();
        List<BenefitCalculator.MileageInput> mileageInputs = claims.stream()
                .map(claim -> new BenefitCalculator.MileageInput(
                        claim.getStatus(), claim.getPaidPeriod(), claim.getDistance(), claim.getAmount()))
                .toList();
        return calculator.calculate(
                profile, periodStart, periodEnd, employmentInput, assignmentInputs, mileageInputs);
    }

    private BenefitInquiryView view(
            BenefitCalculator.Calculation calculation,
            String period,
            String status) {
        List<BenefitLineView> lines = calculation.lines().stream()
                .map(line -> new BenefitLineView(
                        line.registration(),
                        line.fromDate(),
                        line.toDate(),
                        line.days(),
                        line.monthlyBenefit(),
                        line.benefit()))
                .toList();
        return new BenefitInquiryView(
                calculation.employment().employeeNo(),
                period,
                status,
                lines,
                calculation.carDays(),
                calculation.taxableBenefit(),
                calculation.distance(),
                calculation.mileageAmount(),
                calculation.leaverFlag(),
                profile.currency().getCurrencyCode());
    }

    private BenefitInquiryView view(BenefitResult result, String period, String status) {
        List<BenefitLineView> lines = result.getLines().stream()
                .map(line -> new BenefitLineView(
                        line.getVehicle().getRegistration(),
                        line.getFromDate(),
                        line.getToDate(),
                        line.getDays(),
                        line.getMonthlyBenefit(),
                        line.getBenefit()))
                .toList();
        return new BenefitInquiryView(
                result.getEmployeeNo(),
                period,
                status,
                lines,
                result.getCarDays(),
                result.getTaxableBenefit(),
                result.getDistance(),
                result.getMileageAmount(),
                result.getLeaverFlag(),
                profile.currency().getCurrencyCode());
    }

    private BenefitInquiryView emptyView(String employeeNo, String period) {
        return new BenefitInquiryView(
                employeeNo,
                period,
                BenefitPeriodStatus.OPEN.name(),
                List.of(),
                0,
                BigDecimal.ZERO.setScale(2),
                0,
                BigDecimal.ZERO.setScale(2),
                null,
                profile.currency().getCurrencyCode());
    }

    private BenefitPeriod requirePeriod(String period) {
        return periodRepository.findByPeriod(period)
                .orElseThrow(() -> new BenefitException("PERIOD_NOT_FOUND", HttpStatus.NOT_FOUND));
    }

    private BenefitPeriodView view(BenefitPeriod period) {
        return new BenefitPeriodView(
                period.getPeriod().trim(),
                period.getStartDate(),
                period.getEndDate(),
                period.getStatus().name(),
                period.getMileageRate(),
                period.getRecordCount(),
                period.getTotalTaxable(),
                period.getTotalMileage());
    }

    private String format(YearMonth month) {
        return PERIOD_FORMAT.format(month);
    }

    private String dbkeyOrder(String legacyRef, Long id) {
        if (legacyRef != null && legacyRef.matches("^MF:\\d+$")) {
            return String.format("%020d", new java.math.BigInteger(legacyRef.substring(3)));
        }
        return String.format("%020d", id);
    }

    private String ruleText() {
        String benefit = profile.benefitPercentSource() == CountryProfile.BenefitPercentSource.VEHICLE
                ? "vehicle benefit percentage annually"
                : profile.benefitPercent() + "% of list price monthly";
        String contribution = profile.employeeContribution() == CountryProfile.EmployeeContribution.EMPLOYEE
                ? "monthly employee contribution is deducted"
                : "no employee contribution is deducted";
        return "Taxable benefit uses " + benefit
                + "; commute is " + profile.commutePercentPerUnit()
                + "% per distance unit; " + contribution
                + "; rounding is " + profile.benefitRounding() + ".";
    }

    public static YearMonth parsePeriod(String value) {
        try {
            return YearMonth.parse(value, PERIOD_FORMAT);
        } catch (DateTimeParseException | NullPointerException exception) {
            throw new BenefitException("INVALID_PERIOD", HttpStatus.BAD_REQUEST);
        }
    }
}
