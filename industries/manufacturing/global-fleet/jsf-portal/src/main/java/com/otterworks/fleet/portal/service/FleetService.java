package com.otterworks.fleet.portal.service;

import com.otterworks.fleet.portal.model.*;
import java.io.Serializable;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Calendar;
import java.util.Date;
import java.util.List;
import javax.persistence.EntityManager;
import javax.persistence.EntityTransaction;

public class FleetService implements Serializable {

    public FleetRule rule() {
        EntityManager em = Jpa.em();
        try {
            return em.find(FleetRule.class, "DE");
        } finally {
            em.close();
        }
    }

    public List<Employee> searchEmployees(String term) {
        EntityManager em = Jpa.em();
        try {
            String t = term == null ? "" : term.trim().toLowerCase();
            return em.createQuery("select e from Employee e where lower(e.employeeNo) like :t "
                    + "or lower(e.lastName) like :t or lower(e.firstName) like :t order by e.lastName, e.firstName",
                    Employee.class).setParameter("t", "%" + t + "%").setMaxResults(50).getResultList();
        } finally {
            em.close();
        }
    }

    public Employee findEmployee(String employeeNo) {
        EntityManager em = Jpa.em();
        try {
            List<Employee> r = em.createQuery("select e from Employee e where e.employeeNo = :n", Employee.class)
                    .setParameter("n", employeeNo).getResultList();
            return r.isEmpty() ? null : r.get(0);
        } finally {
            em.close();
        }
    }

    public Assignment currentAssignment(Employee e) {
        List<Assignment> r = assignments(e);
        for (Assignment a : r) {
            if (a.isOpen()) {
                return a;
            }
        }
        return null;
    }

    public List<Assignment> assignments(Employee e) {
        EntityManager em = Jpa.em();
        try {
            return em.createQuery("select a from Assignment a join fetch a.vehicle where a.employee = :e "
                    + "order by a.startDate desc", Assignment.class).setParameter("e", e).getResultList();
        } finally {
            em.close();
        }
    }

    public List<Vehicle> availableVehicles() {
        EntityManager em = Jpa.em();
        try {
            return em.createQuery("select v from Vehicle v where v.owner is null and not exists "
                    + "(select a from Assignment a where a.vehicle = v and a.endDate is null) order by v.plate",
                    Vehicle.class).getResultList();
        } finally {
            em.close();
        }
    }

    public Vehicle findVehicleByPlate(String plate) {
        EntityManager em = Jpa.em();
        try {
            List<Vehicle> r = em.createQuery("select v from Vehicle v where v.plate = :p", Vehicle.class)
                    .setParameter("p", plate).getResultList();
            return r.isEmpty() ? null : r.get(0);
        } finally {
            em.close();
        }
    }

    public Assignment openAssignmentForVehicle(Vehicle v) {
        EntityManager em = Jpa.em();
        try {
            List<Assignment> r = em.createQuery("select a from Assignment a join fetch a.employee "
                    + "where a.vehicle = :v and a.endDate is null", Assignment.class).setParameter("v", v).getResultList();
            return r.isEmpty() ? null : r.get(0);
        } finally {
            em.close();
        }
    }

    public Assignment requestCar(Employee e, Vehicle existing, Vehicle registered, Date start) {
        EntityManager em = Jpa.em();
        EntityTransaction tx = em.getTransaction();
        try {
            tx.begin();
            Employee emp = em.find(Employee.class, e.getId());
            Vehicle v;
            if (registered != null) {
                registered.setRegisteredOn(start);
                em.persist(registered);
                v = registered;
            } else {
                v = em.find(Vehicle.class, existing.getId());
            }
            v.setOwner(emp);
            CarRequest r = new CarRequest();
            r.setEmployee(emp);
            r.setVehicle(v);
            r.setRequestedOn(new Date());
            r.setStatus("DELIVERED");
            em.persist(r);
            Assignment a = new Assignment();
            a.setEmployee(emp);
            a.setVehicle(v);
            a.setStartDate(start);
            em.persist(a);
            tx.commit();
            return a;
        } finally {
            if (tx.isActive()) {
                tx.rollback();
            }
            em.close();
        }
    }

    public void returnCar(Assignment open, Date returnDate, Integer odometer, String note) {
        EntityManager em = Jpa.em();
        EntityTransaction tx = em.getTransaction();
        try {
            tx.begin();
            Assignment a = em.find(Assignment.class, open.getId());
            a.setEndDate(returnDate);
            a.getVehicle().setOwner(null);
            CarReturn r = new CarReturn();
            r.setAssignment(a);
            r.setReturnDate(returnDate);
            r.setOdometerKm(odometer);
            r.setConditionNote(note);
            em.persist(r);
            tx.commit();
        } finally {
            if (tx.isActive()) {
                tx.rollback();
            }
            em.close();
        }
    }

    public BigDecimal mileageAmount(int km) {
        return rule().getMileageRate().multiply(BigDecimal.valueOf(km)).setScale(2, RoundingMode.HALF_EVEN);
    }

    public MileageClaim submitClaim(Employee e, Date date, int km, String purpose) {
        EntityManager em = Jpa.em();
        EntityTransaction tx = em.getTransaction();
        try {
            tx.begin();
            MileageClaim c = new MileageClaim();
            c.setEmployee(em.find(Employee.class, e.getId()));
            c.setClaimDate(date);
            c.setKm(km);
            c.setPurpose(purpose);
            c.setAmount(mileageAmount(km));
            c.setStatus("SUBMITTED");
            em.persist(c);
            tx.commit();
            return c;
        } finally {
            if (tx.isActive()) {
                tx.rollback();
            }
            em.close();
        }
    }

    public List<MileageClaim> claims(Employee e, Date from, Date to) {
        EntityManager em = Jpa.em();
        try {
            return em.createQuery("select c from MileageClaim c where c.employee = :e and c.claimDate between :f and :t "
                    + "order by c.claimDate", MileageClaim.class)
                    .setParameter("e", e).setParameter("f", from).setParameter("t", to).getResultList();
        } finally {
            em.close();
        }
    }

    public static int daysBetween(Date a, Date b) {
        return (int) Math.round((strip(b).getTime() - strip(a).getTime()) / 86400000d) + 1;
    }

    public static Date strip(Date d) {
        Calendar c = Calendar.getInstance();
        c.setTime(d);
        c.set(Calendar.HOUR_OF_DAY, 12);
        c.set(Calendar.MINUTE, 0);
        c.set(Calendar.SECOND, 0);
        c.set(Calendar.MILLISECOND, 0);
        return c.getTime();
    }
}
