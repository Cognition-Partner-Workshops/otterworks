package com.otterworks.fleet.domain;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.Collection;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AssignmentRepository extends JpaRepository<Assignment, Long> {

    boolean existsByVehicle_IdAndEndDateIsNull(Long vehicleId);

    @Query("""
            select a from Assignment a
            where a.employment.person.id = :personId and a.endDate is null
            order by a.startDate desc, a.id desc
            """)
    List<Assignment> findOpenByPersonId(@Param("personId") Long personId);

    @Query("""
            select a from Assignment a
            where a.employment.person.id = :personId
            order by a.startDate desc, a.id desc
            """)
    List<Assignment> findHistoryByPersonId(@Param("personId") Long personId);

    @Query("""
            select max(a.endDate) from Assignment a
            where a.vehicle.id = :vehicleId and a.endDate is not null
            """)
    LocalDate findLatestEndDate(@Param("vehicleId") Long vehicleId);

    @Query("""
            select case when count(a) > 0 then true else false end from Assignment a
            where a.employment.person.id = :personId and a.endDate is null
            """)
    boolean hasOpenAssignmentForPerson(@Param("personId") Long personId);

    @Query("""
            select a.employment.person.id, a.employment.person.employeeNo,
                   a.employment.legacyRef, a.id, a.legacyRef, a.vehicle.id,
                   a.vehicle.registration, a.startDate, a.reason
            from Assignment a
            where a.endDate is null
            order by a.employment.person.employeeNo, a.startDate desc, a.id desc
            """)
    List<Object[]> findAllOpenAssignmentRows();

    @Query("""
            select a.employment.person.id, a.vehicle.registration
            from Assignment a
            where a.endDate is null and a.employment.person.id in :personIds
            order by a.employment.person.id, a.startDate desc, a.id desc
            """)
    List<Object[]> findCurrentRegistrations(@Param("personIds") Collection<Long> personIds);

    @Query("""
            select a from Assignment a
            where a.legacyRef = :legacyRef
            """)
    Optional<Assignment> findByLegacyRef(@Param("legacyRef") String legacyRef);
}
