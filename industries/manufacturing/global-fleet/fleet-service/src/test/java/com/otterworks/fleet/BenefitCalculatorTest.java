package com.otterworks.fleet;

import com.otterworks.fleet.benefit.BenefitCalculator;
import com.otterworks.fleet.config.CountryProfile;
import com.otterworks.fleet.domain.MileageClaimStatus;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.YearMonth;
import java.util.Currency;
import java.util.List;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class BenefitCalculatorTest {

    private final BenefitCalculator calculator = new BenefitCalculator();

    @Test
    void GF27_benefitFormulaPerProfile() {
        BenefitCalculator.EmploymentInput employee = employment(
                1L, "GF27", null, new BigDecimal("0.00"), 33);
        BenefitCalculator.AssignmentInput assignment = assignment(
                1L, "CAR-1", LocalDate.of(2026, 4, 30), null);

        BenefitCalculator.Calculation uk = calculator.calculate(
                ukProfile(),
                YearMonth.of(2026, 4),
                employee,
                List.of(assignment),
                List.of());
        BenefitCalculator.Calculation de = calculator.calculate(
                deProfile(),
                YearMonth.of(2026, 4),
                employee,
                List.of(assignment),
                List.of());

        assertEquals(new BigDecimal("100.0000"), uk.lines().get(0).monthlyBenefit());
        assertEquals(new BigDecimal("199.0000"), de.lines().get(0).monthlyBenefit());
        assertEquals(new BigDecimal("3.33"), uk.taxableBenefit());
        assertEquals(new BigDecimal("6.63"), de.taxableBenefit());

        BenefitCalculator.Calculation contributed = calculator.calculate(
                ukProfile(),
                YearMonth.of(2026, 4),
                employment(1L, "GF27", null, new BigDecimal("200.00"), 0),
                List.of(assignment),
                List.of());
        assertEquals(new BigDecimal("0.00"), contributed.taxableBenefit());
    }

    @Test
    void GF28_swapDayCountsForIncomingCarOnly() {
        YearMonth period = YearMonth.of(2026, 8);
        BenefitCalculator.Calculation calculation = calculator.calculate(
                ukProfile(),
                period,
                employment(1L, "GF28", null, BigDecimal.ZERO, 0),
                List.of(
                        assignment(1L, "OUTGOING", period.atDay(1), period.atDay(15)),
                        assignment(2L, "INCOMING", period.atDay(15), null)),
                List.of());

        assertEquals(14, calculation.lines().get(0).days());
        assertEquals(17, calculation.lines().get(1).days());
        assertEquals(31, calculation.carDays());
    }

    @Test
    void GF29_everyHeldCarIsTaxed() {
        YearMonth period = YearMonth.of(2026, 9);
        BenefitCalculator.Calculation calculation = calculator.calculate(
                ukProfile(),
                period,
                employment(1L, "GF29", null, BigDecimal.ZERO, 0),
                List.of(
                        assignment(1L, "OPEN-NC", period.atDay(1), null),
                        assignment(2L, "RETURNED-PL", period.atDay(7), period.atDay(10))),
                List.of());

        assertEquals(2, calculation.lines().size());
        assertEquals(List.of(30, 4), calculation.lines().stream()
                .map(BenefitCalculator.Line::days)
                .toList());
        assertEquals(34, calculation.carDays());
        assertTrue(calculation.lines().stream().anyMatch(line -> line.registration().equals("OPEN-NC")));
    }

    @Test
    void GF30_leaverBenefitCapAndFlag() {
        YearMonth period = YearMonth.of(2026, 6);
        BenefitCalculator.Calculation leaver = calculator.calculate(
                ukProfile(),
                period,
                employment(1L, "GF30", period.atDay(10), BigDecimal.ZERO, 0),
                List.of(assignment(1L, "LEAVER", period.atDay(1), null)),
                List.of());
        BenefitCalculator.Calculation alreadyLeft = calculator.calculate(
                ukProfile(),
                period,
                employment(2L, "GF30-LEFT", period.minusMonths(1).atEndOfMonth(), BigDecimal.ZERO, 0),
                List.of(assignment(2L, "OLD-CAR", period.minusMonths(1).atDay(1), null)),
                List.of());
        BenefitCalculator.Calculation hiredDuringMonth = calculator.calculate(
                ukProfile(),
                period,
                new BenefitCalculator.EmploymentInput(
                        3L, "GF30-HIRE", null, period.atDay(10), null, BigDecimal.ZERO, 0),
                List.of(assignment(3L, "MID-MONTH", period.atDay(1), null)),
                List.of());

        assertEquals(10, leaver.carDays());
        assertEquals("L", leaver.leaverFlag());
        assertEquals(0, alreadyLeft.carDays());
        assertTrue(alreadyLeft.lines().isEmpty());
        assertEquals(period.atDay(10), hiredDuringMonth.lines().get(0).fromDate());
        assertEquals(21, hiredDuringMonth.carDays());
    }

    private BenefitCalculator.EmploymentInput employment(
            Long id,
            String employeeNo,
            LocalDate leaveDate,
            BigDecimal contribution,
            int commuteDistance) {
        return new BenefitCalculator.EmploymentInput(
                id,
                employeeNo,
                null,
                LocalDate.of(2020, 1, 1),
                leaveDate,
                contribution,
                commuteDistance);
    }

    private BenefitCalculator.AssignmentInput assignment(
            Long id,
            String registration,
            LocalDate start,
            LocalDate end) {
        return new BenefitCalculator.AssignmentInput(
                id,
                id,
                registration,
                start,
                end,
                new BigDecimal("10000.00"),
                new BigDecimal("12.00"));
    }

    private static CountryProfile ukProfile() {
        return new CountryProfile(
                "gf-mainframe-idms",
                Currency.getInstance("GBP"),
                CountryProfile.DistanceUnit.MILE,
                7,
                CountryProfile.BenefitPercentSource.VEHICLE,
                null,
                BigDecimal.ZERO,
                CountryProfile.EmployeeContribution.EMPLOYEE,
                RoundingMode.DOWN,
                new BigDecimal("0.445"),
                RoundingMode.HALF_UP,
                3,
                1500,
                6,
                true);
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
