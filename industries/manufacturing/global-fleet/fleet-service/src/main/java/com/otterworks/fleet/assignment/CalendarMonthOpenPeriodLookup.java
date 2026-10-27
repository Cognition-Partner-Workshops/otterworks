package com.otterworks.fleet.assignment;

import java.time.Clock;
import java.time.LocalDate;
import java.time.YearMonth;

public final class CalendarMonthOpenPeriodLookup implements OpenPeriodLookup {

    private final Clock clock;

    public CalendarMonthOpenPeriodLookup(Clock clock) {
        this.clock = clock;
    }

    @Override
    public boolean isOpen(LocalDate date) {
        return !YearMonth.from(date).isBefore(YearMonth.now(clock));
    }
}
