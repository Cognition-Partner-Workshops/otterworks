package com.otterworks.fleet.portal.model;

import java.io.Serializable;
import java.math.BigDecimal;
import javax.persistence.*;

@Entity
@Table(name = "fleet_rule")
public class FleetRule implements Serializable {
    @Id @Column(columnDefinition = "bpchar") private String country;
    @Column(name = "min_grade") private Short minGrade;
    @Column(name = "benefit_pct") private BigDecimal benefitPct;
    @Column(name = "commute_pct") private BigDecimal commutePct;
    @Column(name = "mileage_rate") private BigDecimal mileageRate;
    @Column(columnDefinition = "bpchar") private String currency;

    public String getCountry() { return country; }
    public Short getMinGrade() { return minGrade; }
    public BigDecimal getBenefitPct() { return benefitPct; }
    public BigDecimal getCommutePct() { return commutePct; }
    public BigDecimal getMileageRate() { return mileageRate; }
    public String getCurrency() { return currency; }
}
