package com.otterworks.fleet.benefit;

import com.otterworks.fleet.config.CountryProfile;
import com.otterworks.fleet.domain.MileageClaimStatus;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.temporal.ChronoUnit;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;

public final class BenefitCalculator {

    public Calculation calculate(
            CountryProfile profile,
            YearMonth period,
            EmploymentInput employment,
            List<AssignmentInput> assignments,
            List<MileageInput> mileageClaims) {
        return calculate(
                profile,
                period.atDay(1),
                period.atEndOfMonth(),
                employment,
                assignments,
                mileageClaims);
    }

    public Calculation calculate(
            CountryProfile profile,
            LocalDate periodStart,
            LocalDate periodEnd,
            EmploymentInput employment,
            List<AssignmentInput> assignments,
            List<MileageInput> mileageClaims) {
        if (employment.hireDate().isAfter(periodEnd)
                || (employment.leaveDate() != null && employment.leaveDate().isBefore(periodStart))) {
            return Calculation.empty(employment, periodStart, periodEnd);
        }

        List<Line> lines = assignments.stream()
                .filter(assignment -> !assignment.startDate().isAfter(periodEnd))
                .filter(assignment -> assignment.endDate() == null || !assignment.endDate().isBefore(periodStart))
                .map(assignment -> line(profile, periodStart, periodEnd, employment, assignment, assignments))
                .filter(Objects::nonNull)
                .sorted(Comparator.comparing(Line::fromDate).thenComparingLong(Line::assignmentId))
                .toList();
        int carDays = lines.stream().mapToInt(Line::days).sum();
        BigDecimal taxable = lines.stream()
                .map(Line::benefit)
                .reduce(BigDecimal.ZERO.setScale(2), BigDecimal::add);

        String paidPeriod = String.format("%04d%02d", periodStart.getYear(), periodStart.getMonthValue());
        List<MileageInput> approvedClaims = mileageClaims.stream()
                .filter(claim -> claim.status() == MileageClaimStatus.APPROVED)
                .filter(claim -> paidPeriod.equals(claim.paidPeriod()))
                .toList();
        int distance = approvedClaims.stream().mapToInt(MileageInput::distance).sum();
        BigDecimal mileageAmount = approvedClaims.stream()
                .map(MileageInput::amount)
                .reduce(BigDecimal.ZERO.setScale(2), BigDecimal::add);
        Long vehicleId = lines.stream()
                .max(Comparator.comparing(Line::fromDate).thenComparingLong(Line::assignmentId))
                .map(Line::vehicleId)
                .orElse(null);
        String leaverFlag = employment.leaveDate() != null
                        && !employment.leaveDate().isBefore(periodStart)
                        && !employment.leaveDate().isAfter(periodEnd)
                ? "L"
                : null;
        return new Calculation(
                employment,
                lines,
                carDays,
                taxable,
                distance,
                mileageAmount,
                vehicleId,
                leaverFlag,
                periodStart,
                periodEnd);
    }

    private Line line(
            CountryProfile profile,
            LocalDate periodStart,
            LocalDate periodEnd,
            EmploymentInput employment,
            AssignmentInput assignment,
            List<AssignmentInput> assignments) {
        LocalDate from = assignment.startDate().isAfter(periodStart) ? assignment.startDate() : periodStart;
        LocalDate to = assignment.endDate() == null || assignment.endDate().isAfter(periodEnd)
                ? periodEnd
                : assignment.endDate();
        if (employment.leaveDate() != null && employment.leaveDate().isBefore(to)) {
            to = employment.leaveDate();
        }
        if (assignment.endDate() != null && assignments.stream()
                .anyMatch(other -> other.assignmentId() != assignment.assignmentId()
                        && other.startDate().equals(assignment.endDate()))) {
            LocalDate swappedEnd = assignment.endDate().minusDays(1);
            if (swappedEnd.isBefore(to)) {
                to = swappedEnd;
            }
        }
        int days = (int) ChronoUnit.DAYS.between(from, to) + 1;
        if (days <= 0) {
            return null;
        }

        BigDecimal price = zeroIfNull(assignment.listPrice());
        BigDecimal percentage = profile.benefitPercentSource() == CountryProfile.BenefitPercentSource.VEHICLE
                ? zeroIfNull(assignment.vehicleBenefitPercent())
                : zeroIfNull(profile.benefitPercent());
        int divisor = profile.benefitPercentSource() == CountryProfile.BenefitPercentSource.VEHICLE ? 1200 : 100;
        BigDecimal monthly = price.multiply(percentage)
                .divide(BigDecimal.valueOf(divisor), 12, profile.benefitRounding());
        BigDecimal commute = price.multiply(profile.commutePercentPerUnit())
                .divide(BigDecimal.valueOf(100), 12, profile.benefitRounding())
                .multiply(BigDecimal.valueOf(employment.commuteDistance()));
        monthly = monthly.add(commute);

        BigDecimal contribution = profile.employeeContribution() == CountryProfile.EmployeeContribution.EMPLOYEE
                ? zeroIfNull(employment.monthlyContribution())
                : BigDecimal.ZERO;
        long periodDays = ChronoUnit.DAYS.between(periodStart, periodEnd) + 1;
        BigDecimal taxable = monthly.subtract(contribution)
                .multiply(BigDecimal.valueOf(days))
                .max(BigDecimal.ZERO)
                .divide(BigDecimal.valueOf(periodDays), 2, profile.benefitRounding());

        return new Line(
                assignment.assignmentId(),
                assignment.vehicleId(),
                assignment.registration(),
                from,
                to,
                days,
                monthly.setScale(4, profile.benefitRounding()),
                taxable);
    }

    private BigDecimal zeroIfNull(BigDecimal value) {
        return value == null ? BigDecimal.ZERO : value;
    }

    public record EmploymentInput(
            Long employmentId,
            String employeeNo,
            String legacyRef,
            LocalDate hireDate,
            LocalDate leaveDate,
            BigDecimal monthlyContribution,
            int commuteDistance) {
    }

    public record AssignmentInput(
            Long assignmentId,
            Long vehicleId,
            String registration,
            LocalDate startDate,
            LocalDate endDate,
            BigDecimal listPrice,
            BigDecimal vehicleBenefitPercent) {
    }

    public record MileageInput(
            MileageClaimStatus status,
            String paidPeriod,
            int distance,
            BigDecimal amount) {
    }

    public record Line(
            Long assignmentId,
            Long vehicleId,
            String registration,
            LocalDate fromDate,
            LocalDate toDate,
            int days,
            BigDecimal monthlyBenefit,
            BigDecimal benefit) {
    }

    public record Calculation(
            EmploymentInput employment,
            List<Line> lines,
            int carDays,
            BigDecimal taxableBenefit,
            int distance,
            BigDecimal mileageAmount,
            Long vehicleId,
            String leaverFlag,
            LocalDate periodStart,
            LocalDate periodEnd) {

        public boolean hasOutputRecord() {
            return carDays > 0 || distance > 0;
        }

        private static Calculation empty(EmploymentInput employment, LocalDate start, LocalDate end) {
            return new Calculation(
                    employment,
                    List.of(),
                    0,
                    BigDecimal.ZERO.setScale(2),
                    0,
                    BigDecimal.ZERO.setScale(2),
                    null,
                    null,
                    start,
                    end);
        }
    }
}
