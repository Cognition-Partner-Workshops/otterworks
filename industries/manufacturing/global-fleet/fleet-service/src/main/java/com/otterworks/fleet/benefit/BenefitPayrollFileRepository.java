package com.otterworks.fleet.benefit;

import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface BenefitPayrollFileRepository extends JpaRepository<BenefitPayrollFile, Long> {

    Optional<BenefitPayrollFile> findByBenefitPeriod_Period(String period);
}
