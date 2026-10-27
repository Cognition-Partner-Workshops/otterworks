package com.otterworks.fleet.eligibility;

import com.otterworks.fleet.domain.Employment;
import com.otterworks.fleet.domain.Person;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.stream.Collectors;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class EmployeeSearchService {

    private final EmployeeSearchRepository searchRepository;
    private final EligibilityService eligibilityService;
    private final ObjectProvider<CurrentCarLookup> currentCarLookupProvider;

    public EmployeeSearchService(
            EmployeeSearchRepository searchRepository,
            EligibilityService eligibilityService,
            ObjectProvider<CurrentCarLookup> currentCarLookupProvider) {
        this.searchRepository = searchRepository;
        this.eligibilityService = eligibilityService;
        this.currentCarLookupProvider = currentCarLookupProvider;
    }

    @Transactional(readOnly = true)
    public List<EmployeeSummary> search(String term) {
        List<Person> people;
        if (term == null || term.isBlank()) {
            people = eligibilityService
                    .findAllEmployees(PageRequest.of(0, 50));
        } else {
            String escaped = term.toLowerCase(java.util.Locale.ROOT)
                    .replace("\\", "\\\\")
                    .replace("%", "\\%")
                    .replace("_", "\\_");
            people = searchRepository.search("%" + escaped + "%", PageRequest.of(0, 50));
        }
        Collection<Long> personIds = people.stream().map(Person::getId).toList();
        CurrentCarLookup lookup = currentCarLookupProvider.getIfAvailable(NoCurrentCarLookup::new);
        Map<Long, String> currentCars = lookup.currentRegistrations(personIds);
        return people.stream()
                .map(person -> summary(person, currentCars))
                .collect(Collectors.toList());
    }

    private EmployeeSummary summary(Person person, Map<Long, String> currentCars) {
        Employment employment = eligibilityService.currentEmployment(person).orElse(null);
        return new EmployeeSummary(
                person.getEmployeeNo(),
                person.getLastName(),
                person.getFirstName(),
                employment == null ? null : employment.getGrade(),
                employment == null ? null : employment.getStatus().name(),
                currentCars.get(person.getId()));
    }
}
