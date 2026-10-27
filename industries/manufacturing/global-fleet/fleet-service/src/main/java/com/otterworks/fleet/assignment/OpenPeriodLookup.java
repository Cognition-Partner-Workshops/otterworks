package com.otterworks.fleet.assignment;

import java.time.LocalDate;

public interface OpenPeriodLookup {

    boolean isOpen(LocalDate date);
}
