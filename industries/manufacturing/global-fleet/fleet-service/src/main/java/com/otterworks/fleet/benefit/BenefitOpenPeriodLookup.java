package com.otterworks.fleet.benefit;

import com.otterworks.fleet.assignment.OpenPeriodLookup;
import com.otterworks.fleet.domain.BenefitPeriodRepository;
import com.otterworks.fleet.domain.BenefitPeriodStatus;
import java.time.Clock;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.format.DateTimeFormatter;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Component;

@Component
public class BenefitOpenPeriodLookup implements OpenPeriodLookup {

    private static final DateTimeFormatter PERIOD_FORMAT = DateTimeFormatter.ofPattern("uuuuMM");

    private final BenefitPeriodRepository benefitPeriodRepository;
    private final Clock clock;

    public BenefitOpenPeriodLookup(
            BenefitPeriodRepository benefitPeriodRepository,
            ObjectProvider<Clock> clockProvider) {
        this.benefitPeriodRepository = benefitPeriodRepository;
        this.clock = clockProvider.getIfAvailable(Clock::systemUTC);
    }

    @Override
    public boolean isOpen(LocalDate date) {
        String period = PERIOD_FORMAT.format(YearMonth.from(date));
        return benefitPeriodRepository.findByPeriod(period)
                .map(benefitPeriod -> benefitPeriod.getStatus() == BenefitPeriodStatus.OPEN)
                .orElseGet(() -> !YearMonth.from(date).isBefore(YearMonth.now(clock)));
    }
}
