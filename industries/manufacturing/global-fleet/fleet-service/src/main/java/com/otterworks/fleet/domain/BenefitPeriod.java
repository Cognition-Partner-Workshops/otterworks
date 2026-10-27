package com.otterworks.fleet.domain;

import jakarta.persistence.Entity;
import jakarta.persistence.Column;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.time.YearMonth;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(name = "benefit_period")
public class BenefitPeriod {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @JdbcTypeCode(SqlTypes.CHAR)
    @Column(nullable = false, unique = true, length = 6, columnDefinition = "char(6)")
    private String period;

    @Column(name = "start_date")
    private LocalDate startDate;

    @Column(name = "end_date")
    private LocalDate endDate;

    @Column(name = "mileage_rate", precision = 6, scale = 3)
    private BigDecimal mileageRate;

    @jakarta.persistence.Enumerated(jakarta.persistence.EnumType.STRING)
    @Column(nullable = false, length = 6)
    private BenefitPeriodStatus status = BenefitPeriodStatus.OPEN;

    @Column(name = "closed_at")
    private Instant closedAt;

    @Column(name = "record_count")
    private Integer recordCount;

    @Column(name = "total_taxable", precision = 14, scale = 2)
    private BigDecimal totalTaxable;

    @Column(name = "total_mileage", precision = 14, scale = 2)
    private BigDecimal totalMileage;

    protected BenefitPeriod() {
    }

    public BenefitPeriod(YearMonth month, BigDecimal mileageRate) {
        this.period = String.format("%04d%02d", month.getYear(), month.getMonthValue());
        this.startDate = month.atDay(1);
        this.endDate = month.atEndOfMonth();
        this.mileageRate = mileageRate;
        this.status = BenefitPeriodStatus.OPEN;
    }

    public Long getId() {
        return id;
    }

    public String getPeriod() {
        return period;
    }

    public LocalDate getStartDate() {
        return startDate;
    }

    public LocalDate getEndDate() {
        return endDate;
    }

    public BigDecimal getMileageRate() {
        return mileageRate;
    }

    public BenefitPeriodStatus getStatus() {
        return status;
    }

    public Instant getClosedAt() {
        return closedAt;
    }

    public Integer getRecordCount() {
        return recordCount;
    }

    public BigDecimal getTotalTaxable() {
        return totalTaxable;
    }

    public BigDecimal getTotalMileage() {
        return totalMileage;
    }

    public void close(int recordCount, BigDecimal totalTaxable, BigDecimal totalMileage, Instant closedAt) {
        if (status == BenefitPeriodStatus.CLOSED) {
            throw new IllegalStateException("Benefit period is already closed");
        }
        this.recordCount = recordCount;
        this.totalTaxable = totalTaxable;
        this.totalMileage = totalMileage;
        this.closedAt = closedAt;
        this.status = BenefitPeriodStatus.CLOSED;
    }
}
