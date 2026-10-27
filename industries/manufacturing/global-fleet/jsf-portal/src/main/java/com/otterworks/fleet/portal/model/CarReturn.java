package com.otterworks.fleet.portal.model;

import java.io.Serializable;
import java.util.Date;
import javax.persistence.*;

@Entity
@Table(name = "car_return")
public class CarReturn implements Serializable {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @ManyToOne(optional = false) @JoinColumn(name = "assignment_id") private Assignment assignment;
    @Temporal(TemporalType.DATE) @Column(name = "return_date") private Date returnDate;
    @Column(name = "odometer_km") private Integer odometerKm;
    @Column(name = "condition_note") private String conditionNote;

    public void setAssignment(Assignment assignment) { this.assignment = assignment; }
    public void setReturnDate(Date returnDate) { this.returnDate = returnDate; }
    public void setOdometerKm(Integer odometerKm) { this.odometerKm = odometerKm; }
    public void setConditionNote(String conditionNote) { this.conditionNote = conditionNote; }
}
