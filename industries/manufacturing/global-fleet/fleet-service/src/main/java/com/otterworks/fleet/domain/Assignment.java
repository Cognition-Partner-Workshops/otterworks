package com.otterworks.fleet.domain;

import jakarta.persistence.Entity;
import jakarta.persistence.Column;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import java.time.LocalDate;

@Entity
@Table(name = "assignment", uniqueConstraints = {
        @UniqueConstraint(name = "assignment_legacy_ref_key", columnNames = "legacy_ref")
})
public class Assignment {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne
    @JoinColumn(name = "employment_id", nullable = false)
    private Employment employment;

    @ManyToOne
    @JoinColumn(name = "vehicle_id", nullable = false)
    private Vehicle vehicle;

    @Column(name = "start_date", nullable = false)
    private LocalDate startDate;

    @Column(name = "end_date")
    private LocalDate endDate;

    @Column(length = 2)
    private String reason;

    @Column(name = "legacy_ref", length = 10, unique = true)
    private String legacyRef;

    public Assignment(
            Employment employment,
            Vehicle vehicle,
            LocalDate startDate,
            LocalDate endDate,
            String reason,
            String legacyRef) {
        this.employment = employment;
        this.vehicle = vehicle;
        this.startDate = startDate;
        this.endDate = endDate;
        this.reason = reason;
        this.legacyRef = legacyRef;
    }

    protected Assignment() {
    }

    public Long getId() {
        return id;
    }

    public Employment getEmployment() {
        return employment;
    }

    public Vehicle getVehicle() {
        return vehicle;
    }

    public LocalDate getStartDate() {
        return startDate;
    }

    public LocalDate getEndDate() {
        return endDate;
    }

    public String getReason() {
        return reason;
    }

    public String getLegacyRef() {
        return legacyRef;
    }
}
