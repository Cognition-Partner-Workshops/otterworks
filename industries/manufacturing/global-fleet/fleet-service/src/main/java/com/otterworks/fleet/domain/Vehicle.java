package com.otterworks.fleet.domain;

import jakarta.persistence.Entity;
import jakarta.persistence.Column;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;
import java.math.BigDecimal;

@Entity
@Table(name = "vehicle")
public class Vehicle {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 64)
    private String registration;

    @Column(name = "list_price", precision = 12, scale = 2)
    private BigDecimal listPrice;

    @Column(length = 64)
    private String make;

    @Column(length = 64)
    private String model;

    @Column(name = "co2_g_km")
    private Integer co2GKm;

    @JdbcTypeCode(SqlTypes.CHAR)
    @Column(columnDefinition = "char(1)", length = 1)
    private String fuel;

    @Column(name = "benefit_percent", precision = 5, scale = 2)
    private BigDecimal benefitPercent;

    @Column(length = 64)
    private String status;

    protected Vehicle() {
    }

    public Vehicle(
            String registration,
            String make,
            String model,
            BigDecimal listPrice,
            Integer co2GKm,
            String fuel,
            BigDecimal benefitPercent,
            String status) {
        this.registration = registration;
        this.make = make;
        this.model = model;
        this.listPrice = listPrice;
        this.co2GKm = co2GKm;
        this.fuel = fuel;
        this.benefitPercent = benefitPercent;
        this.status = status;
    }

    public Long getId() {
        return id;
    }

    public String getRegistration() {
        return registration;
    }

    public String getMake() {
        return make;
    }

    public String getModel() {
        return model;
    }

    public BigDecimal getListPrice() {
        return listPrice;
    }

    public Integer getCo2GKm() {
        return co2GKm;
    }

    public String getFuel() {
        return fuel;
    }

    public BigDecimal getBenefitPercent() {
        return benefitPercent;
    }
}
