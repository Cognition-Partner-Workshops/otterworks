package com.otterworks.fleet.benefit;

import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface BenefitResultRepository extends JpaRepository<BenefitResult, Long> {

    @EntityGraph(attributePaths = {"lines", "lines.vehicle"})
    @Query("""
            select distinct result from BenefitResult result
            where result.benefitPeriod.period = :period
            """)
    List<BenefitResult> findAllForPeriod(@Param("period") String period);

    @EntityGraph(attributePaths = {"lines", "lines.vehicle"})
    Optional<BenefitResult> findFirstByBenefitPeriod_PeriodAndEmployment_Id(
            String period,
            Long employmentId);
}
