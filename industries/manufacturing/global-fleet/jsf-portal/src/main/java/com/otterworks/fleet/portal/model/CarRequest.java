package com.otterworks.fleet.portal.model;

import java.io.Serializable;
import java.util.Date;
import javax.persistence.*;

@Entity
@Table(name = "car_request")
public class CarRequest implements Serializable {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @ManyToOne(optional = false) @JoinColumn(name = "employee_id") private Employee employee;
    @ManyToOne @JoinColumn(name = "vehicle_id") private Vehicle vehicle;
    @Temporal(TemporalType.DATE) @Column(name = "requested_on") private Date requestedOn;
    private String status;

    public Long getId() { return id; }
    public void setEmployee(Employee employee) { this.employee = employee; }
    public void setVehicle(Vehicle vehicle) { this.vehicle = vehicle; }
    public void setRequestedOn(Date requestedOn) { this.requestedOn = requestedOn; }
    public void setStatus(String status) { this.status = status; }
}
