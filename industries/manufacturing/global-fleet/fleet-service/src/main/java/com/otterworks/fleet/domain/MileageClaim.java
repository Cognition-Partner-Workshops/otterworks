package com.otterworks.fleet.domain;

import jakarta.persistence.Entity;
import jakarta.persistence.Column;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.persistence.Enumerated;
import jakarta.persistence.EnumType;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(name = "mileage_claim")
public class MileageClaim {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne
    @JoinColumn(name = "employment_id", nullable = false)
    private Employment employment;

    @ManyToOne
    @JoinColumn(name = "benefit_period_id")
    private BenefitPeriod benefitPeriod;

    @ManyToOne
    @JoinColumn(name = "vehicle_id")
    private Vehicle vehicle;

    @Column(name = "claim_date", nullable = false)
    private LocalDate claimDate;

    @Column(nullable = false)
    private Integer distance;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 64)
    private MileageClaimStatus status;

    @Column(precision = 6, scale = 3)
    private BigDecimal rate;

    @Column(precision = 10, scale = 2)
    private BigDecimal amount;

    @JdbcTypeCode(SqlTypes.CHAR)
    @Column(name = "paid_period", nullable = false, length = 6, columnDefinition = "char(6)")
    private String paidPeriod;

    @Column(length = 255)
    private String purpose;

    @Column(name = "submitted_at")
    private Instant submittedAt;

    @Column(name = "decided_at")
    private Instant decidedAt;

    public MileageClaim(
            Employment employment,
            BenefitPeriod benefitPeriod,
            Vehicle vehicle,
            LocalDate claimDate,
            Integer distance,
            MileageClaimStatus status,
            BigDecimal rate,
            BigDecimal amount,
            String paidPeriod,
            String purpose,
            Instant submittedAt) {
        this.employment = employment;
        this.benefitPeriod = benefitPeriod;
        this.vehicle = vehicle;
        this.claimDate = claimDate;
        this.distance = distance;
        this.status = status;
        this.rate = rate;
        this.amount = amount;
        this.paidPeriod = paidPeriod;
        this.purpose = purpose;
        this.submittedAt = submittedAt;
    }

    protected MileageClaim() {
    }

    public Long getId() {
        return id;
    }

    public Employment getEmployment() {
        return employment;
    }

    public BenefitPeriod getBenefitPeriod() {
        return benefitPeriod;
    }

    public Vehicle getVehicle() {
        return vehicle;
    }

    public LocalDate getClaimDate() {
        return claimDate;
    }

    public Integer getDistance() {
        return distance;
    }

    public MileageClaimStatus getStatus() {
        return status;
    }

    public BigDecimal getRate() {
        return rate;
    }

    public BigDecimal getAmount() {
        return amount;
    }

    public String getPaidPeriod() {
        return paidPeriod;
    }

    public String getPurpose() {
        return purpose;
    }

    public Instant getSubmittedAt() {
        return submittedAt;
    }

    public Instant getDecidedAt() {
        return decidedAt;
    }

    public void approve(Instant decidedAt) {
        this.status = MileageClaimStatus.APPROVED;
        this.decidedAt = decidedAt;
    }

    public void reject(Instant decidedAt) {
        this.status = MileageClaimStatus.REJECTED;
        this.decidedAt = decidedAt;
    }
}
