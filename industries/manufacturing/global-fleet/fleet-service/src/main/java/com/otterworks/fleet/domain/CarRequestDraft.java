package com.otterworks.fleet.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.persistence.Version;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

@Entity
@Table(name = "car_request_draft")
public class CarRequestDraft {

    @Id
    private UUID id;

    @ManyToOne
    @JoinColumn(name = "person_id", nullable = false, unique = true)
    private Person person;

    @Column(nullable = false, length = 16)
    private String step;

    @Column(name = "vehicle_choice", length = 8)
    private String vehicleChoice;

    @Column(name = "pool_vehicle_id")
    private Long poolVehicleId;

    @Column(length = 64)
    private String plate;

    @Column(length = 64)
    private String make;

    @Column(length = 64)
    private String model;

    @Column(name = "list_price", precision = 12, scale = 2)
    private BigDecimal listPrice;

    @Column(name = "co2_g_km")
    private Integer co2GKm;

    @JdbcTypeCode(SqlTypes.CHAR)
    @Column(length = 1, columnDefinition = "char(1)")
    private String fuel;

    @Column(name = "benefit_percent", precision = 5, scale = 2)
    private BigDecimal benefitPercent;

    @JdbcTypeCode(SqlTypes.CHAR)
    @Column(length = 2, columnDefinition = "char(2)")
    private String reason;

    @Column(name = "start_date")
    private LocalDate startDate;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @Version
    @Column(nullable = false)
    private Long version;

    protected CarRequestDraft() {
    }

    public CarRequestDraft(UUID id, Person person, String step, Instant now) {
        this.id = id;
        this.person = person;
        this.step = step;
        this.createdAt = now;
        this.updatedAt = now;
    }

    public UUID getId() {
        return id;
    }

    public Person getPerson() {
        return person;
    }

    public String getStep() {
        return step;
    }

    public String getVehicleChoice() {
        return vehicleChoice;
    }

    public Long getPoolVehicleId() {
        return poolVehicleId;
    }

    public String getPlate() {
        return plate;
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

    public String getReason() {
        return reason;
    }

    public LocalDate getStartDate() {
        return startDate;
    }

    public void update(
            String step,
            String vehicleChoice,
            Long poolVehicleId,
            String plate,
            String make,
            String model,
            BigDecimal listPrice,
            Integer co2GKm,
            String fuel,
            BigDecimal benefitPercent,
            String reason,
            LocalDate startDate,
            Instant now) {
        this.step = step;
        this.vehicleChoice = vehicleChoice;
        this.poolVehicleId = poolVehicleId;
        this.plate = plate;
        this.make = make;
        this.model = model;
        this.listPrice = listPrice;
        this.co2GKm = co2GKm;
        this.fuel = fuel;
        this.benefitPercent = benefitPercent;
        this.reason = reason;
        this.startDate = startDate;
        this.updatedAt = now;
    }

    public void returnToVehicleChoice(Instant now) {
        this.step = "VEHICLE";
        this.poolVehicleId = null;
        this.updatedAt = now;
    }
}
