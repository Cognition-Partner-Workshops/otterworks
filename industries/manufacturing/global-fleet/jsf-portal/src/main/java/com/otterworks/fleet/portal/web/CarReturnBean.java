package com.otterworks.fleet.portal.web;

import com.otterworks.fleet.portal.model.Assignment;
import com.otterworks.fleet.portal.model.Vehicle;
import com.otterworks.fleet.portal.service.FleetService;
import java.io.Serializable;
import java.util.Date;
import javax.faces.bean.ManagedBean;
import javax.faces.bean.ViewScoped;

@ManagedBean(name = "carReturn")
@ViewScoped
public class CarReturnBean implements Serializable {
    private final FleetService fleet = new FleetService();
    private String plate;
    private Vehicle vehicle;
    private Assignment open;
    private Date returnDate = new Date();
    private Integer odometer;
    private String note;
    private boolean done;

    public void load() {
        if (plate != null && !plate.isEmpty() && vehicle == null) {
            find();
        }
    }

    public void find() {
        vehicle = fleet.findVehicleByPlate(plate);
        open = null;
        if (vehicle == null) {
            Faces.error("Kein Fahrzeug mit Kennzeichen " + plate + ".");
            return;
        }
        open = fleet.openAssignmentForVehicle(vehicle);
        if (open == null) {
            Faces.error("Fahrzeug " + plate + " ist keinem Mitarbeiter zugeordnet.");
        }
    }

    public void submit() {
        if (open == null || odometer == null) {
            Faces.error("Kilometerstand angeben.");
            return;
        }
        if (returnDate.before(open.getStartDate())) {
            Faces.error("Rueckgabe vor Uebergabedatum.");
            return;
        }
        fleet.returnCar(open, returnDate, odometer, note);
        Faces.info("Rueckgabe von " + vehicle.getPlate() + " gebucht.");
        done = true;
        open = null;
    }

    public String getPlate() { return plate; }
    public void setPlate(String plate) { this.plate = plate; }
    public Vehicle getVehicle() { return vehicle; }
    public Assignment getOpen() { return open; }
    public Date getReturnDate() { return returnDate; }
    public void setReturnDate(Date returnDate) { this.returnDate = returnDate; }
    public Integer getOdometer() { return odometer; }
    public void setOdometer(Integer odometer) { this.odometer = odometer; }
    public String getNote() { return note; }
    public void setNote(String note) { this.note = note; }
    public boolean isDone() { return done; }
}
