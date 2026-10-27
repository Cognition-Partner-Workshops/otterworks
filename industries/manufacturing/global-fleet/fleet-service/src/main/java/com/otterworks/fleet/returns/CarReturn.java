package com.otterworks.fleet.returns;

import com.otterworks.fleet.domain.Assignment;
import com.otterworks.fleet.domain.Vehicle;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.OneToOne;
import jakarta.persistence.Table;
import java.time.LocalDate;

@Entity
@Table(name = "car_return")
public class CarReturn {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @OneToOne
    @JoinColumn(name = "assignment_id", nullable = false, unique = true)
    private Assignment assignment;

    @ManyToOne
    @JoinColumn(name = "vehicle_id", nullable = false)
    private Vehicle vehicle;

    @Column(name = "return_date", nullable = false)
    private LocalDate returnDate;

    @Column(nullable = false)
    private Integer odometer;

    @Column(name = "condition_note", length = 200)
    private String conditionNote;

    protected CarReturn() {
    }

    public CarReturn(Assignment assignment, LocalDate returnDate, Integer odometer, String conditionNote) {
        this.assignment = assignment;
        this.vehicle = assignment.getVehicle();
        this.returnDate = returnDate;
        this.odometer = odometer;
        this.conditionNote = conditionNote;
    }

    public Long getId() {
        return id;
    }

    public Assignment getAssignment() {
        return assignment;
    }

    public Vehicle getVehicle() {
        return vehicle;
    }

    public LocalDate getReturnDate() {
        return returnDate;
    }

    public Integer getOdometer() {
        return odometer;
    }

    public String getConditionNote() {
        return conditionNote;
    }
}
