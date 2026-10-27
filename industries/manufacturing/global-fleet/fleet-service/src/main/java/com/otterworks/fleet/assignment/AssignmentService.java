package com.otterworks.fleet.assignment;

import com.otterworks.fleet.config.CountryProfile;
import com.otterworks.fleet.domain.Assignment;
import com.otterworks.fleet.domain.AssignmentRepository;
import com.otterworks.fleet.domain.CarRequest;
import com.otterworks.fleet.domain.CarRequestDraft;
import com.otterworks.fleet.domain.CarRequestDraftRepository;
import com.otterworks.fleet.domain.CarRequestRepository;
import com.otterworks.fleet.domain.Employment;
import com.otterworks.fleet.domain.Person;
import com.otterworks.fleet.domain.Vehicle;
import com.otterworks.fleet.domain.VehicleRepository;
import com.otterworks.fleet.eligibility.CarRequestStep;
import com.otterworks.fleet.eligibility.EligibilityDecision;
import com.otterworks.fleet.eligibility.EligibilityService;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.UUID;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AssignmentService {

    private final EligibilityService eligibilityService;
    private final CountryProfile profile;
    private final AssignmentRepository assignmentRepository;
    private final VehicleRepository vehicleRepository;
    private final CarRequestDraftRepository draftRepository;
    private final CarRequestRepository carRequestRepository;
    private final JdbcTemplate jdbc;
    private final Clock clock;
    private final ObjectProvider<OpenPeriodLookup> openPeriodLookupProvider;

    public AssignmentService(
            EligibilityService eligibilityService,
            CountryProfile profile,
            AssignmentRepository assignmentRepository,
            VehicleRepository vehicleRepository,
            CarRequestDraftRepository draftRepository,
            CarRequestRepository carRequestRepository,
            JdbcTemplate jdbc,
            ObjectProvider<Clock> clockProvider,
            ObjectProvider<OpenPeriodLookup> openPeriodLookupProvider) {
        this.eligibilityService = eligibilityService;
        this.profile = profile;
        this.assignmentRepository = assignmentRepository;
        this.vehicleRepository = vehicleRepository;
        this.draftRepository = draftRepository;
        this.carRequestRepository = carRequestRepository;
        this.jdbc = jdbc;
        this.clock = clockProvider.getIfAvailable(Clock::systemUTC);
        this.openPeriodLookupProvider = openPeriodLookupProvider;
    }

    @Transactional(readOnly = true)
    public List<PoolVehicle> pool() {
        return poolVehicles();
    }

    @Transactional(readOnly = true)
    public VehicleRulesResponse vehicleRules() {
        List<String> required = new ArrayList<>(
                List.of("plate", "make", "model", "listPrice", "co2", "fuel"));
        if (profile.benefitPercentSource() == CountryProfile.BenefitPercentSource.VEHICLE) {
            required.add("benefitPercent");
        }
        return new VehicleRulesResponse(required);
    }

    @Transactional
    public DraftView getDraft(String employeeNo) {
        Person person = eligibilityService.requireInquiry(employeeNo);
        CarRequestDraft draft = draftRepository.findByPerson_Id(person.getId())
                .orElseThrow(() -> new AssignmentException(
                        "NO_DRAFT", "No saved car request draft", HttpStatus.NOT_FOUND));
        Boolean vehicleAvailable = null;
        if ("POOL".equals(draft.getVehicleChoice()) && draft.getPoolVehicleId() != null) {
            vehicleAvailable = poolVehicles().stream()
                    .anyMatch(vehicle -> vehicle.id().equals(draft.getPoolVehicleId()));
            if (!vehicleAvailable) {
                draft.returnToVehicleChoice(clock.instant());
                draftRepository.saveAndFlush(draft);
            }
        }
        LocalDate eligibilityDate = draft.getStartDate() == null ? today() : draft.getStartDate();
        EligibilityDecision decision = eligibilityService.carRequest(
                person.getEmployeeNo(), step(draft.getStep()), eligibilityDate);
        return view(draft, person.getEmployeeNo(), decision, vehicleAvailable);
    }

    @Transactional
    public DraftView putDraft(String employeeNo, DraftUpdateRequest request) {
        if (request == null || request.step() == null) {
            throw new AssignmentException("STEP_REQUIRED");
        }
        Person person = eligibilityService.requireInquiry(employeeNo);
        LocalDate requestDate = request.startDate() == null ? today() : request.startDate();
        if (request.step() == CarRequestStep.CONFIRM) {
            validateStartDate(person.getEmployeeNo(), null, requestDate);
        } else {
            eligibilityService.requireCarRequest(person.getEmployeeNo(), request.step(), requestDate);
        }
        if (request.step() == CarRequestStep.EMPLOYEE
                && assignmentRepository.hasOpenAssignmentForPerson(person.getId())) {
            throw new AssignmentException("ALREADY_HAS_CAR");
        }

        String choice = normalizeChoice(request.vehicleChoice());
        NewVehicleInput newVehicle = normalizeNewVehicle(request.newVehicle());
        if (request.step() == CarRequestStep.VEHICLE) {
            validateVehicleChoice(choice, request.poolVehicleId(), newVehicle, false, requestDate);
        } else if (request.step() == CarRequestStep.CONFIRM) {
            validateVehicleChoice(choice, request.poolVehicleId(), newVehicle, true, requestDate);
        }
        String reason = request.reason();
        if (request.step() == CarRequestStep.CONFIRM) {
            reason = normalizeReason(reason);
            requestDate = request.startDate() == null ? today() : request.startDate();
        } else if (reason != null && !reason.isBlank()) {
            reason = normalizeReason(reason);
        }

        CarRequestDraft draft = draftRepository.findByPerson_Id(person.getId())
                .orElseGet(() -> new CarRequestDraft(UUID.randomUUID(), person, "EMPLOYEE", clock.instant()));
        draft.update(
                request.step().name(),
                choice,
                "POOL".equals(choice) ? request.poolVehicleId() : null,
                "NEW".equals(choice) && newVehicle != null ? newVehicle.plate() : null,
                "NEW".equals(choice) && newVehicle != null ? newVehicle.make() : null,
                "NEW".equals(choice) && newVehicle != null ? newVehicle.model() : null,
                "NEW".equals(choice) && newVehicle != null ? newVehicle.listPrice() : null,
                "NEW".equals(choice) && newVehicle != null ? newVehicle.co2() : null,
                "NEW".equals(choice) && newVehicle != null ? newVehicle.fuel() : null,
                "NEW".equals(choice) && newVehicle != null ? newVehicle.benefitPercent() : null,
                reason,
                request.startDate() == null && request.step() == CarRequestStep.CONFIRM
                        ? today()
                        : request.startDate(),
                clock.instant());
        draft = draftRepository.saveAndFlush(draft);
        Boolean vehicleAvailable = choice != null && "POOL".equals(choice) && request.poolVehicleId() != null
                ? true
                : null;
        return view(draft, person.getEmployeeNo(),
                eligibilityService.carRequest(person.getEmployeeNo(), request.step(), requestDate),
                vehicleAvailable);
    }

    @Transactional
    public void discardDraft(String employeeNo) {
        Person person = eligibilityService.requireInquiry(employeeNo);
        CarRequestDraft draft = draftRepository.findByPerson_Id(person.getId())
                .orElseThrow(() -> new AssignmentException(
                        "NO_DRAFT", "No saved car request draft", HttpStatus.NOT_FOUND));
        draftRepository.delete(draft);
    }

    @Transactional
    public SubmitOutcome submit(String employeeNo, UUID draftId) {
        Person person = eligibilityService.requireInquiry(employeeNo);
        Optional<CarRequest> existing = carRequestRepository.findBySubmissionKey(draftId);
        if (existing.isPresent()) {
            CarRequest request = existing.get();
            if (!request.getEmployment().getPerson().getId().equals(person.getId())) {
                throw noDraft();
            }
            return new SubmitOutcome(result(request), true);
        }

        CarRequestDraft draft = draftRepository.findByPerson_Id(person.getId())
                .orElseThrow(AssignmentService::noDraft);
        if (!draft.getId().equals(draftId)) {
            throw new AssignmentException(
                    "DRAFT_SUPERSEDED", "The saved draft has been replaced", HttpStatus.CONFLICT);
        }

        jdbc.queryForObject("SELECT id FROM person WHERE id = ? FOR UPDATE", Long.class, person.getId());
        Optional<CarRequest> replay = carRequestRepository.findBySubmissionKey(draftId);
        if (replay.isPresent()) {
            CarRequest request = replay.get();
            if (!request.getEmployment().getPerson().getId().equals(person.getId())) {
                throw noDraft();
            }
            return new SubmitOutcome(result(request), true);
        }
        draft = draftRepository.findByPerson_Id(person.getId())
                .orElseThrow(AssignmentService::noDraft);
        if (!draft.getId().equals(draftId)) {
            throw new AssignmentException(
                    "DRAFT_SUPERSEDED", "The saved draft has been replaced", HttpStatus.CONFLICT);
        }

        LocalDate startDate = draft.getStartDate() == null ? today() : draft.getStartDate();
        Employment employment = validateStartDate(person.getEmployeeNo(), null, startDate);
        if (assignmentRepository.hasOpenAssignmentForPerson(person.getId())) {
            throw new AssignmentException("ALREADY_HAS_CAR");
        }

        String reason = normalizeReason(draft.getReason());
        String choice = normalizeChoice(draft.getVehicleChoice());
        Vehicle vehicle;
        if ("POOL".equals(choice)) {
            if (draft.getPoolVehicleId() == null) {
                throw new AssignmentException("VEHICLE_REQUIRED");
            }
            vehicle = vehicleRepository.findByIdForUpdate(draft.getPoolVehicleId())
                    .orElseThrow(() -> new AssignmentException("VEHICLE_NOT_FOUND"));
            if (assignmentRepository.existsByVehicle_IdAndEndDateIsNull(vehicle.getId())) {
                throw new StalePoolVehicleException();
            }
            validateLastReturnDate(vehicle, startDate);
        } else if ("NEW".equals(choice)) {
            NewVehicleInput newVehicle = normalizeNewVehicle(new NewVehicleInput(
                    draft.getPlate(), draft.getMake(), draft.getModel(), draft.getListPrice(),
                    draft.getCo2GKm(), draft.getFuel(), draft.getBenefitPercent()));
            validateNewVehicle(newVehicle, true);
            if (vehicleRepository.existsByRegistration(newVehicle.plate())) {
                throw new AssignmentException("PLATE_ALREADY_REGISTERED");
            }
            vehicle = vehicleRepository.saveAndFlush(new Vehicle(
                    newVehicle.plate(),
                    newVehicle.make(),
                    newVehicle.model(),
                    newVehicle.listPrice(),
                    newVehicle.co2(),
                    newVehicle.fuel(),
                    newVehicle.benefitPercent(),
                    "AVAILABLE"));
        } else {
            throw new AssignmentException("VEHICLE_REQUIRED");
        }

        Assignment assignment = assignmentRepository.saveAndFlush(new Assignment(
                employment, vehicle, startDate, null, reason, null));
        CarRequest request = carRequestRepository.saveAndFlush(new CarRequest(
                employment, vehicle, assignment, today(), "DELIVERED", draftId));
        draftRepository.delete(draft);
        return new SubmitOutcome(result(request), false);
    }

    @Transactional
    public void returnDraftToVehicleChoice(String employeeNo, UUID draftId) {
        eligibilityService.findPerson(employeeNo).ifPresent(person ->
                draftRepository.findByPerson_Id(person.getId())
                        .filter(draft -> draft.getId().equals(draftId))
                        .ifPresent(draft -> {
                            draft.returnToVehicleChoice(clock.instant());
                            draftRepository.saveAndFlush(draft);
                        }));
    }

    @Transactional(readOnly = true)
    public EmployeeCarView currentCar(String employeeNo) {
        Person person = eligibilityService.requireInquiry(employeeNo);
        List<Assignment> history = assignmentRepository.findHistoryByPersonId(person.getId());
        Assignment current = history.stream().filter(item -> item.getEndDate() == null).findFirst().orElse(null);
        return new EmployeeCarView(
                person.getEmployeeNo(),
                current == null ? null : assignmentView(current),
                history.stream().map(this::assignmentView).toList());
    }

    private DraftView view(
            CarRequestDraft draft,
            String employeeNo,
            EligibilityDecision eligibility,
            Boolean vehicleAvailable) {
        NewVehicleInput newVehicle = draft.getPlate() == null
                && draft.getMake() == null
                && draft.getModel() == null
                && draft.getListPrice() == null
                && draft.getCo2GKm() == null
                && draft.getFuel() == null
                && draft.getBenefitPercent() == null
                ? null
                : new NewVehicleInput(
                        draft.getPlate(),
                        draft.getMake(),
                        draft.getModel(),
                        draft.getListPrice(),
                        draft.getCo2GKm(),
                        draft.getFuel(),
                        draft.getBenefitPercent());
        return new DraftView(
                draft.getId(),
                employeeNo,
                step(draft.getStep()),
                draft.getVehicleChoice(),
                draft.getPoolVehicleId(),
                newVehicle,
                draft.getReason(),
                draft.getStartDate(),
                eligibility,
                vehicleAvailable,
                poolVehicles());
    }

    private void validateVehicleChoice(
            String choice,
            Long poolVehicleId,
            NewVehicleInput newVehicle,
            boolean complete,
            LocalDate startDate) {
        if (choice == null) {
            if (complete) {
                throw new AssignmentException("VEHICLE_REQUIRED");
            }
            return;
        }
        if ("POOL".equals(choice)) {
            if (poolVehicleId == null) {
                if (complete) {
                    throw new AssignmentException("VEHICLE_REQUIRED");
                }
                return;
            }
            Vehicle vehicle = vehicleRepository.findById(poolVehicleId)
                    .orElseThrow(() -> new AssignmentException("VEHICLE_NOT_FOUND"));
            if (assignmentRepository.existsByVehicle_IdAndEndDateIsNull(vehicle.getId())) {
                throw new AssignmentException("VEHICLE_NOT_AVAILABLE");
            }
            if (complete) {
                validateLastReturnDate(vehicle, startDate);
            }
            return;
        }
        if ("NEW".equals(choice)) {
            validateNewVehicle(newVehicle, complete);
            return;
        }
        throw new AssignmentException("VEHICLE_CHOICE_INVALID");
    }

    private void validateNewVehicle(NewVehicleInput input, boolean complete) {
        if (input == null) {
            if (complete) {
                throw new AssignmentException("PLATE_REQUIRED");
            }
            return;
        }
        if (input.plate() == null || input.plate().isBlank()) {
            if (complete) {
                throw new AssignmentException("PLATE_REQUIRED");
            }
        } else if (input.plate().length() > 64) {
            throw new AssignmentException("PLATE_INVALID");
        }
        if (input.make() == null || input.make().isBlank()) {
            if (complete) {
                throw new AssignmentException("MAKE_REQUIRED");
            }
        } else if (input.make().length() > 64) {
            throw new AssignmentException("MAKE_INVALID");
        }
        if (input.model() == null || input.model().isBlank()) {
            if (complete) {
                throw new AssignmentException("MODEL_REQUIRED");
            }
        } else if (input.model().length() > 64) {
            throw new AssignmentException("MODEL_INVALID");
        }
        if (input.listPrice() == null) {
            if (complete) {
                throw new AssignmentException("LIST_PRICE_INVALID");
            }
        } else if (input.listPrice().compareTo(BigDecimal.ZERO) <= 0) {
            throw new AssignmentException("LIST_PRICE_INVALID");
        }
        if (input.co2() == null) {
            if (complete) {
                throw new AssignmentException("CO2_REQUIRED");
            }
        } else if (input.co2() < 0) {
            throw new AssignmentException("CO2_INVALID");
        }
        String fuel = input.fuel() == null || input.fuel().isBlank()
                ? "D"
                : input.fuel().trim().toUpperCase(Locale.ROOT);
        if (!List.of("D", "P", "H", "E").contains(fuel)) {
            throw new AssignmentException("FUEL_INVALID");
        }
        if (profile.benefitPercentSource() == CountryProfile.BenefitPercentSource.VEHICLE
                && input.benefitPercent() == null && complete) {
            throw new AssignmentException("BENEFIT_PERCENT_REQUIRED");
        }
        if (complete && input.plate() != null && !input.plate().isBlank()) {
            String plate = normalizePlate(input.plate());
            if (vehicleRepository.existsByRegistration(plate)) {
                throw new AssignmentException("PLATE_ALREADY_REGISTERED");
            }
        }
    }

    private Employment validateStartDate(String employeeNo, Employment knownEmployment, LocalDate startDate) {
        Person person = eligibilityService.requireInquiry(employeeNo);
        Employment employment = knownEmployment;
        if (employment == null) {
            employment = eligibilityService.currentEmployment(person).orElse(null);
        }
        if (employment == null
                || employment.getHireDate().isAfter(startDate)
                || (employment.getLeaveDate() != null && employment.getLeaveDate().isBefore(startDate))) {
            throw new AssignmentException("START_DATE_OUTSIDE_EMPLOYMENT");
        }
        eligibilityService.requireCarRequest(employeeNo, CarRequestStep.CONFIRM, startDate);
        OpenPeriodLookup openPeriodLookup = openPeriodLookupProvider.getIfAvailable(
                () -> new CalendarMonthOpenPeriodLookup(clock));
        if (!openPeriodLookup.isOpen(startDate)) {
            throw new AssignmentException("START_DATE_IN_CLOSED_PERIOD");
        }
        return employment;
    }

    private void validateLastReturnDate(Vehicle vehicle, LocalDate startDate) {
        LocalDate lastReturn = assignmentRepository.findLatestEndDate(vehicle.getId());
        if (lastReturn != null && !startDate.isAfter(lastReturn)) {
            throw new AssignmentException("START_DATE_BEFORE_LAST_RETURN");
        }
    }

    private String normalizeReason(String reason) {
        String normalized = reason == null || reason.isBlank()
                ? "NC"
                : reason.trim().toUpperCase(Locale.ROOT);
        if (!List.of("NC", "RP", "PL").contains(normalized)) {
            throw new AssignmentException("INVALID_REASON");
        }
        return normalized;
    }

    private static String normalizeChoice(String choice) {
        return choice == null || choice.isBlank()
                ? null
                : choice.trim().toUpperCase(Locale.ROOT);
    }

    private static NewVehicleInput normalizeNewVehicle(NewVehicleInput input) {
        if (input == null) {
            return null;
        }
        String fuel = input.fuel() == null || input.fuel().isBlank()
                ? "D"
                : input.fuel().trim().toUpperCase(Locale.ROOT);
        return new NewVehicleInput(
                input.plate() == null ? null : normalizePlate(input.plate()),
                input.make() == null ? null : input.make().trim(),
                input.model() == null ? null : input.model().trim(),
                input.listPrice(),
                input.co2(),
                fuel,
                input.benefitPercent());
    }

    public static String normalizePlate(String plate) {
        return plate.trim().replaceAll("\\s+", " ").toUpperCase(Locale.ROOT);
    }

    private LocalDate today() {
        return LocalDate.now(clock);
    }

    private List<PoolVehicle> poolVehicles() {
        return vehicleRepository.findPool().stream()
                .map(vehicle -> new PoolVehicle(
                        vehicle.getId(),
                        vehicle.getRegistration(),
                        vehicle.getMake(),
                        vehicle.getModel(),
                        vehicle.getListPrice(),
                        vehicle.getCo2GKm(),
                        vehicle.getFuel()))
                .toList();
    }

    private AssignmentView assignmentView(Assignment assignment) {
        Vehicle vehicle = assignment.getVehicle();
        return new AssignmentView(
                assignment.getId(),
                assignment.getLegacyRef(),
                vehicle.getRegistration(),
                vehicle.getMake(),
                vehicle.getModel(),
                assignment.getStartDate(),
                assignment.getEndDate(),
                assignment.getReason());
    }

    private CarRequestResult result(CarRequest request) {
        return new CarRequestResult(
                request.getId(),
                request.getAssignment().getId(),
                request.getEmployment().getPerson().getEmployeeNo(),
                request.getVehicle().getRegistration(),
                request.getAssignment().getReason(),
                request.getAssignment().getStartDate(),
                request.getStatus());
    }

    private static CarRequestStep step(String value) {
        return CarRequestStep.valueOf(value);
    }

    private static AssignmentException noDraft() {
        return new AssignmentException("NO_DRAFT", "No saved car request draft", HttpStatus.NOT_FOUND);
    }
}
