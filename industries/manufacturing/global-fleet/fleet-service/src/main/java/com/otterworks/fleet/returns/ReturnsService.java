package com.otterworks.fleet.returns;

import com.otterworks.fleet.assignment.AssignmentService;
import com.otterworks.fleet.config.CountryProfile;
import com.otterworks.fleet.domain.Assignment;
import com.otterworks.fleet.domain.AssignmentRepository;
import com.otterworks.fleet.domain.Person;
import com.otterworks.fleet.domain.Vehicle;
import com.otterworks.fleet.domain.VehicleRepository;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.LocalDate;
import java.util.Locale;
import java.util.Objects;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ReturnsService {

    static final int CONDITION_NOTE_MAX = 200;

    private final CountryProfile profile;
    private final VehicleRepository vehicleRepository;
    private final AssignmentRepository assignmentRepository;
    private final CarReturnRepository carReturnRepository;
    private final Clock clock;

    public ReturnsService(
            CountryProfile profile,
            VehicleRepository vehicleRepository,
            AssignmentRepository assignmentRepository,
            CarReturnRepository carReturnRepository,
            ObjectProvider<Clock> clockProvider) {
        this.profile = profile;
        this.vehicleRepository = vehicleRepository;
        this.assignmentRepository = assignmentRepository;
        this.carReturnRepository = carReturnRepository;
        this.clock = clockProvider.getIfAvailable(Clock::systemUTC);
    }

    @Transactional(readOnly = true)
    public ReturnCandidate lookup(String plate, Long vehicleId) {
        Vehicle vehicle = findVehicle(plate, vehicleId);
        Assignment open = openAssignment(vehicle);
        Person person = open.getEmployment().getPerson();
        return new ReturnCandidate(
                vehicle.getId(),
                vehicle.getRegistration(),
                vehicle.getMake(),
                vehicle.getModel(),
                open.getId(),
                person.getEmployeeNo(),
                person.getFirstName(),
                person.getLastName(),
                open.getStartDate(),
                lastOdometer(vehicle.getId()),
                profile.distanceUnit());
    }

    @Transactional
    public ReturnView returnCar(ReturnRequest request) {
        Vehicle found = findVehicle(request.plate(), request.vehicleId());
        Vehicle vehicle = vehicleRepository.findByIdForUpdate(found.getId()).orElseThrow(this::vehicleNotFound);
        Assignment open = openAssignment(vehicle);
        if (request.assignmentId() != null && !Objects.equals(request.assignmentId(), open.getId())) {
            throw new ReturnException("ASSIGNMENT_CHANGED",
                    "The car's open assignment changed since it was looked up; look it up again",
                    HttpStatus.CONFLICT);
        }
        LocalDate returnDate = request.returnDate() == null ? LocalDate.now(clock) : request.returnDate();
        if (returnDate.isBefore(open.getStartDate())) {
            throw new ReturnException("RETURN_DATE_BEFORE_START",
                    "Return date " + returnDate + " is before the assignment start " + open.getStartDate(),
                    HttpStatus.UNPROCESSABLE_ENTITY);
        }
        int odometer = odometer(request.odometer(), vehicle.getId());
        String note = conditionNote(request.conditionNote());

        open.close(returnDate);
        assignmentRepository.saveAndFlush(open);
        CarReturn saved = carReturnRepository.saveAndFlush(new CarReturn(open, returnDate, odometer, note));
        return new ReturnView(
                saved.getId(),
                open.getId(),
                vehicle.getId(),
                vehicle.getRegistration(),
                open.getEmployment().getPerson().getEmployeeNo(),
                open.getStartDate(),
                returnDate,
                odometer,
                profile.distanceUnit(),
                note);
    }

    private Vehicle findVehicle(String plate, Long vehicleId) {
        boolean hasPlate = plate != null && !plate.isBlank();
        if (hasPlate == (vehicleId != null)) {
            throw new ReturnException("RETURN_KEY_REQUIRED",
                    "Give either a plate or a vehicle id", HttpStatus.BAD_REQUEST);
        }
        return (hasPlate
                ? vehicleRepository.findByRegistration(AssignmentService.normalizePlate(plate))
                : vehicleRepository.findById(vehicleId))
                .orElseThrow(this::vehicleNotFound);
    }

    private ReturnException vehicleNotFound() {
        return new ReturnException("VEHICLE_NOT_FOUND", "No car with that plate or vehicle id", HttpStatus.NOT_FOUND);
    }

    private Assignment openAssignment(Vehicle vehicle) {
        return assignmentRepository.findByVehicle_IdAndEndDateIsNull(vehicle.getId())
                .orElseThrow(() -> new ReturnException("ALREADY_RETURNED",
                        "Car " + vehicle.getRegistration() + " has no open assignment; it is already returned",
                        HttpStatus.CONFLICT));
    }

    private Integer lastOdometer(Long vehicleId) {
        return carReturnRepository.findFirstByVehicle_IdOrderByReturnDateDescIdDesc(vehicleId)
                .map(CarReturn::getOdometer)
                .orElse(null);
    }

    private int odometer(BigDecimal reading, Long vehicleId) {
        String unit = profile.distanceUnit().name().toLowerCase(Locale.ROOT);
        if (reading == null) {
            throw new ReturnException("ODOMETER_REQUIRED",
                    "An odometer reading in " + unit + " is required", HttpStatus.UNPROCESSABLE_ENTITY);
        }
        if (reading.signum() != 0 && reading.stripTrailingZeros().scale() > 0) {
            throw new ReturnException("ODOMETER_NOT_WHOLE",
                    "The odometer reading must be a whole number of " + unit, HttpStatus.UNPROCESSABLE_ENTITY);
        }
        if (reading.signum() < 0 || reading.compareTo(BigDecimal.valueOf(Integer.MAX_VALUE)) > 0) {
            throw new ReturnException("ODOMETER_INVALID",
                    "The odometer reading is out of range", HttpStatus.UNPROCESSABLE_ENTITY);
        }
        int value = reading.intValueExact();
        Integer last = lastOdometer(vehicleId);
        if (last != null && value < last) {
            throw new ReturnException("ODOMETER_BELOW_LAST_READING",
                    "The odometer reading " + value + " is below the car's last recorded reading of "
                            + last + " " + unit,
                    HttpStatus.UNPROCESSABLE_ENTITY);
        }
        return value;
    }

    private static String conditionNote(String note) {
        if (note == null || note.isBlank()) {
            return null;
        }
        String trimmed = note.trim();
        if (trimmed.length() > CONDITION_NOTE_MAX) {
            throw new ReturnException("CONDITION_NOTE_TOO_LONG",
                    "The condition note is limited to " + CONDITION_NOTE_MAX + " characters",
                    HttpStatus.UNPROCESSABLE_ENTITY);
        }
        return trimmed;
    }
}
