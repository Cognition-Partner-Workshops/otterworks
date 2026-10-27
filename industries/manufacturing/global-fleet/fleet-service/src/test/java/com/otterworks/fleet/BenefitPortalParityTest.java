package com.otterworks.fleet;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.fleet.benefit.BenefitCalculator;
import com.otterworks.fleet.config.CountryProfile;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.YearMonth;
import java.util.Currency;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class BenefitPortalParityTest {

    private static final Path RECORDED = Path.of("../parity/jsf/recorded.json");
    private static final Path SEED = Path.of("../seed/jsf/002_seed.sql");

    @Test
    void GF27_benefitMatchesPortalStatements() throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        JsonNode contexts = mapper.readTree(RECORDED.toFile()).path("contexts").path("statement");
        String seed = Files.readString(SEED);
        int commuteDistance = employeeCommute(seed, "E1009100");
        BigDecimal listPrice = vehiclePrice(seed, "HH-VS 7629");
        BenefitCalculator calculator = new BenefitCalculator();
        CountryProfile profile = deProfile();

        for (String contextId : List.of("statement-2026-08", "statement-2026-09")) {
            String html = statementHtml(contexts, contextId);
            BenefitCalculator.Calculation calculation = calculator.calculate(
                    profile,
                    YearMonth.parse(contextId.substring("statement-".length())),
                    new BenefitCalculator.EmploymentInput(
                            1L, "E1009100", null, LocalDate.of(2021, 8, 29), null, BigDecimal.ZERO, commuteDistance),
                    List.of(),
                    List.of());
            assertEquals(0, calculation.carDays(), contextId);
            assertTrue(html.contains("Summe geldwerter Vorteil: <b>0 EUR</b>"), contextId);
        }

        String contextId = "statement-2026-10-new-car";
        String html = statementHtml(contexts, contextId);
        Matcher row = Pattern.compile(
                "<td>\\s*(HH-VS 7629)\\s*</td>\\s*<td>\\s*(\\d+)\\s*</td>\\s*<td>\\s*([0-9.]+)\\s*</td>")
                .matcher(html);
        assertTrue(row.find(), "Recorded portal benefit row missing");
        int days = Integer.parseInt(row.group(2));
        BigDecimal expectedBenefit = new BigDecimal(row.group(3));
        YearMonth month = YearMonth.of(2026, 10);
        LocalDate assignmentStart = LocalDate.of(2026, 10, 27);
        assertEquals(days, month.lengthOfMonth() - assignmentStart.getDayOfMonth() + 1);
        BenefitCalculator.Calculation calculation = calculator.calculate(
                profile,
                month,
                new BenefitCalculator.EmploymentInput(
                        1L, "E1009100", null, LocalDate.of(2021, 8, 29), null, BigDecimal.ZERO, commuteDistance),
                List.of(new BenefitCalculator.AssignmentInput(
                        1L, 1L, row.group(1), assignmentStart, null, listPrice, null)),
                List.of());

        assertEquals(5, days);
        assertEquals(expectedBenefit, calculation.taxableBenefit());
        assertEquals(5, calculation.carDays());
        assertTrue(html.contains("Summe geldwerter Vorteil: <b>" + expectedBenefit + " EUR</b>"));
    }

    private static String statementHtml(JsonNode contexts, String id) {
        for (JsonNode context : contexts) {
            if (context.path("id").asText().equals(id)) {
                return context.path("response").path("body").asText();
            }
        }
        throw new IllegalArgumentException("Missing recorded statement context " + id);
    }

    private static int employeeCommute(String seed, String employeeNo) {
        String line = seed.lines()
                .filter(candidate -> candidate.startsWith("INSERT INTO employee")
                        && candidate.contains("'" + employeeNo + "'"))
                .findFirst()
                .orElseThrow();
        Matcher matcher = Pattern.compile(", (\\d+), '2021-08-29'").matcher(line);
        if (!matcher.find()) {
            matcher = Pattern.compile(", (\\d+), '[0-9]{4}-[0-9]{2}-[0-9]{2}', NULL, 'A'\\);")
                    .matcher(line);
        }
        if (!matcher.find(0)) {
            throw new IllegalArgumentException("Missing seeded commute distance for " + employeeNo);
        }
        return Integer.parseInt(matcher.group(1));
    }

    private static BigDecimal vehiclePrice(String seed, String registration) {
        String line = seed.lines()
                .filter(candidate -> candidate.startsWith("INSERT INTO vehicle")
                        && candidate.contains("'" + registration + "'"))
                .findFirst()
                .orElseThrow();
        Matcher matcher = Pattern.compile(Pattern.quote("'" + registration + "'")
                + ", '[^']*', '[^']*', ([0-9.]+),").matcher(line);
        if (!matcher.find()) {
            throw new IllegalArgumentException("Missing seeded vehicle price for " + registration);
        }
        return new BigDecimal(matcher.group(1));
    }

    private static CountryProfile deProfile() {
        return new CountryProfile(
                "gf-jsf-portal",
                Currency.getInstance("EUR"),
                CountryProfile.DistanceUnit.KM,
                6,
                CountryProfile.BenefitPercentSource.PROFILE,
                new BigDecimal("1.00"),
                new BigDecimal("0.030"),
                CountryProfile.EmployeeContribution.NONE,
                RoundingMode.HALF_UP,
                new BigDecimal("0.305"),
                RoundingMode.HALF_UP,
                2,
                2500,
                6,
                false);
    }
}
