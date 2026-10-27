package com.otterworks.fleet.portal.web;

import com.otterworks.fleet.portal.model.Assignment;
import com.otterworks.fleet.portal.model.Employee;
import com.otterworks.fleet.portal.service.FleetService;
import java.io.Serializable;
import java.util.Collections;
import java.util.List;
import javax.faces.bean.ManagedBean;
import javax.faces.bean.RequestScoped;

@ManagedBean(name = "assignment")
@RequestScoped
public class AssignmentBean implements Serializable {
    private final FleetService fleet = new FleetService();
    private String employeeNo;
    private Employee employee;
    private Assignment current;
    private List<Assignment> history = Collections.emptyList();

    public void load() {
        if (employeeNo == null) {
            return;
        }
        employee = fleet.findEmployee(employeeNo);
        if (employee == null) {
            Faces.error("Mitarbeiter " + employeeNo + " nicht gefunden.");
            return;
        }
        history = fleet.assignments(employee);
        current = fleet.currentAssignment(employee);
    }

    public String getEmployeeNo() { return employeeNo; }
    public void setEmployeeNo(String employeeNo) { this.employeeNo = employeeNo; }
    public Employee getEmployee() { return employee; }
    public Assignment getCurrent() { return current; }
    public List<Assignment> getHistory() { return history; }
}
