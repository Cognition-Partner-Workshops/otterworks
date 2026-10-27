package com.otterworks.fleet.portal.web;

import com.otterworks.fleet.portal.model.Assignment;
import com.otterworks.fleet.portal.model.Employee;
import com.otterworks.fleet.portal.service.FleetService;
import java.io.Serializable;
import java.util.ArrayList;
import java.util.List;
import javax.faces.bean.ManagedBean;
import javax.faces.bean.RequestScoped;

@ManagedBean(name = "lookup")
@RequestScoped
public class EmployeeLookupBean implements Serializable {
    private final FleetService fleet = new FleetService();
    private String term;
    private List<Row> rows = new ArrayList<Row>();

    public static class Row implements Serializable {
        private final Employee employee;
        private final String plate;

        Row(Employee employee, String plate) {
            this.employee = employee;
            this.plate = plate;
        }

        public Employee getEmployee() { return employee; }
        public String getPlate() { return plate; }
    }

    public void load() {
        rows.clear();
        for (Employee e : fleet.searchEmployees(term)) {
            Assignment a = fleet.currentAssignment(e);
            rows.add(new Row(e, a == null ? "" : a.getVehicle().getPlate()));
        }
    }

    public String getTerm() { return term; }
    public void setTerm(String term) { this.term = term; }
    public List<Row> getRows() { return rows; }
}
