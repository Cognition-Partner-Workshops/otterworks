package com.otterworks.fleet;

import com.otterworks.fleet.config.CountryProfile;
import com.otterworks.fleet.domain.Employment;
import com.otterworks.fleet.domain.EmploymentRepository;
import com.otterworks.fleet.domain.EmploymentStatus;
import com.otterworks.fleet.domain.Person;
import com.otterworks.fleet.domain.PersonRepository;
import com.otterworks.fleet.eligibility.CurrentCarLookup;
import com.otterworks.fleet.eligibility.EmployeeSearchService;
import com.otterworks.fleet.eligibility.EmployeeSummary;
import java.time.LocalDate;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyCollection;
import static org.mockito.Mockito.clearInvocations;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.hamcrest.Matchers.hasSize;

@SpringBootTest
@AutoConfigureMockMvc
class EmployeeSearchIntegrationTest extends AbstractPostgresIntegrationTest {

    @Autowired
    private PersonRepository personRepository;

    @Autowired
    private EmploymentRepository employmentRepository;

    @Autowired
    private EmployeeSearchService employeeSearchService;

    @Autowired
    private CountryProfile profile;

    @Autowired
    private JdbcTemplate jdbc;

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private CurrentCarLookup currentCarLookup;

    @Test
    void GF33_employeeSearch() throws Exception {
        String token = UUID.randomUUID().toString().replace("-", "");
        for (int index = 0; index < 55; index++) {
            Person person = person(
                    "GF33-" + token.substring(0, 8).toUpperCase() + "-" + index,
                    "First" + index,
                    "mIxEd-" + token + "-" + String.format("%02d", index));
            employmentRepository.save(new Employment(
                    person, profile.minGrade(), EmploymentStatus.ACTIVE,
                    LocalDate.of(2020, 1, 1), null, null, null));
        }
        String firstMatchNo = "GF33-FIRST-" + token.substring(0, 8).toUpperCase();
        Person firstMatch = person(firstMatchNo, "Needle-" + token, "FirstMatch");
        employmentRepository.save(new Employment(
                firstMatch, profile.minGrade(), EmploymentStatus.ACTIVE,
                LocalDate.of(2020, 1, 1), null, null, null));
        String numberMatchNo = "GF33-NUMBERNEEDLE-" + token.substring(0, 8).toUpperCase();
        Person numberMatch = person(numberMatchNo, "Number", "Match");

        Person literalPercent = person(
                "GF33-PERCENT-" + token.substring(0, 8).toUpperCase(), "Literal%Token", "PercentMatch");

        when(currentCarLookup.currentRegistrations(anyCollection())).thenAnswer(invocation -> {
            Collection<Long> ids = invocation.getArgument(0);
            return ids.stream().collect(java.util.stream.Collectors.toMap(id -> id, id -> "REG-" + id));
        });
        clearInvocations(currentCarLookup);

        List<EmployeeSummary> lastNameMatches = employeeSearchService.search("MIXED-" + token);
        assertEquals(50, lastNameMatches.size());
        assertTrue(lastNameMatches.stream()
                .allMatch(summary -> summary.lastName().toLowerCase().contains(token.toLowerCase())));
        assertEquals(lastNameMatches.stream()
                        .sorted(java.util.Comparator.comparing(EmployeeSummary::lastName)
                                .thenComparing(EmployeeSummary::firstName)
                                .thenComparing(EmployeeSummary::employeeNo))
                        .toList(),
                lastNameMatches);
        assertTrue(lastNameMatches.get(0).currentCar().startsWith("REG-"));
        verify(currentCarLookup, times(1)).currentRegistrations(anyCollection());

        assertEquals(firstMatch.getEmployeeNo(),
                employeeSearchService.search(("NEEDLE-" + token).toLowerCase()).get(0).employeeNo());
        assertEquals(numberMatch.getEmployeeNo(),
                employeeSearchService.search(("NUMBERNEEDLE-" + token.substring(0, 8)).toLowerCase())
                        .get(0).employeeNo());
        List<EmployeeSummary> literalMatches = employeeSearchService.search("%");
        assertEquals(1, literalMatches.size());
        assertEquals(literalPercent.getEmployeeNo(), literalMatches.get(0).employeeNo());

        mockMvc.perform(get("/api/v1/employees").param("q", ""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(50)));
    }

    private Person person(String employeeNo, String firstName, String lastName) {
        return personRepository.save(new Person(employeeNo, firstName, lastName));
    }
}
