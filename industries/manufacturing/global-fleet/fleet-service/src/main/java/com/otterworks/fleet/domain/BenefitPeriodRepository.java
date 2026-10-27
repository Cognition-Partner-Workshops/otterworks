package com.otterworks.fleet.domain;

import jakarta.persistence.LockModeType;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface BenefitPeriodRepository extends JpaRepository<BenefitPeriod, Long> {

    Optional<BenefitPeriod> findByPeriod(String period);

    List<BenefitPeriod> findAllByOrderByPeriodDesc();

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select period from BenefitPeriod period where period.period = :period")
    Optional<BenefitPeriod> findByPeriodForUpdate(@Param("period") String period);
}
