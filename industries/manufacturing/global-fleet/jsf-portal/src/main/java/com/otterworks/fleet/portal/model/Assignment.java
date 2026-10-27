package com.otterworks.fleet.portal.model;

import java.io.Serializable;
import java.util.Date;
import javax.persistence.*;

@Entity
@Table(name = "assignment")
public class Assignment implements Serializable {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @ManyToOne(optional = false) @JoinColumn(name = "employee_id") private Employee employee;
    @ManyToOne(optional = false) @JoinColumn(name = "vehicle_id") private Vehicle vehicle;
    @Temporal(TemporalType.DATE) @Column(name = "start_date") private Date startDate;
    @Temporal(TemporalType.DATE) @Column(name = "end_date") private Date endDate;

    public Long getId() { return id; }
    public Employee getEmployee() { return employee; }
    public void setEmployee(Employee employee) { this.employee = employee; }
    public Vehicle getVehicle() { return vehicle; }
    public void setVehicle(Vehicle vehicle) { this.vehicle = vehicle; }
    public Date getStartDate() { return startDate; }
    public void setStartDate(Date startDate) { this.startDate = startDate; }
    public Date getEndDate() { return endDate; }
    public void setEndDate(Date endDate) { this.endDate = endDate; }
    public boolean isOpen() { return endDate == null; }
}
