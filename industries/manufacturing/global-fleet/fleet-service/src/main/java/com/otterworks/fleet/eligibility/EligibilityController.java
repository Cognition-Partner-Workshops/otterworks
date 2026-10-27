package com.otterworks.fleet.eligibility;

import com.otterworks.fleet.domain.Employment;
import com.otterworks.fleet.domain.Person;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.List;
import java.util.Map;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1")
public class EligibilityController {

    private final EligibilityService eligibilityService;
    private final EmployeeSearchService employeeSearchService;
    private final ObjectProvider<CurrentCarLookup> currentCarLookupProvider;

    public EligibilityController(
            EligibilityService eligibilityService,
            EmployeeSearchService employeeSearchService,
            ObjectProvider<CurrentCarLookup> currentCarLookupProvider) {
        this.eligibilityService = eligibilityService;
        this.employeeSearchService = employeeSearchService;
        this.currentCarLookupProvider = currentCarLookupProvider;
    }

    @GetMapping("/employees")
    public List<EmployeeSummary> searchEmployees(@RequestParam(name = "q", required = false) String term) {
        return employeeSearchService.search(term);
    }

    @GetMapping("/employees/{employeeNo}")
    public EmployeeInquiry employee(@PathVariable("employeeNo") String employeeNo) {
        Person person = eligibilityService.requireInquiry(employeeNo);
        List<Employment> employments = eligibilityService.employments(person);
        Employment current = eligibilityService.currentEmployment(person).orElse(null);
        CurrentCarLookup lookup = currentCarLookupProvider.getIfAvailable(NoCurrentCarLookup::new);
        Map<Long, String> currentCars = lookup.currentRegistrations(List.of(person.getId()));
        return new EmployeeInquiry(
                person.getEmployeeNo(),
                person.getLastName(),
                person.getFirstName(),
                currentCars.get(person.getId()),
                current == null ? null : EmploymentView.from(current),
                employments.stream().map(EmploymentView::from).toList(),
                eligibilityService.carRequest(
                        person.getEmployeeNo(), CarRequestStep.EMPLOYEE, eligibilityService.today()));
    }

    @GetMapping("/eligibility/car-request")
    public EligibilityDecision carRequest(
            @RequestParam("employeeNo") String employeeNo,
            @RequestParam("step") CarRequestStep step,
            @RequestParam(name = "date", required = false)
            @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date) {
        return eligibilityService.carRequest(
                employeeNo, step, date == null ? eligibilityService.today() : date);
    }

    @GetMapping("/eligibility/mileage-claim")
    public EligibilityDecision mileageClaim(
            @RequestParam("employeeNo") String employeeNo,
            @RequestParam("claimDate")
            @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate claimDate) {
        return eligibilityService.mileageClaim(employeeNo, claimDate);
    }

    @GetMapping("/eligibility/below-grade-holders")
    public List<BelowGradeHolder> belowGradeHolders(@RequestParam("period") String period) {
        try {
            return eligibilityService.belowGradeHolders(
                    YearMonth.parse(period, DateTimeFormatter.ofPattern("uuuuMM")));
        } catch (DateTimeParseException exception) {
            throw new InvalidPeriodException();
        }
    }

}
