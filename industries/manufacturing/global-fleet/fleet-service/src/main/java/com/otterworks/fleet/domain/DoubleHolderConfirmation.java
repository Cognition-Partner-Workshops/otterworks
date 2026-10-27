package com.otterworks.fleet.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.time.LocalDate;

@Entity
@Table(name = "double_holder_confirmation")
public class DoubleHolderConfirmation {

    @Id
    @Column(name = "employment_legacy_ref", length = 64)
    private String employmentLegacyRef;

    @Column(name = "assignment_legacy_ref", nullable = false, length = 10)
    private String assignmentLegacyRef;

    @Column(name = "confirmed_return_date", nullable = false)
    private LocalDate confirmedReturnDate;

    @Column(name = "confirmed_at", nullable = false)
    private Instant confirmedAt;

    protected DoubleHolderConfirmation() {
    }

    public DoubleHolderConfirmation(
            String employmentLegacyRef,
            String assignmentLegacyRef,
            LocalDate confirmedReturnDate,
            Instant confirmedAt) {
        this.employmentLegacyRef = employmentLegacyRef;
        this.assignmentLegacyRef = assignmentLegacyRef;
        this.confirmedReturnDate = confirmedReturnDate;
        this.confirmedAt = confirmedAt;
    }

    public String getAssignmentLegacyRef() {
        return assignmentLegacyRef;
    }

    public LocalDate getConfirmedReturnDate() {
        return confirmedReturnDate;
    }

    public Instant getConfirmedAt() {
        return confirmedAt;
    }
}
