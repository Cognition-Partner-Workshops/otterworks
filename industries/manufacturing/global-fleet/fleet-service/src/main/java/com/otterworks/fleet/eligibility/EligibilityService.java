package com.otterworks.fleet.eligibility;

import com.otterworks.fleet.config.CountryProfile;
import com.otterworks.fleet.domain.Employment;
import com.otterworks.fleet.domain.EmploymentRepository;
import com.otterworks.fleet.domain.EmploymentStatus;
import com.otterworks.fleet.domain.Person;
import com.otterworks.fleet.domain.PersonRepository;
import java.time.Clock;
import java.time.LocalDate;
import java.time.YearMonth;
import java.util.List;
import java.util.Optional;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class EligibilityService {

    private final PersonRepository personRepository;
    private final EmploymentRepository employmentRepository;
    private final EligibilityRepository eligibilityRepository;
    private final CountryProfile profile;
    private final Clock clock;

    public EligibilityService(
            PersonRepository personRepository,
            EmploymentRepository employmentRepository,
            EligibilityRepository eligibilityRepository,
            CountryProfile profile,
            ObjectProvider<Clock> clockProvider) {
        this.personRepository = personRepository;
        this.employmentRepository = employmentRepository;
        this.eligibilityRepository = eligibilityRepository;
        this.profile = profile;
        this.clock = clockProvider.getIfAvailable(Clock::systemUTC);
    }

    @Transactional(readOnly = true)
    public Optional<Person> findPerson(String employeeNo) {
        String normalized = EmployeeNumbers.normalize(employeeNo);
        return normalized == null ? Optional.empty() : personRepository.findByEmployeeNo(normalized);
    }

    @Transactional(readOnly = true)
    public List<Person> findAllEmployees(org.springframework.data.domain.Pageable pageable) {
        return personRepository.findAllByOrderByLastNameAscFirstNameAscEmployeeNoAsc(pageable);
    }

    @Transactional(readOnly = true)
    public Optional<Employment> currentEmployment(Person person) {
        return employmentRepository
                .findFirstByPersonAndStatusOrderByHireDateDescIdDesc(person, EmploymentStatus.ACTIVE)
                .or(() -> employmentRepository.findFirstByPersonOrderByHireDateDescIdDesc(person));
    }

    @Transactional(readOnly = true)
    public List<Employment> employments(Person person) {
        return employmentRepository.findByPersonOrderByHireDateDescIdDesc(person);
    }

    @Transactional(readOnly = true)
    public Optional<Employment> employmentOn(String employeeNo, LocalDate date) {
        if (date == null) {
            return Optional.empty();
        }
        return findPerson(employeeNo)
                .flatMap(person -> employmentRepository
                        .findCovering(person, date, PageRequest.of(0, 1))
                        .stream()
                        .findFirst());
    }

    public boolean meetsGradeThreshold(Employment employment) {
        return employment.getGrade() != null && employment.getGrade() >= profile.minGrade();
    }

    @Transactional(readOnly = true)
    public EligibilityDecision carRequest(String employeeNo, CarRequestStep step, LocalDate onDate) {
        String normalized = EmployeeNumbers.normalize(employeeNo);
        if (normalized == null) {
            return EligibilityDecision.refuse(EligibilityReason.EMPLOYEE_NUMBER_REQUIRED, null);
        }
        Optional<Person> person = personRepository.findByEmployeeNo(normalized);
        if (person.isEmpty()) {
            return EligibilityDecision.refuse(EligibilityReason.EMPLOYEE_NOT_FOUND, normalized);
        }
        Optional<Employment> current = currentEmployment(person.get());
        if (current.isEmpty()) {
            return EligibilityDecision.refuse(EligibilityReason.NOT_ACTIVE, normalized);
        }
        Employment employment = current.get();
        if (employment.getStatus() != EmploymentStatus.ACTIVE
                || (onDate != null && employment.getLeaveDate() != null
                && employment.getLeaveDate().isBefore(onDate))) {
            return EligibilityDecision.refuse(
                    EligibilityReason.NOT_ACTIVE, normalized, employment.getId());
        }
        if (!meetsGradeThreshold(employment)) {
            return EligibilityDecision.refuse(
                    EligibilityReason.GRADE_BELOW_THRESHOLD, normalized, employment.getId());
        }
        return EligibilityDecision.allow(normalized, employment.getId());
    }

    @Transactional(readOnly = true)
    public EligibilityDecision mileageClaim(String employeeNo, LocalDate claimDate) {
        String normalized = EmployeeNumbers.normalize(employeeNo);
        if (normalized == null) {
            return EligibilityDecision.refuse(EligibilityReason.EMPLOYEE_NUMBER_REQUIRED, null);
        }
        Optional<Person> person = personRepository.findByEmployeeNo(normalized);
        if (person.isEmpty()) {
            return EligibilityDecision.refuse(EligibilityReason.EMPLOYEE_NOT_FOUND, normalized);
        }
        Optional<Employment> covering = employmentRepository
                .findCovering(person.get(), claimDate, PageRequest.of(0, 1))
                .stream()
                .findFirst();
        if (covering.isEmpty()) {
            boolean claimedAfterLeaving = employmentRepository
                    .findByPersonOrderByHireDateAscIdAsc(person.get())
                    .stream()
                    .anyMatch(employment -> employment.getLeaveDate() != null
                            && claimDate != null
                            && employment.getLeaveDate().isBefore(claimDate));
            return EligibilityDecision.refuse(
                    claimedAfterLeaving
                            ? EligibilityReason.CLAIM_AFTER_LEAVING_DATE
                            : EligibilityReason.NO_EMPLOYMENT_ON_DATE,
                    normalized);
        }
        Employment employment = covering.get();
        if (employment.getStatus() == EmploymentStatus.TRANSFERRED) {
            return EligibilityDecision.refuse(
                    EligibilityReason.NOT_ACTIVE, normalized, employment.getId());
        }
        return EligibilityDecision.allow(normalized, employment.getId());
    }

    @Transactional(readOnly = true)
    public EligibilityDecision inquiry(String employeeNo) {
        String normalized = EmployeeNumbers.normalize(employeeNo);
        if (normalized == null) {
            return EligibilityDecision.refuse(EligibilityReason.EMPLOYEE_NUMBER_REQUIRED, null);
        }
        Optional<Person> person = personRepository.findByEmployeeNo(normalized);
        if (person.isEmpty()) {
            return EligibilityDecision.refuse(EligibilityReason.EMPLOYEE_NOT_FOUND, normalized);
        }
        return currentEmployment(person.get())
                .map(employment -> EligibilityDecision.allow(normalized, employment.getId()))
                .orElseGet(() -> EligibilityDecision.allow(normalized, null));
    }

    @Transactional(readOnly = true)
    public Employment requireCarRequest(String employeeNo, CarRequestStep step, LocalDate onDate) {
        EligibilityDecision decision = carRequest(employeeNo, step, onDate);
        if (!decision.allowed()) {
            throw new EligibilityException(decision.reason());
        }
        return employmentRepository.findById(decision.employmentId())
                .orElseThrow(() -> new EligibilityException(EligibilityReason.NOT_ACTIVE));
    }

    @Transactional(readOnly = true)
    public Employment requireMileageClaim(String employeeNo, LocalDate claimDate) {
        EligibilityDecision decision = mileageClaim(employeeNo, claimDate);
        if (!decision.allowed()) {
            throw new EligibilityException(decision.reason());
        }
        return employmentRepository.findById(decision.employmentId())
                .orElseThrow(() -> new EligibilityException(EligibilityReason.NO_EMPLOYMENT_ON_DATE));
    }

    @Transactional(readOnly = true)
    public Person requireInquiry(String employeeNo) {
        String normalized = EmployeeNumbers.normalize(employeeNo);
        if (normalized == null) {
            throw new EligibilityException(EligibilityReason.EMPLOYEE_NUMBER_REQUIRED);
        }
        return personRepository.findByEmployeeNo(normalized)
                .orElseThrow(() -> new EligibilityException(EligibilityReason.EMPLOYEE_NOT_FOUND));
    }

    @Transactional(readOnly = true)
    public List<BelowGradeHolder> belowGradeHolders(YearMonth period) {
        return eligibilityRepository.findBelowGradeHolders(
                period.atDay(1), period.atEndOfMonth(), profile.minGrade());
    }

    public LocalDate today() {
        return LocalDate.now(clock);
    }
}
