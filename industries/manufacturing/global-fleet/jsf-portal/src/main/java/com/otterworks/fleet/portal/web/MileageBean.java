package com.otterworks.fleet.portal.web;

import com.otterworks.fleet.portal.model.Employee;
import com.otterworks.fleet.portal.model.MileageClaim;
import com.otterworks.fleet.portal.service.FleetService;
import java.io.Serializable;
import java.math.BigDecimal;
import java.util.Calendar;
import java.util.Collections;
import java.util.Date;
import java.util.List;
import javax.faces.bean.ManagedBean;
import javax.faces.bean.ViewScoped;

@ManagedBean(name = "mileage")
@ViewScoped
public class MileageBean implements Serializable {
    private final FleetService fleet = new FleetService();
    private String employeeNo;
    private Employee employee;
    private Date claimDate = new Date();
    private Integer km;
    private String purpose;
    private BigDecimal preview;
    private List<MileageClaim> claims = Collections.emptyList();

    public void load() {
        if (employeeNo != null && employee == null) {
            employee = fleet.findEmployee(employeeNo);
            refresh();
        }
    }

    public void find() {
        employee = fleet.findEmployee(employeeNo == null ? null : employeeNo.trim().toUpperCase());
        if (employee == null) {
            Faces.error("Mitarbeiter nicht gefunden.");
        }
        refresh();
    }

    public void calculate() {
        preview = km == null ? null : fleet.mileageAmount(km);
    }

    public void submit() {
        if (employee == null || km == null || km <= 0) {
            Faces.error("Mitarbeiter und Kilometer angeben.");
            return;
        }
        MileageClaim c = fleet.submitClaim(employee, claimDate, km, purpose == null ? "" : purpose);
        Faces.info("Reisekostenabrechnung erfasst: " + c.getAmount() + " EUR");
        km = null;
        purpose = null;
        preview = null;
        refresh();
    }

    private void refresh() {
        if (employee == null) {
            claims = Collections.emptyList();
            return;
        }
        Calendar from = Calendar.getInstance();
        from.add(Calendar.MONTH, -6);
        claims = fleet.claims(employee, from.getTime(), new Date());
    }

    public String getEmployeeNo() { return employeeNo; }
    public void setEmployeeNo(String employeeNo) { this.employeeNo = employeeNo; }
    public Employee getEmployee() { return employee; }
    public Date getClaimDate() { return claimDate; }
    public void setClaimDate(Date claimDate) { this.claimDate = claimDate; }
    public Integer getKm() { return km; }
    public void setKm(Integer km) { this.km = km; }
    public String getPurpose() { return purpose; }
    public void setPurpose(String purpose) { this.purpose = purpose; }
    public BigDecimal getPreview() { return preview; }
    public BigDecimal getRate() { return fleet.rule().getMileageRate(); }
    public List<MileageClaim> getClaims() { return claims; }
}
