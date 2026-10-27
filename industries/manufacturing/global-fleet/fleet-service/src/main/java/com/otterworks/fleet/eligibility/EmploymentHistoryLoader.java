package com.otterworks.fleet.eligibility;

import com.otterworks.fleet.domain.Employment;
import com.otterworks.fleet.domain.EmploymentRepository;
import com.otterworks.fleet.domain.Person;
import com.otterworks.fleet.domain.PersonRepository;
import com.otterworks.fleet.domain.EmploymentStatus;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class EmploymentHistoryLoader {

    private final PersonRepository personRepository;
    private final EmploymentRepository employmentRepository;

    public EmploymentHistoryLoader(
            PersonRepository personRepository,
            EmploymentRepository employmentRepository) {
        this.personRepository = personRepository;
        this.employmentRepository = employmentRepository;
    }

    @Transactional
    public List<Employment> load(List<LegacyEmploymentRecord> records) {
        Map<String, List<LegacyEmploymentRecord>> byEmployee = new LinkedHashMap<>();
        for (LegacyEmploymentRecord record : records) {
            String employeeNo = EmployeeNumbers.normalize(record.employeeNo());
            if (employeeNo == null || record.legacyRef() == null || record.legacyRef().isBlank()) {
                throw new IllegalArgumentException("Employee number and legacy reference are required");
            }
            byEmployee.computeIfAbsent(employeeNo, ignored -> new ArrayList<>()).add(record);
        }

        List<Employment> loaded = new ArrayList<>();
        for (Map.Entry<String, List<LegacyEmploymentRecord>> group : byEmployee.entrySet()) {
            String employeeNo = group.getKey();
            List<LegacyEmploymentRecord> employeeRecords = group.getValue();
            LegacyEmploymentRecord newest = employeeRecords.stream()
                    .max(Comparator.comparing(LegacyEmploymentRecord::hireDate))
                    .orElseThrow();
            Person person = personRepository.findByEmployeeNo(employeeNo)
                    .orElseGet(() -> personRepository.save(
                            new Person(employeeNo, newest.firstName(), newest.lastName())));

            List<Employment> existing = employmentRepository.findByPersonOrderByHireDateAscIdAsc(person);
            LocalDate latestKnownHireDate = existing.stream()
                    .map(Employment::getHireDate)
                    .max(LocalDate::compareTo)
                    .orElse(null);
            if (latestKnownHireDate == null || !latestKnownHireDate.isAfter(newest.hireDate())) {
                person.setFirstName(newest.firstName());
                person.setLastName(newest.lastName());
            }

            for (LegacyEmploymentRecord record : employeeRecords) {
                Optional<Employment> alreadyLoaded = employmentRepository.findFirstByLegacyRef(record.legacyRef());
                if (alreadyLoaded.isPresent()) {
                    Employment employment = alreadyLoaded.get();
                    if (!employeeNo.equals(EmployeeNumbers.normalize(
                            employment.getPerson().getEmployeeNo()))) {
                        throw new IllegalStateException(
                                "legacy reference " + record.legacyRef() + " already belongs to another employee");
                    }
                    employment.setGrade(record.grade());
                    employment.setStatus(record.status());
                    employment.setHireDate(record.hireDate());
                    employment.setLeaveDate(record.leaveDate());
                    employment.setMonthlyContribution(record.monthlyContribution());
                    loaded.add(employmentRepository.save(employment));
                    continue;
                }
                Employment employment = new Employment(
                        person,
                        record.grade(),
                        record.status(),
                        record.hireDate(),
                        record.leaveDate(),
                        record.monthlyContribution(),
                        record.legacyRef());
                loaded.add(employmentRepository.save(employment));
            }
        }
        return loaded;
    }

    @Transactional(readOnly = true)
    public Optional<Employment> employmentByLegacyRef(String legacyRef) {
        return employmentRepository.findFirstByLegacyRef(legacyRef);
    }

    public record LegacyEmploymentRecord(
            String legacyRef,
            String employeeNo,
            String lastName,
            String firstName,
            Integer grade,
            EmploymentStatus status,
            LocalDate hireDate,
            LocalDate leaveDate,
            BigDecimal monthlyContribution) {
    }
}
