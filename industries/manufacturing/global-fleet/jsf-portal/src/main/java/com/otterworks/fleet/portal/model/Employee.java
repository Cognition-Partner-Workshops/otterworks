package com.otterworks.fleet.portal.model;

import java.io.Serializable;
import java.util.Date;
import javax.persistence.*;

@Entity
@Table(name = "employee")
public class Employee implements Serializable {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @Column(name = "employee_no") private String employeeNo;
    @Column(name = "first_name") private String firstName;
    @Column(name = "last_name") private String lastName;
    private Short grade;
    @Column(name = "cost_center") private String costCenter;
    private String site;
    @Column(name = "commute_km") private Integer commuteKm;
    @Temporal(TemporalType.DATE) @Column(name = "hire_date") private Date hireDate;
    @Temporal(TemporalType.DATE) @Column(name = "leave_date") private Date leaveDate;
    @Column(columnDefinition = "bpchar") private String status;

    public Long getId() { return id; }
    public String getEmployeeNo() { return employeeNo; }
    public String getFirstName() { return firstName; }
    public String getLastName() { return lastName; }
    public String getFullName() { return firstName + " " + lastName; }
    public Short getGrade() { return grade; }
    public String getCostCenter() { return costCenter; }
    public String getSite() { return site; }
    public Integer getCommuteKm() { return commuteKm; }
    public Date getHireDate() { return hireDate; }
    public Date getLeaveDate() { return leaveDate; }
    public String getStatus() { return status; }
    public boolean isActive() { return "A".equals(status); }
}
