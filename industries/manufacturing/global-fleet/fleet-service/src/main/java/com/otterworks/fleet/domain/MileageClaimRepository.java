package com.otterworks.fleet.domain;

import java.time.LocalDate;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface MileageClaimRepository extends JpaRepository<MileageClaim, Long> {

    List<MileageClaim> findByStatusOrderByClaimDateAscIdAsc(MileageClaimStatus status);

    List<MileageClaim> findByEmployment_IdInAndClaimDateBetweenOrderByClaimDateDescIdDesc(
            Collection<Long> employmentIds, LocalDate from, LocalDate to);

    List<MileageClaim> findByEmployment_IdInAndPaidPeriodAndStatus(
            Collection<Long> employmentIds, String paidPeriod, MileageClaimStatus status);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select claim from MileageClaim claim where claim.id = :id")
    Optional<MileageClaim> findByIdForUpdate(@Param("id") Long id);
}
