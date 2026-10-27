package com.otterworks.fleet.domain;

import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.Optional;
import java.time.LocalDate;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface EmploymentRepository extends JpaRepository<Employment, Long> {

    Optional<Employment> findFirstByPersonAndStatusOrderByHireDateDescIdDesc(
            Person person, EmploymentStatus status);

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
}
