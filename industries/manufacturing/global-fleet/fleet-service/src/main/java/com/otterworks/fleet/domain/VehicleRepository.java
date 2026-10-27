package com.otterworks.fleet.domain;

import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;

public interface VehicleRepository extends JpaRepository<Vehicle, Long> {

    boolean existsByRegistration(String registration);

    @Query("""
            select v from Vehicle v
            where not exists (
                select a.id from Assignment a
                where a.vehicle = v and a.endDate is null
            )
            order by v.registration
            """)
    List<Vehicle> findPool();

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select v from Vehicle v where v.id = :id")
    Optional<Vehicle> findByIdForUpdate(@Param("id") Long id);
}
