package com.otterworks.fleet.domain;

import jakarta.persistence.Entity;
import jakarta.persistence.Column;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.persistence.Enumerated;
import jakarta.persistence.EnumType;
import java.math.BigDecimal;
import java.time.LocalDate;

@Entity
@Table(name = "employment")
public class Employment {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne
    @JoinColumn(name = "person_id", nullable = false)
    private Person person;

    private Integer grade;

    @Enumerated(EnumType.STRING)
    @Column(length = 64, nullable = false)
    private EmploymentStatus status;

    @Column(name = "hire_date", nullable = false)
    private LocalDate hireDate;

    @Column(name = "leave_date")
    private LocalDate leaveDate;

    @Column(name = "monthly_contribution", precision = 10, scale = 2)
    private BigDecimal monthlyContribution;

    @Column(name = "commute_distance", nullable = false)
    private int commuteDistance;

    @Column(name = "legacy_ref", length = 64, unique = true)
    private String legacyRef;

    protected Employment() {
    }

    public Employment(
            Person person,
            Integer grade,
            EmploymentStatus status,
            LocalDate hireDate,
            LocalDate leaveDate,
            BigDecimal monthlyContribution,
            String legacyRef) {
        this(person, grade, status, hireDate, leaveDate, monthlyContribution, legacyRef, 0);
    }

    public Employment(
            Person person,
            Integer grade,
            EmploymentStatus status,
            LocalDate hireDate,
            LocalDate leaveDate,
            BigDecimal monthlyContribution,
            String legacyRef,
            int commuteDistance) {
        this.person = person;
        this.grade = grade;
        this.status = status;
        this.hireDate = hireDate;
        this.leaveDate = leaveDate;
        this.monthlyContribution = monthlyContribution;
        this.legacyRef = legacyRef;
        this.commuteDistance = commuteDistance;
    }

    public Long getId() {
        return id;
    }

    public Person getPerson() {
        return person;
    }

    public Integer getGrade() {
        return grade;
    }

    public EmploymentStatus getStatus() {
        return status;
    }

    public LocalDate getHireDate() {
        return hireDate;
    }

    public LocalDate getLeaveDate() {
        return leaveDate;
    }

    public BigDecimal getMonthlyContribution() {
        return monthlyContribution;
    }

    public String getLegacyRef() {
        return legacyRef;
    }

    public int getCommuteDistance() {
        return commuteDistance;
    }

    public void setGrade(Integer grade) {
        this.grade = grade;
    }

    public void setStatus(EmploymentStatus status) {
        this.status = status;
    }

    public void setHireDate(LocalDate hireDate) {
        this.hireDate = hireDate;
    }

    public void setLeaveDate(LocalDate leaveDate) {
        this.leaveDate = leaveDate;
    }

    public void setMonthlyContribution(BigDecimal monthlyContribution) {
        this.monthlyContribution = monthlyContribution;
    }

    public void setCommuteDistance(int commuteDistance) {
        this.commuteDistance = commuteDistance;
    }
}
