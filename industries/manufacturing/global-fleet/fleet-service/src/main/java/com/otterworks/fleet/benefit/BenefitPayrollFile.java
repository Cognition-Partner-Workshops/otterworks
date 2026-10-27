package com.otterworks.fleet.benefit;

import com.otterworks.fleet.domain.BenefitPeriod;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.MapsId;
import jakarta.persistence.OneToOne;
import jakarta.persistence.Table;
import java.time.Instant;

@Entity
@Table(name = "benefit_payroll_file")
public class BenefitPayrollFile {

    @Id
    @Column(name = "benefit_period_id")
    private Long id;

    @MapsId
    @OneToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "benefit_period_id", nullable = false)
    private BenefitPeriod benefitPeriod;

    @Column(nullable = false, columnDefinition = "bytea")
    private byte[] content;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    protected BenefitPayrollFile() {
    }

    public BenefitPayrollFile(BenefitPeriod benefitPeriod, byte[] content, Instant createdAt) {
        this.benefitPeriod = benefitPeriod;
        this.content = content.clone();
        this.createdAt = createdAt;
    }

    public byte[] getContent() {
        return content.clone();
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
