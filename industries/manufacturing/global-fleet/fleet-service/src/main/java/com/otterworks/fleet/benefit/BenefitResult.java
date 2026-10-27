package com.otterworks.fleet.benefit;

import com.otterworks.fleet.domain.BenefitPeriod;
import com.otterworks.fleet.domain.Assignment;
import com.otterworks.fleet.domain.Employment;
import com.otterworks.fleet.domain.Vehicle;
import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.OneToMany;
import jakarta.persistence.OrderBy;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Entity
@Table(name = "benefit_result")
public class BenefitResult {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "benefit_period_id", nullable = false)
    private BenefitPeriod benefitPeriod;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "employment_id", nullable = false)
    private Employment employment;

    @Column(name = "employee_no", nullable = false, length = 64)
    private String employeeNo;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "vehicle_id")
    private Vehicle vehicle;

    @Column(name = "car_days", nullable = false)
    private int carDays;

    @Column(name = "taxable_benefit", nullable = false, precision = 12, scale = 2)
    private BigDecimal taxableBenefit;

    @Column(nullable = false)
    private int distance;

    @Column(name = "mileage_amount", nullable = false, precision = 12, scale = 2)
    private BigDecimal mileageAmount;

    @Column(name = "leaver_flag", length = 1)
    private String leaverFlag;

    @OneToMany(mappedBy = "benefitResult", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("fromDate asc, id asc")
    private List<BenefitResultLine> lines = new ArrayList<>();

    protected BenefitResult() {
    }

    public BenefitResult(
            BenefitPeriod benefitPeriod,
            Employment employment,
            BenefitCalculator.Calculation calculation,
            Vehicle vehicle,
            Map<Long, Assignment> assignments) {
        this.benefitPeriod = benefitPeriod;
        this.employment = employment;
        this.employeeNo = employment.getPerson().getEmployeeNo();
        this.vehicle = vehicle;
        this.carDays = calculation.carDays();
        this.taxableBenefit = calculation.taxableBenefit();
        this.distance = calculation.distance();
        this.mileageAmount = calculation.mileageAmount();
        this.leaverFlag = calculation.leaverFlag();
        calculation.lines().forEach(line -> this.lines.add(
                new BenefitResultLine(this, line, assignments.get(line.assignmentId()))));
    }

    public Long getId() {
        return id;
    }

    public BenefitPeriod getBenefitPeriod() {
        return benefitPeriod;
    }

    public Employment getEmployment() {
        return employment;
    }

    public String getEmployeeNo() {
        return employeeNo;
    }

    public Vehicle getVehicle() {
        return vehicle;
    }

    public int getCarDays() {
        return carDays;
    }

    public BigDecimal getTaxableBenefit() {
        return taxableBenefit;
    }

    public int getDistance() {
        return distance;
    }

    public BigDecimal getMileageAmount() {
        return mileageAmount;
    }

    public String getLeaverFlag() {
        return leaverFlag;
    }

    public List<BenefitResultLine> getLines() {
        return lines;
    }
}
