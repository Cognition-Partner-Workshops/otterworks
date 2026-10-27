package com.otterworks.fleet.domain;

import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface BenefitPeriodRepository extends JpaRepository<BenefitPeriod, Long> {

    Optional<BenefitPeriod> findByPeriod(String period);
}
