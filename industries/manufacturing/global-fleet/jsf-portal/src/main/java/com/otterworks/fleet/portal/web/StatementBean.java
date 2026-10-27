package com.otterworks.fleet.portal.web;

import com.otterworks.fleet.portal.model.Assignment;
import com.otterworks.fleet.portal.model.Employee;
import com.otterworks.fleet.portal.model.FleetRule;
import com.otterworks.fleet.portal.model.MileageClaim;
import com.otterworks.fleet.portal.service.FleetService;
import java.io.Serializable;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.Date;
import java.util.List;
import javax.faces.bean.ManagedBean;
import javax.faces.bean.RequestScoped;

@ManagedBean(name = "statement")
@RequestScoped
public class StatementBean implements Serializable {
    private static final BigDecimal HUNDRED = new BigDecimal("100");
    private final FleetService fleet = new FleetService();
    private String employeeNo;
    private String period;
    private Employee employee;
    private FleetRule rule;
    private final List<Line> lines = new ArrayList<Line>();
    private BigDecimal totalBenefit = BigDecimal.ZERO;
    private BigDecimal totalMileage = BigDecimal.ZERO;

    public static class Line implements Serializable {
        private final String plate;
        private final int days;
        private final BigDecimal benefit;

        Line(String plate, int days, BigDecimal benefit) {
            this.plate = plate;
            this.days = days;
            this.benefit = benefit;
        }

        public String getPlate() { return plate; }
        public int getDays() { return days; }
        public BigDecimal getBenefit() { return benefit; }
    }

    public void load() throws Exception {
        if (employeeNo == null) {
            return;
        }
        employee = fleet.findEmployee(employeeNo);
        if (employee == null) {
            Faces.error("Mitarbeiter " + employeeNo + " nicht gefunden.");
            return;
        }
        rule = fleet.rule();
        if (period == null || period.isEmpty()) {
            Calendar c = Calendar.getInstance();
            c.add(Calendar.MONTH, -1);
            period = new SimpleDateFormat("yyyy-MM").format(c.getTime());
        }
        Date from = new SimpleDateFormat("yyyy-MM-dd").parse(period + "-01");
        Calendar end = Calendar.getInstance();
        end.setTime(from);
        end.set(Calendar.DAY_OF_MONTH, end.getActualMaximum(Calendar.DAY_OF_MONTH));
        Date to = end.getTime();
        int monthDays = end.get(Calendar.DAY_OF_MONTH);
        for (Assignment a : fleet.assignments(employee)) {
            Date s = a.getStartDate().after(from) ? a.getStartDate() : from;
            Date e = a.getEndDate() == null || a.getEndDate().after(to) ? to : a.getEndDate();
            if (s.after(e)) {
                continue;
            }
            int days = FleetService.daysBetween(s, e);
            BigDecimal list = a.getVehicle().getListPrice();
            BigDecimal monthly = list.multiply(rule.getBenefitPct()).divide(HUNDRED)
                    .add(list.multiply(rule.getCommutePct()).divide(HUNDRED)
                            .multiply(BigDecimal.valueOf(employee.getCommuteKm())));
            BigDecimal benefit = monthly.multiply(BigDecimal.valueOf(days))
                    .divide(BigDecimal.valueOf(monthDays), 2, RoundingMode.HALF_UP);
            lines.add(new Line(a.getVehicle().getPlate(), days, benefit));
            totalBenefit = totalBenefit.add(benefit);
        }
        for (MileageClaim c : fleet.claims(employee, from, to)) {
            if ("APPROVED".equals(c.getStatus())) {
                totalMileage = totalMileage.add(c.getAmount());
            }
        }
    }

    public String getEmployeeNo() { return employeeNo; }
    public void setEmployeeNo(String employeeNo) { this.employeeNo = employeeNo; }
    public String getPeriod() { return period; }
    public void setPeriod(String period) { this.period = period; }
    public Employee getEmployee() { return employee; }
    public FleetRule getRule() { return rule; }
    public List<Line> getLines() { return lines; }
    public BigDecimal getTotalBenefit() { return totalBenefit; }
    public BigDecimal getTotalMileage() { return totalMileage; }
}
