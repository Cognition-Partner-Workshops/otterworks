package com.otterworks.fleet.portal.web;

import com.otterworks.fleet.portal.model.Employee;
import com.otterworks.fleet.portal.model.FleetRule;
import com.otterworks.fleet.portal.model.Vehicle;
import com.otterworks.fleet.portal.service.FleetService;
import java.io.Serializable;
import java.math.BigDecimal;
import java.util.Date;
import java.util.List;
import javax.faces.bean.ManagedBean;
import javax.faces.bean.ViewScoped;

@ManagedBean(name = "wizard")
@ViewScoped
public class CarRequestWizard implements Serializable {
    private final FleetService fleet = new FleetService();
    private int step = 1;
    private String employeeNo;
    private Employee employee;
    private String choice = "pool";
    private Long vehicleId;
    private String plate;
    private String make;
    private String model;
    private BigDecimal listPrice;
    private Integer co2;
    private String fuel = "D";
    private Date startDate = new Date();
    private List<Vehicle> available;

    public void checkEmployee() {
        employee = fleet.findEmployee(employeeNo == null ? null : employeeNo.trim().toUpperCase());
        if (employee == null || !employee.isActive()) {
            Faces.error("Mitarbeiter nicht gefunden oder nicht aktiv.");
            return;
        }
        FleetRule rule = fleet.rule();
        if (employee.getGrade() < rule.getMinGrade()) {
            Faces.error("Entgeltgruppe " + employee.getGrade() + " ist nicht dienstwagenberechtigt.");
            return;
        }
        if (fleet.currentAssignment(employee) != null) {
            Faces.error("Mitarbeiter hat bereits einen Dienstwagen.");
            return;
        }
        available = fleet.availableVehicles();
        step = 2;
    }

    public void chooseVehicle() {
        if ("pool".equals(choice) && vehicleId == null) {
            Faces.error("Bitte ein Fahrzeug aus dem Pool waehlen.");
            return;
        }
        if ("new".equals(choice) && (plate == null || make == null || model == null || listPrice == null || co2 == null)) {
            Faces.error("Bitte Kennzeichen, Marke, Modell, Listenpreis und CO2 angeben.");
            return;
        }
        step = 3;
    }

    public String submit() {
        Vehicle existing = null;
        Vehicle registered = null;
        if ("pool".equals(choice)) {
            for (Vehicle v : available) {
                if (v.getId().equals(vehicleId)) {
                    existing = v;
                }
            }
        } else {
            registered = new Vehicle();
            registered.setPlate(plate);
            registered.setMake(make);
            registered.setModel(model);
            registered.setListPrice(listPrice);
            registered.setCo2(co2);
            registered.setFuel(fuel);
        }
        fleet.requestCar(employee, existing, registered, startDate);
        return "assignment?faces-redirect=true&employee=" + employee.getEmployeeNo();
    }

    public void back() {
        if (step > 1) {
            step--;
        }
    }

    public Vehicle getSelected() {
        if (available != null && vehicleId != null) {
            for (Vehicle v : available) {
                if (v.getId().equals(vehicleId)) {
                    return v;
                }
            }
        }
        return null;
    }

    public int getStep() { return step; }
    public String getEmployeeNo() { return employeeNo; }
    public void setEmployeeNo(String employeeNo) { this.employeeNo = employeeNo; }
    public Employee getEmployee() { return employee; }
    public String getChoice() { return choice; }
    public void setChoice(String choice) { this.choice = choice; }
    public Long getVehicleId() { return vehicleId; }
    public void setVehicleId(Long vehicleId) { this.vehicleId = vehicleId; }
    public String getPlate() { return plate; }
    public void setPlate(String plate) { this.plate = plate; }
    public String getMake() { return make; }
    public void setMake(String make) { this.make = make; }
    public String getModel() { return model; }
    public void setModel(String model) { this.model = model; }
    public BigDecimal getListPrice() { return listPrice; }
    public void setListPrice(BigDecimal listPrice) { this.listPrice = listPrice; }
    public Integer getCo2() { return co2; }
    public void setCo2(Integer co2) { this.co2 = co2; }
    public String getFuel() { return fuel; }
    public void setFuel(String fuel) { this.fuel = fuel; }
    public Date getStartDate() { return startDate; }
    public void setStartDate(Date startDate) { this.startDate = startDate; }
    public List<Vehicle> getAvailable() { return available; }
}
