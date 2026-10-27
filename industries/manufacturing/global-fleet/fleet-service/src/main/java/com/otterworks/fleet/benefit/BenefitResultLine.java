package com.otterworks.fleet.benefit;

import com.otterworks.fleet.domain.Assignment;
import com.otterworks.fleet.domain.Vehicle;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.time.LocalDate;

@Entity
@Table(name = "benefit_result_line")
public class BenefitResultLine {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "benefit_result_id", nullable = false)
    private BenefitResult benefitResult;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "assignment_id", nullable = false)
    private Assignment assignment;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "vehicle_id", nullable = false)
    private Vehicle vehicle;

    @Column(name = "from_date", nullable = false)
    private LocalDate fromDate;

    @Column(name = "to_date", nullable = false)
    private LocalDate toDate;

    @Column(nullable = false)
    private int days;

    @Column(name = "monthly_benefit", nullable = false, precision = 14, scale = 4)
    private BigDecimal monthlyBenefit;

    @Column(nullable = false, precision = 12, scale = 2)
    private BigDecimal benefit;

    protected BenefitResultLine() {
    }

    BenefitResultLine(
            BenefitResult benefitResult,
            BenefitCalculator.Line calculation,
            Assignment assignment) {
        this.benefitResult = benefitResult;
        this.assignment = assignment;
        this.vehicle = assignment.getVehicle();
        this.fromDate = calculation.fromDate();
        this.toDate = calculation.toDate();
        this.days = calculation.days();
        this.monthlyBenefit = calculation.monthlyBenefit();
        this.benefit = calculation.benefit();
    }

    public Long getId() {
        return id;
    }

    public Assignment getAssignment() {
        return assignment;
    }

    public Vehicle getVehicle() {
        return vehicle;
    }

    public LocalDate getFromDate() {
        return fromDate;
    }

    public LocalDate getToDate() {
        return toDate;
    }

    public int getDays() {
        return days;
    }

    public BigDecimal getMonthlyBenefit() {
        return monthlyBenefit;
    }

    public BigDecimal getBenefit() {
        return benefit;
    }
}
