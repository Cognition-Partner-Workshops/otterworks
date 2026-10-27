package com.otterworks.fleet.domain;

import jakarta.persistence.Entity;
import jakarta.persistence.Column;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.util.UUID;
import java.time.LocalDate;

@Entity
@Table(name = "car_request")
public class CarRequest {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne
    @JoinColumn(name = "employment_id", nullable = false)
    private Employment employment;

    @ManyToOne
    @JoinColumn(name = "vehicle_id")
    private Vehicle vehicle;

    @ManyToOne
    @JoinColumn(name = "assignment_id", unique = true)
    private Assignment assignment;

    @Column(name = "requested_on", nullable = false)
    private LocalDate requestedOn;

    @Column(length = 64)
    private String status;

    @Column(name = "submission_key", unique = true)
    private UUID submissionKey;

    public CarRequest(
            Employment employment,
            Vehicle vehicle,
            Assignment assignment,
            LocalDate requestedOn,
            String status,
            UUID submissionKey) {
        this.employment = employment;
        this.vehicle = vehicle;
        this.assignment = assignment;
        this.requestedOn = requestedOn;
        this.status = status;
        this.submissionKey = submissionKey;
    }

    protected CarRequest() {
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

    public Assignment getAssignment() {
        return assignment;
    }

    public LocalDate getRequestedOn() {
        return requestedOn;
    }

    public String getStatus() {
        return status;
    }

    public UUID getSubmissionKey() {
        return submissionKey;
    }
}
