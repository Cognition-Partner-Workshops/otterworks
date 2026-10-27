package com.otterworks.fleet.domain;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface EmploymentRepository extends JpaRepository<Employment, Long> {

    Optional<Employment> findFirstByPersonOrderByHireDateDescIdDesc(Person person);

    Optional<Employment> findFirstByPersonAndLegacyRef(Person person, String legacyRef);

    Optional<Employment> findFirstByLegacyRef(String legacyRef);

    List<Employment> findByPersonOrderByHireDateDescIdDesc(Person person);

    @Query("""
            select e from Employment e
            where e.person = :person
              and e.hireDate <= :date
              and (e.leaveDate is null or e.leaveDate >= :date)
            order by e.hireDate desc, e.id desc
            """)
    List<Employment> findCovering(
            @Param("person") Person person,
            @Param("date") LocalDate date,
            org.springframework.data.domain.Pageable pageable);

    List<Employment> findByPersonOrderByHireDateAscIdAsc(Person person);

    @Query("""
            select employment from Employment employment
            where employment.hireDate <= :periodEnd
              and (employment.leaveDate is null or employment.leaveDate >= :periodStart)
            order by employment.id
            """)
    List<Employment> findInRun(
            @Param("periodStart") LocalDate periodStart,
            @Param("periodEnd") LocalDate periodEnd);

    @Query("""
            select employment from Employment employment
            where employment.person.employeeNo = :employeeNo
              and employment.hireDate <= :periodEnd
              and (employment.leaveDate is null or employment.leaveDate >= :periodStart)
            order by employment.hireDate desc, employment.id desc
            """)
    List<Employment> findInRunByEmployeeNo(
            @Param("employeeNo") String employeeNo,
            @Param("periodStart") LocalDate periodStart,
            @Param("periodEnd") LocalDate periodEnd);
}
