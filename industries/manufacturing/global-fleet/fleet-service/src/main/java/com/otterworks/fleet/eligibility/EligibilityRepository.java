package com.otterworks.fleet.eligibility;

import com.otterworks.fleet.domain.Assignment;
import java.time.LocalDate;
import java.util.List;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

public interface EligibilityRepository extends Repository<Assignment, Long> {

    @Query("""
            select new com.otterworks.fleet.eligibility.BelowGradeHolder(
                p.employeeNo, p.lastName, p.firstName, e.grade, :minGrade,
                e.id, a.id, v.registration, a.startDate, a.endDate)
            from Assignment a
            join a.employment e
            join e.person p
            join a.vehicle v
            where a.startDate <= :lastDay
              and (a.endDate is null or a.endDate >= :firstDay)
              and (e.grade is null or e.grade < :minGrade)
            order by p.lastName, p.firstName, p.employeeNo, a.startDate
            """)
    List<BelowGradeHolder> findBelowGradeHolders(
            @Param("firstDay") LocalDate firstDay,
            @Param("lastDay") LocalDate lastDay,
            @Param("minGrade") int minGrade);
}
