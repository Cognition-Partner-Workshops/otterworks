package com.otterworks.fleet.domain;

import jakarta.persistence.Entity;
import jakarta.persistence.Column;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
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

    @Column(length = 64)
    private String status;

    @Column(name = "hire_date", nullable = false)
    private LocalDate hireDate;

    @Column(name = "leave_date")
    private LocalDate leaveDate;

    @Column(name = "monthly_contribution", precision = 10, scale = 2)
    private BigDecimal monthlyContribution;

    protected Employment() {
    }
}
